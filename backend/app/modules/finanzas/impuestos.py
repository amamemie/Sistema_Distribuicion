"""IVA e IT por mes (D-30, T-27).

- Ventas del mes: lo facturado de los pedidos entregados en el mes (monto por cobrar).
- IVA débito = IVA % de las ventas (en Bolivia el precio facturado ya incluye el IVA).
- IVA crédito = IVA % de las compras y gastos con factura del mes.
- Si el crédito supera al débito, el sobrante pasa al mes siguiente (saldo a favor).
- IT = IT % de las ventas.
"""

import uuid
from collections import defaultdict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.compras.models import Compra, EstadoCompra
from app.modules.finanzas import cuentas
from app.modules.finanzas.models import EstadoRegistro, Gasto
from app.modules.finanzas.parametros import ParametrosFinanzas
from app.modules.finanzas.schemas import ImpuestoMes

CERO = Decimal(0)


def _pct(base: Decimal, pct: Decimal) -> Decimal:
    return (base * pct / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def inicio_mes(d: date) -> date:
    return d.replace(day=1)


def siguiente_mes(d: date) -> date:
    return date(d.year + d.month // 12, d.month % 12 + 1, 1)


def ventas_por_mes(
    db: Session, empresa_id: uuid.UUID, p: ParametrosFinanzas
) -> dict[date, Decimal]:
    resultado: defaultdict[date, Decimal] = defaultdict(lambda: CERO)
    for c in cuentas.cuentas(db, empresa_id, p.dias_credito):
        resultado[inicio_mes(c.fecha)] += c.monto
    return resultado


def _compras_con_factura(db: Session, empresa_id: uuid.UUID) -> dict[date, Decimal]:
    mes = func.date_trunc("month", Compra.fecha)
    return {
        m.date(): total or CERO
        for m, total in db.execute(
            select(mes, func.sum(Compra.total))
            .where(
                Compra.empresa_id == empresa_id,
                Compra.estado == EstadoCompra.REGISTRADA,
                Compra.con_factura.is_(True),
            )
            .group_by(mes)
        )
    }


def _gastos_con_factura(db: Session, empresa_id: uuid.UUID) -> dict[date, Decimal]:
    mes = func.date_trunc("month", Gasto.fecha)
    return {
        m.date(): total or CERO
        for m, total in db.execute(
            select(mes, func.sum(Gasto.monto))
            .where(
                Gasto.empresa_id == empresa_id,
                Gasto.estado == EstadoRegistro.REGISTRADO,
                Gasto.con_factura.is_(True),
            )
            .group_by(mes)
        )
    }


def mensual(
    db: Session, empresa_id: uuid.UUID, p: ParametrosFinanzas, desde: date, hasta: date
) -> list[ImpuestoMes]:
    """Un renglón por mes entre `desde` y `hasta`. El saldo a favor se arrastra desde el primer
    mes con movimiento, aunque sea anterior al rango pedido."""
    ventas = ventas_por_mes(db, empresa_id, p)
    compras = _compras_con_factura(db, empresa_id)
    gastos = _gastos_con_factura(db, empresa_id)
    desde, hasta = inicio_mes(desde), inicio_mes(hasta)
    meses_con_datos = [m for m in (*ventas, *compras, *gastos) if m < desde]
    mes = min([*meses_con_datos, desde])
    saldo = CERO
    filas: list[ImpuestoMes] = []
    while mes <= hasta:
        v, c, g = ventas.get(mes, CERO), compras.get(mes, CERO), gastos.get(mes, CERO)
        debito = _pct(v, p.iva_pct)
        credito = _pct(c + g, p.iva_pct)
        neto = debito - credito - saldo
        iva_pagar = max(neto, CERO)
        saldo_siguiente = max(-neto, CERO)
        it = _pct(v, p.it_pct)
        if mes >= desde:
            filas.append(
                ImpuestoMes(
                    mes=mes,
                    ventas=v,
                    iva_debito=debito,
                    compras_con_factura=c,
                    gastos_con_factura=g,
                    iva_credito=credito,
                    saldo_anterior=saldo,
                    iva_pagar=iva_pagar,
                    saldo_siguiente=saldo_siguiente,
                    it=it,
                    total_pagar=iva_pagar + it,
                )
            )
        saldo = saldo_siguiente
        mes = siguiente_mes(mes)
    return filas
