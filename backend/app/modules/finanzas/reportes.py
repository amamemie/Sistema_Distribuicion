"""Reportes financieros (mismo formato `Reporte`: se ven en pantalla y se exportan).

- resultados: ventas - costo - gastos - impuestos = ganancia neta (estado de resultados de
  gestión, T-28). Requiere además `costos.ver`.
- flujo_caja: lo cobrado frente a lo pagado (compras y gastos) por período.
- cobranza: antigüedad de los saldos por cobrar y días promedio de cobro.
- impuestos: IVA e IT por mes, con el crédito fiscal que pasa de un mes a otro.

La venta se reconoce en la fecha de entrega (cuando se factura), no en la de la nota (T-27).
"""

import uuid
from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session

from app.core.errors import SinPermiso
from app.core.tiempo import fecha_local, hoy
from app.modules.compras.models import Compra, EstadoCompra
from app.modules.finanzas import cuentas, impuestos, parametros
from app.modules.finanzas.models import CategoriaGasto, Cobro, CobroDetalle, EstadoRegistro, Gasto
from app.modules.finanzas.parametros import ParametrosFinanzas
from app.modules.identidad.contexto import Contexto
from app.modules.inventario.models import Lote
from app.modules.organizacion.models import Ubicacion
from app.modules.pedidos.models import Pedido, PedidoLinea, PedidoLineaLote
from app.modules.reportes.consultas import (
    _dinero,
    _filtros_texto,
    _kpi,
    _validar,
    etiqueta_periodo,
    inicio_periodo,
    periodo_anterior,
    periodos,
)
from app.modules.reportes.schemas import Columna, Filtros, Reporte, Serie, Tabla

CERO = Decimal(0)
MESES_LARGOS = [
    "Enero",
    "Febrero",
    "Marzo",
    "Abril",
    "Mayo",
    "Junio",
    "Julio",
    "Agosto",
    "Septiembre",
    "Octubre",
    "Noviembre",
    "Diciembre",
]


def _pct(base: Decimal, pct: Decimal) -> Decimal:
    return _dinero(base * pct / 100)


def _margen(parte: Decimal, total: Decimal) -> Decimal | None:
    return (parte * 100 / total).quantize(Decimal("0.01")) if total > 0 else None


# ================================================================ datos base


def _gastos(
    db: Session, empresa_id: uuid.UUID, desde: date, hasta: date, ubicacion_id: uuid.UUID | None
) -> list[tuple[date, str, str | None, Decimal, bool]]:
    """(fecha, categoría, ubicación, monto, con_factura) de los gastos vigentes."""
    condiciones: list[ColumnElement[bool]] = [
        Gasto.empresa_id == empresa_id,
        Gasto.estado == EstadoRegistro.REGISTRADO,
        Gasto.fecha.between(desde, hasta),
    ]
    if ubicacion_id:
        condiciones.append(Gasto.ubicacion_id == ubicacion_id)
    return [
        (f, c, u, m, fac)
        for f, c, u, m, fac in db.execute(
            select(
                Gasto.fecha, CategoriaGasto.nombre, Ubicacion.nombre, Gasto.monto, Gasto.con_factura
            )
            .join(CategoriaGasto, CategoriaGasto.id == Gasto.categoria_id)
            .outerjoin(Ubicacion, Ubicacion.id == Gasto.ubicacion_id)
            .where(*condiciones)
        )
    ]


def _pagos_compras(
    db: Session, empresa_id: uuid.UUID, desde: date, hasta: date, ubicacion_id: uuid.UUID | None
) -> list[tuple[date, Decimal]]:
    """(fecha de pago, total) de las compras vigentes pagadas en el rango."""
    condiciones: list[ColumnElement[bool]] = [
        Compra.empresa_id == empresa_id,
        Compra.estado == EstadoCompra.REGISTRADA,
        Compra.fecha_pago.between(desde, hasta),
    ]
    if ubicacion_id:
        condiciones.append(Compra.ubicacion_id == ubicacion_id)
    return [
        (f, t)
        for f, t in db.execute(select(Compra.fecha_pago, Compra.total).where(*condiciones))
        if f is not None
    ]


class _Resultado:
    """Acumula ventas, costo, gastos e impuestos de un período."""

    def __init__(self) -> None:
        self.ventas = CERO
        self.costo = CERO
        self.gastos = CERO
        # Costo de lo vendido que vino de compras con factura + gastos con factura (T-28).
        self.credito_base = CERO

    def impuestos(self, p: ParametrosFinanzas) -> tuple[Decimal, Decimal]:
        """(IVA de lo vendido, IT). El IVA se calcula sobre el margen: débito de las ventas
        menos el crédito del costo de lo vendido y de los gastos con factura. Así una compra
        grande no "regala" ganancia en el mes en que se compra."""
        return _pct(self.ventas, p.iva_pct) - _pct(self.credito_base, p.iva_pct), _pct(
            self.ventas, p.it_pct
        )

    def neta(self, p: ParametrosFinanzas) -> Decimal:
        iva, it = self.impuestos(p)
        return self.ventas - self.costo - self.gastos - iva - it


def _resultados_rango(
    db: Session, ctx: Contexto, f: Filtros, desde: date, hasta: date, p: ParametrosFinanzas
) -> tuple[dict[date, _Resultado], list[tuple[date, str, str | None, Decimal, bool]]]:
    por_periodo: dict[date, _Resultado] = {
        d: _Resultado() for d in periodos(desde, hasta, f.agrupacion)
    }

    def periodo(d: date) -> _Resultado:
        return por_periodo[inicio_periodo(d, f.agrupacion)]

    fechas: dict[uuid.UUID, date] = {}
    for c in cuentas.cuentas(
        db,
        ctx.empresa_id,
        p.dias_credito,
        cadena_id=f.cadena_id,
        ubicacion_id=f.ubicacion_id,
        entregado_desde=desde,
        entregado_hasta=hasta,
    ):
        r = periodo(c.fecha)
        r.ventas += c.monto
        r.costo += c.costo
        fechas[c.pedido_id] = c.fecha
    for pedido_id, costo in _costo_con_factura(db, list(fechas)).items():
        periodo(fechas[pedido_id]).credito_base += costo
    gastos = _gastos(db, ctx.empresa_id, desde, hasta, f.ubicacion_id)
    for fecha, _cat, _ub, monto, factura in gastos:
        r = periodo(fecha)
        r.gastos += monto
        if factura:
            r.credito_base += monto
    return por_periodo, gastos


def _costo_con_factura(db: Session, pedido_ids: list[uuid.UUID]) -> dict[uuid.UUID, Decimal]:
    """Costo de lo entregado (neto de devoluciones) que salió de lotes comprados con factura."""
    if not pedido_ids:
        return {}
    return {
        pid: _dinero(costo)
        for pid, costo in db.execute(
            select(
                PedidoLinea.pedido_id,
                func.sum(
                    (PedidoLineaLote.cantidad - PedidoLineaLote.devuelta)
                    * PedidoLineaLote.costo_unitario
                ),
            )
            .join(PedidoLineaLote, PedidoLineaLote.linea_id == PedidoLinea.id)
            .join(Lote, Lote.id == PedidoLineaLote.lote_id)
            .join(Compra, (Lote.origen_tipo == "COMPRA") & (Compra.id == Lote.origen_id))
            .where(PedidoLinea.pedido_id.in_(pedido_ids), Compra.con_factura.is_(True))
            .group_by(PedidoLinea.pedido_id)
        )
    }


def _sumar(resultados: dict[date, _Resultado]) -> _Resultado:
    total = _Resultado()
    for r in resultados.values():
        total.ventas += r.ventas
        total.costo += r.costo
        total.gastos += r.gastos
        total.credito_base += r.credito_base
    return total


# ================================================================ estado de resultados


def resultados(db: Session, ctx: Contexto, f: Filtros) -> Reporte:
    """Estado de resultados de gestión: de la ganancia bruta a la ganancia neta."""
    _validar(f)
    if not ctx.puede("costos.ver"):
        raise SinPermiso("No tiene permiso para ver costos ni ganancias.")
    p = parametros.leer(db, ctx.empresa_id)
    por_periodo, gastos = _resultados_rango(db, ctx, f, f.desde, f.hasta, p)
    total = _sumar(por_periodo)
    a_desde, a_hasta = periodo_anterior(f.desde, f.hasta)
    anterior = _sumar(_resultados_rango(db, ctx, f, a_desde, a_hasta, p)[0])
    iva, it = total.impuestos(p)
    a_iva, a_it = anterior.impuestos(p)
    bruta = total.ventas - total.costo
    neta = total.neta(p)

    por_categoria: defaultdict[str, Decimal] = defaultdict(lambda: CERO)
    por_ubicacion: defaultdict[str, Decimal] = defaultdict(lambda: CERO)
    for _f, categoria, ubicacion, monto, _fac in gastos:
        por_categoria[categoria] += monto
        por_ubicacion[ubicacion or "General (sin ubicación)"] += monto

    def fila(concepto: str, monto: Decimal, nivel: str = "detalle") -> dict[str, Any]:
        return {
            "concepto": concepto,
            "monto": _dinero(monto),
            "porcentaje": _margen(monto, total.ventas),
            "nivel": nivel,
        }

    estado = [
        fila("Ventas facturadas", total.ventas, "total"),
        fila("(-) Costo de lo vendido", -total.costo),
        fila("= Ganancia bruta", bruta, "total"),
        *[
            fila(f"(-) {nombre}", -monto)
            for nombre, monto in sorted(por_categoria.items(), key=lambda x: -x[1])
        ],
        fila("= Ganancia después de gastos", bruta - total.gastos, "total"),
        fila(f"(-) IVA de lo vendido ({p.iva_pct.normalize():f} % del margen con factura)", -iva),
        fila(f"(-) IT ({p.it_pct.normalize():f} %)", -it),
        fila("= Ganancia neta", neta, "total"),
    ]
    filas_periodo = []
    for d, r in por_periodo.items():
        r_iva, r_it = r.impuestos(p)
        filas_periodo.append(
            {
                "periodo": etiqueta_periodo(d, f.agrupacion),
                "ventas": _dinero(r.ventas),
                "costo": _dinero(r.costo),
                "bruta": _dinero(r.ventas - r.costo),
                "gastos": _dinero(r.gastos),
                "impuestos": _dinero(r_iva + r_it),
                "neta": _dinero(r.neta(p)),
                "margen": _margen(r.neta(p), r.ventas),
            }
        )
    return Reporte(
        clave="resultados",
        titulo="Estado de resultados",
        descripcion=(
            "Ventas entregadas (facturadas) menos su costo, los gastos operativos y los impuestos "
            "de lo vendido. Es un resultado de gestión: los montos incluyen IVA; el IVA se resta "
            "sobre el margen (ventas menos costo y gastos con factura). Lo que se declara cada mes "
            "está en el reporte de Impuestos."
        ),
        filtros_texto=_filtros_texto(db, ctx, f),
        con_rentabilidad=True,
        kpis=[
            _kpi(
                "ventas",
                "Ventas facturadas",
                "dinero",
                _dinero(total.ventas),
                _dinero(anterior.ventas),
            ),
            _kpi(
                "bruta",
                "Ganancia bruta",
                "dinero",
                _dinero(bruta),
                _dinero(anterior.ventas - anterior.costo),
            ),
            _kpi(
                "gastos",
                "Gastos operativos",
                "dinero",
                _dinero(total.gastos),
                _dinero(anterior.gastos),
            ),
            _kpi("impuestos", "IVA + IT", "dinero", _dinero(iva + it), _dinero(a_iva + a_it)),
            _kpi("neta", "Ganancia neta", "dinero", _dinero(neta), _dinero(anterior.neta(p))),
            _kpi(
                "margen_neto",
                "Margen neto",
                "porcentaje",
                _margen(neta, total.ventas),
                _margen(anterior.neta(p), anterior.ventas),
            ),
        ],
        series=[
            Serie(
                clave="resultado",
                titulo="Ganancia bruta y neta por período (Bs)",
                tipo="dinero",
                forma="barras",
                claves=[
                    Columna(clave="bruta", titulo="Ganancia bruta", tipo="dinero"),
                    Columna(clave="neta", titulo="Ganancia neta", tipo="dinero"),
                ],
                puntos=[
                    {"etiqueta": x["periodo"], "bruta": x["bruta"], "neta": x["neta"]}
                    for x in filas_periodo
                ],
            )
        ],
        tablas=[
            Tabla(
                clave="estado",
                titulo="Estado de resultados",
                descripcion="El porcentaje es sobre las ventas.",
                columnas=[
                    Columna(clave="concepto", titulo="Concepto"),
                    Columna(clave="monto", titulo="Monto (Bs)", tipo="dinero"),
                    Columna(clave="porcentaje", titulo="% de ventas", tipo="porcentaje"),
                ],
                filas=estado,
            ),
            Tabla(
                clave="periodos",
                titulo="Por período",
                columnas=[
                    Columna(clave="periodo", titulo="Período"),
                    Columna(clave="ventas", titulo="Ventas", tipo="dinero"),
                    Columna(clave="costo", titulo="Costo", tipo="dinero"),
                    Columna(clave="bruta", titulo="Ganancia bruta", tipo="dinero"),
                    Columna(clave="gastos", titulo="Gastos", tipo="dinero"),
                    Columna(clave="impuestos", titulo="IVA + IT", tipo="dinero"),
                    Columna(clave="neta", titulo="Ganancia neta", tipo="dinero"),
                    Columna(clave="margen", titulo="Margen neto", tipo="porcentaje"),
                ],
                filas=filas_periodo,
            ),
            Tabla(
                clave="gastos_ubicacion",
                titulo="Gastos por ubicación",
                columnas=[
                    Columna(clave="ubicacion", titulo="Ubicación"),
                    Columna(clave="monto", titulo="Monto (Bs)", tipo="dinero"),
                ],
                filas=[
                    {"ubicacion": u, "monto": _dinero(m)}
                    for u, m in sorted(por_ubicacion.items(), key=lambda x: -x[1])
                ],
            ),
        ],
    )


# ================================================================ flujo de caja


def flujo_caja(db: Session, ctx: Contexto, f: Filtros) -> Reporte:
    """Dinero que entró (cobros) y salió (compras pagadas y gastos) por período."""
    _validar(f)
    p = parametros.leer(db, ctx.empresa_id)
    por_periodo: dict[date, dict[str, Decimal]] = {
        d: defaultdict(lambda: CERO) for d in periodos(f.desde, f.hasta, f.agrupacion)
    }

    def periodo(d: date) -> dict[str, Decimal]:
        return por_periodo[inicio_periodo(d, f.agrupacion)]

    condiciones: list[ColumnElement[bool]] = [
        Cobro.empresa_id == ctx.empresa_id,
        Cobro.estado == EstadoRegistro.REGISTRADO,
        Cobro.fecha.between(f.desde, f.hasta),
        Cobro.monto > 0,
    ]
    if f.cadena_id:
        condiciones.append(Cobro.cadena_id == f.cadena_id)
    cobros = list(db.scalars(select(Cobro).where(*condiciones).order_by(Cobro.fecha, Cobro.numero)))
    for c in cobros:
        periodo(c.fecha)["cobros"] += c.monto
    for fecha, total in _pagos_compras(db, ctx.empresa_id, f.desde, f.hasta, f.ubicacion_id):
        periodo(fecha)["compras"] += total
    gastos = _gastos(db, ctx.empresa_id, f.desde, f.hasta, f.ubicacion_id)
    por_categoria: defaultdict[str, Decimal] = defaultdict(lambda: CERO)
    for fecha, categoria, _ub, monto, _fac in gastos:
        periodo(fecha)["gastos"] += monto
        por_categoria[categoria] += monto

    filas = []
    acumulado = CERO
    for d, v in por_periodo.items():
        salidas = v["compras"] + v["gastos"]
        neto = v["cobros"] - salidas
        acumulado += neto
        filas.append(
            {
                "periodo": etiqueta_periodo(d, f.agrupacion),
                "cobros": _dinero(v["cobros"]),
                "compras": _dinero(v["compras"]),
                "gastos": _dinero(v["gastos"]),
                "salidas": _dinero(salidas),
                "neto": _dinero(neto),
                "acumulado": _dinero(acumulado),
            }
        )
    entradas = sum((v["cobros"] for v in por_periodo.values()), CERO)
    salidas_total = sum((v["compras"] + v["gastos"] for v in por_periodo.values()), CERO)
    pendientes = cuentas.por_cadena(
        cuentas.cuentas(db, ctx.empresa_id, p.dias_credito, cadena_id=f.cadena_id)
    )
    return Reporte(
        clave="flujo_caja",
        titulo="Flujo de caja",
        descripcion=(
            "Entradas: transferencias cobradas a los supermercados. Salidas: compras pagadas "
            "(al contado el día de la compra) y gastos operativos."
        ),
        filtros_texto=_filtros_texto(db, ctx, f),
        con_rentabilidad=False,
        kpis=[
            _kpi("entradas", "Cobrado", "dinero", entradas),
            _kpi("salidas", "Pagado", "dinero", salidas_total),
            _kpi("neto", "Flujo neto", "dinero", entradas - salidas_total),
            _kpi(
                "por_cobrar",
                "Por cobrar hoy",
                "dinero",
                _dinero(sum((r.pendiente for r in pendientes), CERO)),
            ),
            _kpi(
                "vencido",
                "Vencido hoy",
                "dinero",
                _dinero(sum((r.vencido for r in pendientes), CERO)),
            ),
        ],
        series=[
            Serie(
                clave="flujo",
                titulo="Entradas y salidas por período (Bs)",
                tipo="dinero",
                forma="barras",
                claves=[
                    Columna(clave="cobros", titulo="Cobrado", tipo="dinero"),
                    Columna(clave="salidas", titulo="Pagado", tipo="dinero"),
                ],
                puntos=[
                    {"etiqueta": x["periodo"], "cobros": x["cobros"], "salidas": x["salidas"]}
                    for x in filas
                ],
            )
        ],
        tablas=[
            Tabla(
                clave="periodos",
                titulo="Por período",
                columnas=[
                    Columna(clave="periodo", titulo="Período"),
                    Columna(clave="cobros", titulo="Cobrado", tipo="dinero"),
                    Columna(clave="compras", titulo="Compras pagadas", tipo="dinero"),
                    Columna(clave="gastos", titulo="Gastos", tipo="dinero"),
                    Columna(clave="neto", titulo="Neto", tipo="dinero"),
                    Columna(clave="acumulado", titulo="Acumulado", tipo="dinero"),
                ],
                filas=filas,
            ),
            Tabla(
                clave="cobros",
                titulo="Cobros del período",
                columnas=[
                    Columna(clave="fecha", titulo="Fecha", tipo="fecha"),
                    Columna(clave="cadena", titulo="Cadena"),
                    Columna(clave="referencia", titulo="N.º de operación"),
                    Columna(clave="pedidos", titulo="Pedidos", tipo="entero"),
                    Columna(clave="monto", titulo="Monto (Bs)", tipo="dinero"),
                ],
                filas=[
                    {
                        "fecha": c.fecha,
                        "cadena": c.cadena.nombre,
                        "referencia": c.referencia,
                        "pedidos": len(c.detalles),
                        "monto": c.monto,
                    }
                    for c in cobros
                ],
            ),
            Tabla(
                clave="gastos",
                titulo="Gastos por categoría",
                columnas=[
                    Columna(clave="categoria", titulo="Categoría"),
                    Columna(clave="monto", titulo="Monto (Bs)", tipo="dinero"),
                ],
                filas=[
                    {"categoria": c, "monto": _dinero(m)}
                    for c, m in sorted(por_categoria.items(), key=lambda x: -x[1])
                ],
            ),
        ],
    )


# ================================================================ cobranza


TRAMOS = (
    ("por_vencer", "Por vencer"),
    ("d1_30", "Vencido 1-30 días"),
    ("d31_60", "Vencido 31-60 días"),
    ("d60", "Vencido más de 60 días"),
)


def _tramo(dias: int) -> str:
    if dias <= 0:
        return "por_vencer"
    if dias <= 30:
        return "d1_30"
    return "d31_60" if dias <= 60 else "d60"


def cobranza(db: Session, ctx: Contexto, f: Filtros) -> Reporte:
    """Antigüedad de saldos (al día de hoy) y días promedio de cobro en el rango."""
    _validar(f)
    p = parametros.leer(db, ctx.empresa_id)
    al = hoy()
    lista = [
        c
        for c in cuentas.cuentas(db, ctx.empresa_id, p.dias_credito, cadena_id=f.cadena_id)
        if c.saldo > 0
    ]
    por_cadena: dict[str, dict[str, Decimal]] = defaultdict(lambda: defaultdict(lambda: CERO))
    for c in lista:
        por_cadena[c.cadena][_tramo(c.dias_vencida(al))] += c.saldo
    filas_cadena = [
        {"cadena": cadena}
        | {k: _dinero(v[k]) for k, _ in TRAMOS}
        | {"total": _dinero(sum(v.values(), CERO))}
        for cadena, v in sorted(por_cadena.items())
    ]

    # Días de cobro: desde la entrega hasta la transferencia, ponderado por el monto cobrado.
    entrega = fecha_local(Pedido.entregado_at)
    condiciones: list[ColumnElement[bool]] = [
        Cobro.empresa_id == ctx.empresa_id,
        Cobro.estado == EstadoRegistro.REGISTRADO,
        Cobro.fecha.between(f.desde, f.hasta),
        CobroDetalle.monto > 0,
    ]
    if f.cadena_id:
        condiciones.append(Cobro.cadena_id == f.cadena_id)
    pares = db.execute(
        select(Cobro.fecha, entrega, CobroDetalle.monto)
        .join(CobroDetalle, CobroDetalle.cobro_id == Cobro.id)
        .join(Pedido, Pedido.id == CobroDetalle.pedido_id)
        .where(*condiciones)
    ).all()
    cobrado = sum((m for _c, _e, m in pares), CERO)
    dias_cobro = (
        (sum((Decimal((c - e).days) * m for c, e, m in pares), CERO) / cobrado).quantize(Decimal(1))
        if cobrado > 0
        else None
    )
    pendiente = sum((c.saldo for c in lista), CERO)
    vencido = sum((c.saldo for c in lista if c.vencimiento < al), CERO)
    diferencias = db.scalar(
        select(func.coalesce(func.sum(CobroDetalle.diferencia), 0))
        .join(Cobro, Cobro.id == CobroDetalle.cobro_id)
        .where(
            Cobro.empresa_id == ctx.empresa_id,
            Cobro.estado == EstadoRegistro.REGISTRADO,
            Cobro.fecha.between(f.desde, f.hasta),
            *([Cobro.cadena_id == f.cadena_id] if f.cadena_id else []),
        )
    )
    return Reporte(
        clave="cobranza",
        titulo="Cobranza",
        descripcion=(
            f"Saldos por cobrar al {al:%d/%m/%Y} según su antigüedad (vencen a los "
            f"{p.dias_credito} días de la entrega) y días promedio de cobro de las "
            "transferencias del período."
        ),
        filtros_texto=_filtros_texto(db, ctx, f),
        con_rentabilidad=False,
        kpis=[
            _kpi("pendiente", "Por cobrar hoy", "dinero", _dinero(pendiente)),
            _kpi("vencido", "Vencido hoy", "dinero", _dinero(vencido)),
            _kpi("cobrado", "Cobrado en el período", "dinero", _dinero(cobrado)),
            _kpi(
                "dias_cobro",
                "Días promedio de cobro",
                "entero",
                int(dias_cobro) if dias_cobro is not None else None,
            ),
            _kpi("diferencias", "Diferencias cerradas", "dinero", _dinero(diferencias)),
        ],
        tablas=[
            Tabla(
                clave="antiguedad",
                titulo="Antigüedad de saldos por cadena",
                columnas=[Columna(clave="cadena", titulo="Cadena")]
                + [Columna(clave=k, titulo=t, tipo="dinero") for k, t in TRAMOS]
                + [Columna(clave="total", titulo="Total", tipo="dinero")],
                filas=filas_cadena,
            ),
            Tabla(
                clave="pendientes",
                titulo="Pedidos por cobrar",
                columnas=[
                    Columna(clave="numero", titulo="Pedido", tipo="entero"),
                    Columna(clave="numero_oc", titulo="N.º O/C"),
                    Columna(clave="cliente", titulo="Cliente"),
                    Columna(clave="fecha", titulo="Entregado", tipo="fecha"),
                    Columna(clave="vencimiento", titulo="Vence", tipo="fecha"),
                    Columna(clave="dias", titulo="Días vencido", tipo="entero"),
                    Columna(clave="saldo", titulo="Saldo (Bs)", tipo="dinero"),
                ],
                filas=[
                    {
                        "id": str(c.pedido_id),
                        "numero": c.numero,
                        "numero_oc": c.numero_oc,
                        "cliente": " · ".join(x for x in (c.cadena, c.sucursal) if x),
                        "fecha": c.fecha,
                        "vencimiento": c.vencimiento,
                        "dias": c.dias_vencida(al),
                        "saldo": _dinero(c.saldo),
                    }
                    for c in sorted(lista, key=lambda c: c.fecha)
                ],
            ),
        ],
    )


# ================================================================ impuestos


def impuestos_reporte(db: Session, ctx: Contexto, f: Filtros) -> Reporte:
    """IVA (débito, crédito y saldo a favor) e IT por mes."""
    _validar(f)
    p = parametros.leer(db, ctx.empresa_id)
    meses = impuestos.mensual(db, ctx.empresa_id, p, f.desde, f.hasta)
    iva = sum((m.iva_pagar for m in meses), CERO)
    it = sum((m.it for m in meses), CERO)
    return Reporte(
        clave="impuestos",
        titulo="Impuestos (IVA e IT)",
        descripcion=(
            f"IVA {p.iva_pct.normalize():f} % sobre lo facturado menos el crédito fiscal de "
            "compras y gastos con factura; el sobrante pasa al mes siguiente. IT "
            f"{p.it_pct.normalize():f} % "
            "sobre lo facturado. Es una referencia: la declaración la valida el contador."
        ),
        filtros_texto=[f"De {_mes(meses[0].mes)} a {_mes(meses[-1].mes)}"] if meses else [],
        con_rentabilidad=False,
        kpis=[
            _kpi("ventas", "Facturado", "dinero", sum((m.ventas for m in meses), CERO)),
            _kpi("iva", "IVA a pagar", "dinero", iva),
            _kpi("it", "IT a pagar", "dinero", it),
            _kpi("total", "Total impuestos", "dinero", iva + it),
            _kpi(
                "saldo",
                "Crédito fiscal a favor al cierre",
                "dinero",
                meses[-1].saldo_siguiente if meses else None,
            ),
        ],
        series=[
            Serie(
                clave="impuestos",
                titulo="Impuestos por mes (Bs)",
                tipo="dinero",
                forma="barras",
                claves=[
                    Columna(clave="iva", titulo="IVA a pagar", tipo="dinero"),
                    Columna(clave="it", titulo="IT", tipo="dinero"),
                ],
                puntos=[{"etiqueta": _mes(m.mes), "iva": m.iva_pagar, "it": m.it} for m in meses],
            )
        ],
        tablas=[
            Tabla(
                clave="meses",
                titulo="Por mes",
                columnas=[
                    Columna(clave="mes", titulo="Mes"),
                    Columna(clave="ventas", titulo="Facturado", tipo="dinero"),
                    Columna(clave="iva_debito", titulo="IVA débito", tipo="dinero"),
                    Columna(clave="compras", titulo="Compras con factura", tipo="dinero"),
                    Columna(clave="gastos", titulo="Gastos con factura", tipo="dinero"),
                    Columna(clave="iva_credito", titulo="IVA crédito", tipo="dinero"),
                    Columna(clave="saldo_anterior", titulo="Saldo a favor anterior", tipo="dinero"),
                    Columna(clave="iva_pagar", titulo="IVA a pagar", tipo="dinero"),
                    Columna(clave="it", titulo="IT", tipo="dinero"),
                    Columna(clave="total", titulo="Total a pagar", tipo="dinero"),
                ],
                filas=[
                    {
                        "mes": _mes(m.mes),
                        "ventas": m.ventas,
                        "iva_debito": m.iva_debito,
                        "compras": m.compras_con_factura,
                        "gastos": m.gastos_con_factura,
                        "iva_credito": m.iva_credito,
                        "saldo_anterior": m.saldo_anterior,
                        "iva_pagar": m.iva_pagar,
                        "it": m.it,
                        "total": m.total_pagar,
                    }
                    for m in meses
                ],
            )
        ],
    )


def _mes(d: date) -> str:
    return f"{MESES_LARGOS[d.month - 1]} {d.year}"


REPORTES = {
    "resultados": resultados,
    "flujo_caja": flujo_caja,
    "cobranza": cobranza,
    "impuestos": impuestos_reporte,
}
