"""Cuentas por cobrar: cada pedido ENTREGADO es un documento por cobrar (spec 7, D-27).

- Monto: el ingreso del pedido (lo alistado menos lo devuelto) con el descuento de la nota de
  recepción aplicado en proporción (total de la nota / suma de sus líneas, T-26).
- Fecha: la de la entrega; vence a los `dias_credito` días (40 por defecto).
- Saldo = monto - lo cobrado - las diferencias cerradas. Negativo = saldo a favor de la cadena
  (p. ej. una devolución registrada después de que pagaron).
"""

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.tiempo import fecha_local, hoy
from app.modules.clientes.models import Cadena, SucursalCliente
from app.modules.finanzas.models import Cobro, CobroDetalle, EstadoRegistro
from app.modules.pedidos.models import EstadoPedido, Pedido, PedidoLinea

CERO = Decimal(0)
CENTAVO = Decimal("0.01")


class EstadoCuenta(StrEnum):
    PENDIENTE = "PENDIENTE"  # no se cobró nada
    PARCIAL = "PARCIAL"  # se cobró una parte
    SALDADA = "SALDADA"
    A_FAVOR = "A_FAVOR"  # se cobró de más (devolución posterior al pago)


@dataclass
class Cuenta:
    pedido_id: uuid.UUID
    numero: int
    numero_oc: str | None
    cadena_id: uuid.UUID
    cadena: str
    sucursal: str | None
    fecha: date  # entrega
    vencimiento: date
    monto: Decimal
    cobrado: Decimal
    diferencia: Decimal
    costo: Decimal = CERO  # costo de lo entregado (neto de devoluciones)

    @property
    def saldo(self) -> Decimal:
        return self.monto - self.cobrado - self.diferencia

    @property
    def estado(self) -> EstadoCuenta:
        if self.saldo < 0:
            return EstadoCuenta.A_FAVOR
        if self.saldo == 0:
            return EstadoCuenta.SALDADA
        return (
            EstadoCuenta.PARCIAL if self.cobrado + self.diferencia > 0 else EstadoCuenta.PENDIENTE
        )

    def dias_vencida(self, al: date) -> int:
        return max((al - self.vencimiento).days, 0) if self.saldo > 0 else 0


def monto_facturado(
    ingreso: Decimal | None, total_nota: Decimal | None, suma_lineas: Decimal | None
) -> Decimal:
    """Ingreso del pedido con el descuento de la nota aplicado en proporción."""
    ingreso = ingreso or CERO
    if total_nota is not None and suma_lineas and 0 <= total_nota < suma_lineas:
        ingreso = ingreso * total_nota / suma_lineas
    return ingreso.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def cuentas(
    db: Session,
    empresa_id: uuid.UUID,
    dias_credito: int,
    *,
    cadena_id: uuid.UUID | None = None,
    ubicacion_id: uuid.UUID | None = None,
    pedido_ids: list[uuid.UUID] | None = None,
    entregado_desde: date | None = None,
    entregado_hasta: date | None = None,
) -> list[Cuenta]:
    """Cuentas de los pedidos entregados, ordenadas por fecha de entrega."""
    suma_lineas = (
        select(
            PedidoLinea.pedido_id,
            func.sum(
                func.coalesce(
                    PedidoLinea.total_linea_oc,
                    func.round(PedidoLinea.cantidad_oc * PedidoLinea.precio_oc, 2),
                )
            ).label("suma"),
        )
        .group_by(PedidoLinea.pedido_id)
        .subquery()
    )
    entrega = fecha_local(Pedido.entregado_at)
    consulta = (
        select(
            Pedido.id,
            Pedido.numero,
            Pedido.numero_oc,
            Pedido.cadena_id,
            Cadena.nombre,
            SucursalCliente.nombre,
            entrega,
            Pedido.ingreso,
            Pedido.total_oc,
            suma_lineas.c.suma,
            Pedido.costo,
        )
        .join(Cadena, Cadena.id == Pedido.cadena_id)
        .outerjoin(SucursalCliente, SucursalCliente.id == Pedido.sucursal_cliente_id)
        .outerjoin(suma_lineas, suma_lineas.c.pedido_id == Pedido.id)
        .where(Pedido.empresa_id == empresa_id, Pedido.estado == EstadoPedido.ENTREGADO)
        .order_by(entrega, Pedido.numero)
    )
    if cadena_id:
        consulta = consulta.where(Pedido.cadena_id == cadena_id)
    if ubicacion_id:
        consulta = consulta.where(Pedido.ubicacion_id == ubicacion_id)
    if pedido_ids is not None:
        consulta = consulta.where(Pedido.id.in_(pedido_ids))
    if entregado_desde:
        consulta = consulta.where(entrega >= entregado_desde)
    if entregado_hasta:
        consulta = consulta.where(entrega <= entregado_hasta)
    filas = list(db.execute(consulta))
    aplicado = _aplicado(db, [f[0] for f in filas])
    plazo = timedelta(days=dias_credito)
    return [
        Cuenta(
            pedido_id=pid,
            numero=numero,
            numero_oc=oc,
            cadena_id=cid,
            cadena=cadena,
            sucursal=sucursal,
            fecha=fecha,
            vencimiento=fecha + plazo,
            monto=monto_facturado(ingreso, total, suma),
            cobrado=aplicado[pid][0],
            diferencia=aplicado[pid][1],
            costo=costo or CERO,
        )
        for pid, numero, oc, cid, cadena, sucursal, fecha, ingreso, total, suma, costo in filas
    ]


def _aplicado(
    db: Session, pedido_ids: list[uuid.UUID]
) -> defaultdict[uuid.UUID, tuple[Decimal, Decimal]]:
    resultado: defaultdict[uuid.UUID, tuple[Decimal, Decimal]] = defaultdict(lambda: (CERO, CERO))
    if not pedido_ids:
        return resultado
    for pid, cobrado, diferencia in db.execute(
        select(
            CobroDetalle.pedido_id, func.sum(CobroDetalle.monto), func.sum(CobroDetalle.diferencia)
        )
        .join(Cobro, Cobro.id == CobroDetalle.cobro_id)
        .where(CobroDetalle.pedido_id.in_(pedido_ids), Cobro.estado == EstadoRegistro.REGISTRADO)
        .group_by(CobroDetalle.pedido_id)
    ):
        resultado[pid] = (cobrado or CERO, diferencia or CERO)
    return resultado


@dataclass
class ResumenCadena:
    cadena_id: uuid.UUID
    cadena: str
    pedidos_pendientes: int = 0
    pendiente: Decimal = CERO
    vencido: Decimal = CERO
    a_favor: Decimal = CERO
    mas_antiguo: date | None = None  # entrega más antigua con saldo


def por_cadena(lista: list[Cuenta], al: date | None = None) -> list[ResumenCadena]:
    al = al or hoy()
    resumen: dict[uuid.UUID, ResumenCadena] = {}
    for c in lista:
        r = resumen.setdefault(c.cadena_id, ResumenCadena(cadena_id=c.cadena_id, cadena=c.cadena))
        if c.saldo > 0:
            r.pedidos_pendientes += 1
            r.pendiente += c.saldo
            if c.vencimiento < al:
                r.vencido += c.saldo
            r.mas_antiguo = min(r.mas_antiguo or c.fecha, c.fecha)
        elif c.saldo < 0:
            r.a_favor -= c.saldo
    return sorted(resumen.values(), key=lambda r: (-r.pendiente, r.cadena))
