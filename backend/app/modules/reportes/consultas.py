"""Consultas de los reportes (solo lectura). Cada función devuelve un `Reporte` completo.

Criterios (ver docs/decisiones-negocio.md, T-16 a T-19):
- Una venta es un pedido ALISTADO o ENTREGADO; su fecha es la del pedido (la de la nota de
  recepción). Las cifras salen de las líneas, netas de devoluciones.
- Los costos, ganancias y valores a costo solo se incluyen con `reportes.rentabilidad`.
"""

import uuid
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import ColumnElement, and_, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ReglaNegocio, SinPermiso
from app.core.tiempo import fecha_local, hoy
from app.modules.catalogo.models import Categoria, Producto
from app.modules.clientes.models import Cadena, SucursalCliente
from app.modules.compras.models import Compra, CompraLinea, EstadoCompra
from app.modules.identidad.contexto import Contexto
from app.modules.identidad.models import Usuario
from app.modules.inventario.models import (
    Ajuste,
    AjusteLinea,
    EstadoAjuste,
    MotivoAjuste,
    Movimiento,
    StockUbicacion,
    TipoMovimiento,
)
from app.modules.organizacion.models import Ubicacion
from app.modules.pedidos.models import EstadoPedido, Lectura, Pedido, PedidoLinea
from app.modules.proveedores.models import Proveedor
from app.modules.reportes.schemas import (
    Agrupacion,
    Columna,
    Filtros,
    Kpi,
    Reporte,
    Serie,
    Tabla,
)

CERO = Decimal(0)
VENDIDOS = (EstadoPedido.ALISTADO, EstadoPedido.ENTREGADO)
MAX_DIAS = 3660  # rango máximo de un reporte (~10 años)
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
MOTIVOS = {
    MotivoAjuste.MERMA: "Merma",
    MotivoAjuste.ROTURA: "Rotura",
    MotivoAjuste.VENCIMIENTO: "Vencimiento",
    MotivoAjuste.CONTEO_FISICO: "Conteo físico",
    MotivoAjuste.CORRECCION: "Corrección",
    MotivoAjuste.OTRO: "Otro",
}


# ================================================================ utilidades


def _dinero(valor: Decimal | None) -> Decimal:
    return (valor or CERO).quantize(Decimal("0.01"))


def _margen(ganancia: Decimal, ingreso: Decimal) -> Decimal | None:
    return (ganancia * 100 / ingreso).quantize(Decimal("0.01")) if ingreso > 0 else None


def _variacion(actual: Decimal | int | None, anterior: Decimal | int | None) -> Decimal | None:
    if actual is None or anterior is None or anterior == 0:
        return None
    return ((Decimal(actual) - Decimal(anterior)) * 100 / abs(Decimal(anterior))).quantize(
        Decimal("0.1")
    )


def _kpi(clave: str, titulo: str, tipo: Any, valor: Any, anterior: Any = None) -> Kpi:
    return Kpi(
        clave=clave,
        titulo=titulo,
        tipo=tipo,
        valor=valor,
        anterior=anterior,
        variacion=_variacion(valor, anterior),
    )


_fecha_local = fecha_local  # nombre usado en este módulo


def inicio_periodo(d: date, agrupacion: Agrupacion) -> date:
    if agrupacion == Agrupacion.SEMANA:
        return d - timedelta(days=d.weekday())
    if agrupacion == Agrupacion.MES:
        return d.replace(day=1)
    if agrupacion == Agrupacion.ANIO:
        return date(d.year, 1, 1)
    return d


def periodos(desde: date, hasta: date, agrupacion: Agrupacion) -> list[date]:
    """Todos los períodos del rango (también los que no tienen ventas)."""
    resultado: list[date] = []
    actual = inicio_periodo(desde, agrupacion)
    while actual <= hasta:
        resultado.append(actual)
        if agrupacion == Agrupacion.DIA:
            actual += timedelta(days=1)
        elif agrupacion == Agrupacion.SEMANA:
            actual += timedelta(days=7)
        elif agrupacion == Agrupacion.MES:
            actual = date(actual.year + actual.month // 12, actual.month % 12 + 1, 1)
        else:
            actual = date(actual.year + 1, 1, 1)
    return resultado


def etiqueta_periodo(d: date, agrupacion: Agrupacion) -> str:
    if agrupacion == Agrupacion.SEMANA:
        return f"Sem. {d:%d/%m/%Y}"
    if agrupacion == Agrupacion.MES:
        return f"{MESES[d.month - 1]} {d.year}"
    if agrupacion == Agrupacion.ANIO:
        return str(d.year)
    return f"{d:%d/%m/%Y}"


def periodo_anterior(desde: date, hasta: date) -> tuple[date, date]:
    dias = (hasta - desde).days + 1
    return desde - timedelta(days=dias), desde - timedelta(days=1)


def _validar(f: Filtros) -> None:
    if f.hasta < f.desde:
        raise ReglaNegocio("La fecha «hasta» no puede ser anterior a «desde».")
    if (f.hasta - f.desde).days > MAX_DIAS:
        raise ReglaNegocio("El rango de fechas es demasiado grande (máximo 10 años).")


def _exigir_rentabilidad(ctx: Contexto) -> None:
    if not ctx.puede("reportes.rentabilidad"):
        raise SinPermiso("No tiene permiso para ver costos ni ganancias.")


def _filtros_texto(db: Session, ctx: Contexto, f: Filtros, *, fechas: bool = True) -> list[str]:
    textos = [f"Del {f.desde:%d/%m/%Y} al {f.hasta:%d/%m/%Y}"] if fechas else []
    for modelo, valor, titulo in (
        (Ubicacion, f.ubicacion_id, "Ubicación"),
        (Cadena, f.cadena_id, "Cadena"),
        (SucursalCliente, f.sucursal_cliente_id, "Sucursal de cliente"),
        (Categoria, f.categoria_id, "Categoría"),
        (Producto, f.producto_id, "Producto"),
    ):
        if valor:
            objeto: Any = db.get(modelo, valor)
            if objeto is None or objeto.empresa_id != ctx.empresa_id:
                raise ReglaNegocio(f"{titulo}: no existe.")
            textos.append(f"{titulo}: {objeto.nombre}")
    return textos


# ================================================================ ventas


def _condiciones_venta(
    ctx: Contexto, f: Filtros, desde: date, hasta: date, *, clientes: bool = True
) -> list[ColumnElement[bool]]:
    condiciones: list[ColumnElement[bool]] = [
        Pedido.empresa_id == ctx.empresa_id,
        Pedido.estado.in_(VENDIDOS),
        Pedido.fecha_oc.between(desde, hasta),
    ]
    if f.ubicacion_id:
        condiciones.append(Pedido.ubicacion_id == f.ubicacion_id)
    if clientes and f.cadena_id:
        condiciones.append(Pedido.cadena_id == f.cadena_id)
    if clientes and f.sucursal_cliente_id:
        condiciones.append(Pedido.sucursal_cliente_id == f.sucursal_cliente_id)
    if f.producto_id:
        condiciones.append(PedidoLinea.producto_id == f.producto_id)
    if f.categoria_id:
        condiciones.append(Producto.categoria_id == f.categoria_id)
    return condiciones


_UNIDADES = func.coalesce(PedidoLinea.cantidad_alistada, 0) - PedidoLinea.cantidad_devuelta


@dataclass
class _PedidoVendido:
    id: uuid.UUID
    numero: int
    fecha: date
    numero_oc: str | None
    cliente: str
    unidades: Decimal = CERO
    ingreso: Decimal = CERO
    costo: Decimal = CERO

    @property
    def ganancia(self) -> Decimal:
        return self.ingreso - self.costo


def _pedidos_vendidos(
    db: Session, ctx: Contexto, f: Filtros, desde: date, hasta: date
) -> list[_PedidoVendido]:
    """Totales por pedido (de sus líneas que cumplen los filtros de producto/categoría)."""
    filas = db.execute(
        select(
            Pedido.id,
            Pedido.numero,
            Pedido.fecha_oc,
            Pedido.numero_oc,
            Cadena.nombre,
            SucursalCliente.nombre,
            func.sum(_UNIDADES),
            func.sum(func.coalesce(PedidoLinea.ingreso, 0)),
            func.sum(func.coalesce(PedidoLinea.costo_total, 0)),
        )
        .join(PedidoLinea, PedidoLinea.pedido_id == Pedido.id)
        .join(Producto, Producto.id == PedidoLinea.producto_id)
        .outerjoin(Cadena, Cadena.id == Pedido.cadena_id)
        .outerjoin(SucursalCliente, SucursalCliente.id == Pedido.sucursal_cliente_id)
        .where(*_condiciones_venta(ctx, f, desde, hasta))
        .group_by(Pedido.id, Cadena.nombre, SucursalCliente.nombre)
    )
    return [
        _PedidoVendido(
            id=i,
            numero=n,
            fecha=fecha or desde,
            numero_oc=oc,
            cliente=" · ".join(x for x in (cadena, sucursal) if x) or "—",
            unidades=u or CERO,
            ingreso=ing or CERO,
            costo=cos or CERO,
        )
        for i, n, fecha, oc, cadena, sucursal, u, ing, cos in filas
    ]


@dataclass
class _Totales:
    pedidos: int = 0
    unidades: Decimal = CERO
    ingreso: Decimal = CERO
    costo: Decimal = CERO
    ids: set[uuid.UUID] = field(default_factory=set)

    def sumar(self, p: _PedidoVendido) -> None:
        self.ids.add(p.id)
        self.pedidos = len(self.ids)
        self.unidades += p.unidades
        self.ingreso += p.ingreso
        self.costo += p.costo

    @property
    def ganancia(self) -> Decimal:
        return self.ingreso - self.costo


def _totales(pedidos: Iterable[_PedidoVendido]) -> _Totales:
    t = _Totales()
    for p in pedidos:
        t.sumar(p)
    return t


COLUMNAS_PEDIDO = [
    Columna(clave="numero", titulo="Pedido", tipo="entero"),
    Columna(clave="fecha", titulo="Fecha", tipo="fecha"),
    Columna(clave="numero_oc", titulo="N.º OC"),
    Columna(clave="cliente", titulo="Cliente"),
    Columna(clave="ingreso", titulo="Ingreso", tipo="dinero"),
    Columna(clave="ganancia", titulo="Ganancia", tipo="dinero"),
    Columna(clave="margen", titulo="Margen", tipo="porcentaje"),
]


def _fila_pedido(p: _PedidoVendido) -> dict[str, Any]:
    return {
        "id": str(p.id),
        "numero": p.numero,
        "fecha": p.fecha,
        "numero_oc": p.numero_oc,
        "cliente": p.cliente,
        "ingreso": _dinero(p.ingreso),
        "ganancia": _dinero(p.ganancia),
        "margen": _margen(p.ganancia, p.ingreso),
    }


def ganancias(db: Session, ctx: Contexto, f: Filtros) -> Reporte:
    """Ingreso, costo, ganancia y margen por período, contra el período anterior."""
    _exigir_rentabilidad(ctx)
    _validar(f)
    actuales = _pedidos_vendidos(db, ctx, f, f.desde, f.hasta)
    previo_desde, previo_hasta = periodo_anterior(f.desde, f.hasta)
    t = _totales(actuales)
    a = _totales(_pedidos_vendidos(db, ctx, f, previo_desde, previo_hasta))

    por_periodo: dict[date, _Totales] = {
        p: _Totales() for p in periodos(f.desde, f.hasta, f.agrupacion)
    }
    for p in actuales:
        por_periodo[inicio_periodo(p.fecha, f.agrupacion)].sumar(p)
    filas = [
        {
            "etiqueta": etiqueta_periodo(d, f.agrupacion),
            "pedidos": x.pedidos,
            "ingreso": _dinero(x.ingreso),
            "costo": _dinero(x.costo),
            "ganancia": _dinero(x.ganancia),
            "margen": _margen(x.ganancia, x.ingreso),
        }
        for d, x in por_periodo.items()
    ]
    con_ingreso = [p for p in actuales if p.ingreso > 0]
    return Reporte(
        clave="ganancias",
        titulo="Ganancias",
        descripcion=(
            "Pedidos alistados y entregados según la fecha del pedido. Comparado con el período "
            f"anterior de igual duración ({previo_desde:%d/%m/%Y} al {previo_hasta:%d/%m/%Y})."
        ),
        filtros_texto=_filtros_texto(db, ctx, f),
        con_rentabilidad=True,
        kpis=[
            _kpi("ingreso", "Ingreso", "dinero", _dinero(t.ingreso), _dinero(a.ingreso)),
            _kpi("costo", "Costo", "dinero", _dinero(t.costo), _dinero(a.costo)),
            _kpi("ganancia", "Ganancia", "dinero", _dinero(t.ganancia), _dinero(a.ganancia)),
            _kpi(
                "margen",
                "Margen",
                "porcentaje",
                _margen(t.ganancia, t.ingreso),
                _margen(a.ganancia, a.ingreso),
            ),
            _kpi("pedidos", "Pedidos", "entero", t.pedidos, a.pedidos),
        ],
        series=[
            Serie(
                clave="ganancias",
                titulo="Ingreso, costo y ganancia",
                tipo="dinero",
                forma="linea" if len(filas) > 12 else "barras",
                claves=[
                    Columna(clave="ingreso", titulo="Ingreso", tipo="dinero"),
                    Columna(clave="costo", titulo="Costo", tipo="dinero"),
                    Columna(clave="ganancia", titulo="Ganancia", tipo="dinero"),
                ],
                puntos=filas,
            )
        ],
        tablas=[
            Tabla(
                clave="periodos",
                titulo="Por período",
                columnas=[
                    Columna(clave="etiqueta", titulo="Período"),
                    Columna(clave="pedidos", titulo="Pedidos", tipo="entero"),
                    Columna(clave="ingreso", titulo="Ingreso", tipo="dinero"),
                    Columna(clave="costo", titulo="Costo", tipo="dinero"),
                    Columna(clave="ganancia", titulo="Ganancia", tipo="dinero"),
                    Columna(clave="margen", titulo="Margen", tipo="porcentaje"),
                ],
                filas=filas,
            ),
            Tabla(
                clave="mas_caros",
                titulo="Pedidos más caros",
                columnas=COLUMNAS_PEDIDO,
                filas=[_fila_pedido(p) for p in sorted(actuales, key=lambda p: -p.ingreso)[:5]],
            ),
            Tabla(
                clave="mayor_ganancia",
                titulo="Pedidos de mayor ganancia",
                columnas=COLUMNAS_PEDIDO,
                filas=[_fila_pedido(p) for p in sorted(actuales, key=lambda p: -p.ganancia)[:5]],
            ),
            Tabla(
                clave="menor_margen",
                titulo="Pedidos de menor margen",
                columnas=COLUMNAS_PEDIDO,
                filas=[
                    _fila_pedido(p)
                    for p in sorted(con_ingreso, key=lambda p: p.ganancia / p.ingreso)[:5]
                ],
            ),
        ],
    )


# ================================================================ productos


def productos(db: Session, ctx: Contexto, f: Filtros) -> Reporte:
    """Productos más entregados (unidades y Bs) y su rentabilidad."""
    _validar(f)
    rent = ctx.puede("reportes.rentabilidad")
    filas_db = db.execute(
        select(
            Producto.id,
            Producto.sku,
            Producto.nombre,
            Producto.unidad_base,
            func.count(func.distinct(Pedido.id)),
            func.sum(_UNIDADES),
            func.sum(func.coalesce(PedidoLinea.ingreso, 0)),
            func.sum(func.coalesce(PedidoLinea.costo_total, 0)),
        )
        .join(PedidoLinea, PedidoLinea.pedido_id == Pedido.id)
        .join(Producto, Producto.id == PedidoLinea.producto_id)
        .where(*_condiciones_venta(ctx, f, f.desde, f.hasta))
        .group_by(Producto.id)
    ).all()
    filas = []
    for _, sku, nombre, unidad, pedidos, unidades, ingreso, costo in filas_db:
        fila: dict[str, Any] = {
            "sku": sku,
            "producto": nombre,
            "unidad": unidad,
            "pedidos": pedidos,
            "unidades": unidades or CERO,
            "ingreso": _dinero(ingreso),
        }
        if rent:
            fila |= {
                "costo": _dinero(costo),
                "ganancia": _dinero((ingreso or CERO) - (costo or CERO)),
                "margen": _margen((ingreso or CERO) - (costo or CERO), ingreso or CERO),
            }
        filas.append(fila)

    base = [
        Columna(clave="sku", titulo="Código"),
        Columna(clave="producto", titulo="Producto"),
        Columna(clave="pedidos", titulo="Pedidos", tipo="entero"),
        Columna(clave="unidades", titulo="Unidades", tipo="cantidad"),
        Columna(clave="ingreso", titulo="Facturación", tipo="dinero"),
    ]
    rentab = [
        Columna(clave="costo", titulo="Costo", tipo="dinero"),
        Columna(clave="ganancia", titulo="Ganancia", tipo="dinero"),
        Columna(clave="margen", titulo="Margen", tipo="porcentaje"),
    ]
    por_ingreso = sorted(filas, key=lambda x: -x["ingreso"])
    tablas = [
        Tabla(
            clave="mas_entregados",
            titulo="Más entregados (unidades)",
            columnas=base,
            filas=sorted(filas, key=lambda x: -x["unidades"])[:10],
        ),
        Tabla(
            clave="productos",
            titulo="Todos los productos vendidos",
            descripcion="Ordenados por facturación.",
            columnas=base + (rentab if rent else []),
            filas=por_ingreso,
        ),
    ]
    if rent:
        con_ingreso = [x for x in filas if x["ingreso"] > 0]
        tablas[1:1] = [
            Tabla(
                clave="mas_rentables",
                titulo="Más rentables",
                descripcion="Mayor ganancia en Bs.",
                columnas=base + rentab,
                filas=sorted(filas, key=lambda x: -x["ganancia"])[:10],
            ),
            Tabla(
                clave="menos_rentables",
                titulo="Menos rentables",
                descripcion="Menor margen.",
                columnas=base + rentab,
                filas=sorted(con_ingreso, key=lambda x: x["margen"])[:10],
            ),
        ]
    total_ingreso = sum((x["ingreso"] for x in filas), CERO)
    kpis = [
        _kpi("productos", "Productos vendidos", "entero", len(filas)),
        _kpi("unidades", "Unidades", "cantidad", sum((x["unidades"] for x in filas), CERO)),
        _kpi("ingreso", "Facturación", "dinero", total_ingreso),
    ]
    if rent:
        ganancia = sum((x["ganancia"] for x in filas), CERO)
        kpis.append(_kpi("ganancia", "Ganancia", "dinero", ganancia))
    return Reporte(
        clave="productos",
        titulo="Productos",
        descripcion=(
            "Unidades entregadas (netas de devoluciones) en pedidos alistados y entregados."
        ),
        filtros_texto=_filtros_texto(db, ctx, f),
        con_rentabilidad=rent,
        kpis=kpis,
        series=[
            Serie(
                clave="top_facturacion",
                eje="categoria",
                titulo="Top 10 por facturación",
                tipo="dinero",
                forma="barras",
                claves=[Columna(clave="ingreso", titulo="Facturación", tipo="dinero")]
                + ([Columna(clave="ganancia", titulo="Ganancia", tipo="dinero")] if rent else []),
                puntos=[
                    {"etiqueta": x["producto"], "ingreso": x["ingreso"]}
                    | ({"ganancia": x["ganancia"]} if rent else {})
                    for x in por_ingreso[:10]
                ],
            )
        ],
        tablas=tablas,
    )


# ================================================================ clientes


def clientes(db: Session, ctx: Contexto, f: Filtros) -> Reporte:
    """Ranking de cadenas y sucursales de cliente por volumen, facturación y ganancia."""
    _validar(f)
    rent = ctx.puede("reportes.rentabilidad")
    consulta = (
        select(
            Cadena.nombre,
            SucursalCliente.nombre,
            func.count(func.distinct(Pedido.id)),
            func.sum(_UNIDADES),
            func.sum(func.coalesce(PedidoLinea.ingreso, 0)),
            func.sum(func.coalesce(PedidoLinea.costo_total, 0)),
        )
        .join(PedidoLinea, PedidoLinea.pedido_id == Pedido.id)
        .join(Producto, Producto.id == PedidoLinea.producto_id)
        .join(Cadena, Cadena.id == Pedido.cadena_id)
        .outerjoin(SucursalCliente, SucursalCliente.id == Pedido.sucursal_cliente_id)
        .where(*_condiciones_venta(ctx, f, f.desde, f.hasta))
        .group_by(Cadena.nombre, SucursalCliente.nombre)
    )
    cadenas: dict[str, _Acumulado] = defaultdict(_Acumulado)
    sucursales = []
    for cadena, sucursal, pedidos, unidades, ingreso, costo in db.execute(consulta):
        sucursales.append(
            _fila_cliente(
                {"cadena": cadena, "sucursal": sucursal or "—"},
                pedidos,
                unidades,
                ingreso,
                costo,
                rent,
            )
        )
        c = cadenas[cadena]
        c.sucursales.add(sucursal)
        c.pedidos += pedidos  # cada pedido va a una sola sucursal: se pueden sumar
        c.unidades += unidades or CERO
        c.ingreso += ingreso or CERO
        c.costo += costo or CERO
    filas_cadena = [
        _fila_cliente(
            {"cadena": nombre, "sucursales": len(c.sucursales)},
            c.pedidos,
            c.unidades,
            c.ingreso,
            c.costo,
            rent,
        )
        for nombre, c in cadenas.items()
    ]
    metricas = [
        Columna(clave="pedidos", titulo="Pedidos", tipo="entero"),
        Columna(clave="unidades", titulo="Unidades", tipo="cantidad"),
        Columna(clave="ingreso", titulo="Facturación", tipo="dinero"),
    ] + (
        [
            Columna(clave="ganancia", titulo="Ganancia", tipo="dinero"),
            Columna(clave="margen", titulo="Margen", tipo="porcentaje"),
        ]
        if rent
        else []
    )
    filas_cadena.sort(key=lambda x: -x["ingreso"])
    sucursales.sort(key=lambda x: -x["ingreso"])
    return Reporte(
        clave="clientes",
        titulo="Clientes",
        descripcion="Ranking por facturación de los pedidos alistados y entregados.",
        filtros_texto=_filtros_texto(db, ctx, f),
        con_rentabilidad=rent,
        kpis=[
            _kpi("cadenas", "Cadenas", "entero", len(filas_cadena)),
            _kpi("sucursales", "Sucursales atendidas", "entero", len(sucursales)),
            _kpi("ingreso", "Facturación", "dinero", sum((x["ingreso"] for x in sucursales), CERO)),
        ],
        series=[
            Serie(
                clave="top_sucursales",
                eje="categoria",
                titulo="Top 10 sucursales por facturación",
                tipo="dinero",
                forma="barras",
                claves=[Columna(clave="ingreso", titulo="Facturación", tipo="dinero")],
                puntos=[
                    {"etiqueta": f"{x['cadena']} · {x['sucursal']}", "ingreso": x["ingreso"]}
                    for x in sucursales[:10]
                ],
            )
        ],
        tablas=[
            Tabla(
                clave="cadenas",
                titulo="Por cadena",
                columnas=[
                    Columna(clave="cadena", titulo="Cadena"),
                    Columna(clave="sucursales", titulo="Sucursales", tipo="entero"),
                    *metricas,
                ],
                filas=filas_cadena,
            ),
            Tabla(
                clave="sucursales",
                titulo="Por sucursal de cliente",
                columnas=[
                    Columna(clave="cadena", titulo="Cadena"),
                    Columna(clave="sucursal", titulo="Sucursal"),
                    *metricas,
                ],
                filas=sucursales,
            ),
        ],
    )


@dataclass
class _Acumulado:
    sucursales: set[str | None] = field(default_factory=set)
    pedidos: int = 0
    unidades: Decimal = CERO
    ingreso: Decimal = CERO
    costo: Decimal = CERO


def _fila_cliente(
    base: dict[str, Any],
    pedidos: int,
    unidades: Decimal | None,
    ingreso: Decimal | None,
    costo: Decimal | None,
    rent: bool,
) -> dict[str, Any]:
    fila = base | {
        "pedidos": pedidos,
        "unidades": unidades or CERO,
        "ingreso": _dinero(ingreso),
    }
    if rent:
        ganancia = (ingreso or CERO) - (costo or CERO)
        fila |= {"ganancia": _dinero(ganancia), "margen": _margen(ganancia, ingreso or CERO)}
    return fila


# ================================================================ inventario


def _condiciones_stock(ctx: Contexto, f: Filtros) -> list[ColumnElement[bool]]:
    condiciones: list[ColumnElement[bool]] = [StockUbicacion.empresa_id == ctx.empresa_id]
    if f.ubicacion_id:
        condiciones.append(StockUbicacion.ubicacion_id == f.ubicacion_id)
    if f.producto_id:
        condiciones.append(StockUbicacion.producto_id == f.producto_id)
    if f.categoria_id:
        condiciones.append(Producto.categoria_id == f.categoria_id)
    return condiciones


def inventario(db: Session, ctx: Contexto, f: Filtros) -> Reporte:
    """Valor del inventario a costo, rotación, días de inventario y stock inmovilizado.

    Rotación = unidades vendidas en el período ÷ stock actual; días de inventario = stock actual ÷
    venta diaria promedio del período (T-17). Sin movimiento = con stock y sin ventas ni
    transferencias de salida en los últimos N días (T-18).
    """
    _validar(f)
    rent = ctx.puede("reportes.rentabilidad")
    tablas: list[Tabla] = []
    kpis: list[Kpi] = []
    series: list[Serie] = []

    # --- valor a costo por ubicación
    por_ubicacion = db.execute(
        select(
            Ubicacion.nombre,
            Ubicacion.tipo,
            func.count(func.distinct(StockUbicacion.producto_id)).filter(StockUbicacion.fisico > 0),
            func.sum(StockUbicacion.fisico),
            func.sum(StockUbicacion.fisico * StockUbicacion.cpp),
        )
        .join(Ubicacion, Ubicacion.id == StockUbicacion.ubicacion_id)
        .join(Producto, Producto.id == StockUbicacion.producto_id)
        .where(*_condiciones_stock(ctx, f))
        .group_by(Ubicacion.id)
        .order_by(Ubicacion.tipo, Ubicacion.nombre)
    ).all()
    filas_ub = [
        {
            "ubicacion": nombre,
            "tipo": "Depósito" if tipo.value == "DEPOSITO" else "Sucursal",
            "productos": productos_con_stock,
            "unidades": unidades or CERO,
        }
        | ({"valor": _dinero(valor)} if rent else {})
        for nombre, tipo, productos_con_stock, unidades, valor in por_ubicacion
    ]
    if rent:
        total = sum((x["valor"] for x in filas_ub), CERO)
        kpis.append(_kpi("valor", "Valor del inventario a costo", "dinero", total))
        series.append(
            Serie(
                clave="valor_ubicacion",
                eje="categoria",
                titulo="Valor a costo por ubicación",
                tipo="dinero",
                forma="barras",
                claves=[Columna(clave="valor", titulo="Valor a costo", tipo="dinero")],
                puntos=[{"etiqueta": x["ubicacion"], "valor": x["valor"]} for x in filas_ub],
            )
        )
    kpis.append(
        _kpi(
            "unidades",
            "Unidades en stock",
            "cantidad",
            sum((x["unidades"] for x in filas_ub), CERO),
        )
    )
    tablas.append(
        Tabla(
            clave="valor_ubicacion",
            titulo="Inventario por ubicación",
            columnas=[
                Columna(clave="ubicacion", titulo="Ubicación"),
                Columna(clave="tipo", titulo="Tipo"),
                Columna(clave="productos", titulo="Productos con stock", tipo="entero"),
                Columna(clave="unidades", titulo="Unidades", tipo="cantidad"),
            ]
            + ([Columna(clave="valor", titulo="Valor a costo", tipo="dinero")] if rent else []),
            filas=filas_ub,
        )
    )

    # --- rotación y días de inventario por producto
    stock_actual = {
        pid: (sku, nombre, fisico or CERO, valor or CERO)
        for pid, sku, nombre, fisico, valor in db.execute(
            select(
                Producto.id,
                Producto.sku,
                Producto.nombre,
                func.sum(StockUbicacion.fisico),
                func.sum(StockUbicacion.fisico * StockUbicacion.cpp),
            )
            .join(Producto, Producto.id == StockUbicacion.producto_id)
            .where(*_condiciones_stock(ctx, f))
            .group_by(Producto.id)
        )
    }
    vendidas = dict(
        db.execute(
            select(PedidoLinea.producto_id, func.sum(_UNIDADES))
            .join(Pedido, Pedido.id == PedidoLinea.pedido_id)
            .join(Producto, Producto.id == PedidoLinea.producto_id)
            .where(*_condiciones_venta(ctx, f, f.desde, f.hasta, clientes=False))
            .group_by(PedidoLinea.producto_id)
        ).all()
    )
    dias = (f.hasta - f.desde).days + 1
    filas_rot: list[dict[str, Any]] = []
    for pid, (sku, nombre, fisico, _) in stock_actual.items():
        vendido = vendidas.get(pid) or CERO
        if fisico <= 0 and vendido <= 0:
            continue
        diaria = vendido / dias
        filas_rot.append(
            {
                "sku": sku,
                "producto": nombre,
                "stock": fisico,
                "vendidas": vendido,
                "rotacion": (vendido / fisico).quantize(Decimal("0.01")) if fisico > 0 else None,
                "dias": int((fisico / diaria).to_integral_value()) if diaria > 0 else None,
            }
        )
    # Primero los que más tardan en venderse (sin ventas al final no aporta: van primero también).
    filas_rot.sort(key=lambda x: (x["dias"] is not None, -(x["dias"] or 0)))
    tablas.append(
        Tabla(
            clave="rotacion",
            titulo="Rotación y días de inventario",
            descripcion=(
                "Rotación = unidades vendidas en el período ÷ stock actual. Días de inventario = "
                "días que alcanza el stock actual al ritmo de venta del período (vacío: sin "
                "ventas)."
            ),
            columnas=[
                Columna(clave="sku", titulo="Código"),
                Columna(clave="producto", titulo="Producto"),
                Columna(clave="stock", titulo="Stock actual", tipo="cantidad"),
                Columna(clave="vendidas", titulo="Vendidas en el período", tipo="cantidad"),
                Columna(clave="rotacion", titulo="Rotación", tipo="cantidad"),
                Columna(clave="dias", titulo="Días de inventario", tipo="entero"),
            ],
            filas=filas_rot,
        )
    )

    # --- sin movimiento
    limite = datetime.combine(
        hoy() - timedelta(days=f.dias_sin_movimiento),
        datetime.min.time(),
        tzinfo=ZoneInfo(get_settings().zona_horaria),
    )
    # Lo recién ingresado no cuenta: se mide desde la última salida o, si nunca salió, desde el
    # primer ingreso a esa ubicación (T-18).
    referencia = (
        select(
            Movimiento.ubicacion_id,
            Movimiento.producto_id,
            func.max(Movimiento.fecha)
            .filter(
                Movimiento.tipo.in_((TipoMovimiento.VENTA, TipoMovimiento.TRANSFERENCIA_SALIDA))
            )
            .label("ultima"),
            func.min(Movimiento.fecha).label("primera"),
        )
        .where(Movimiento.empresa_id == ctx.empresa_id)
        .group_by(Movimiento.ubicacion_id, Movimiento.producto_id)
        .subquery()
    )
    desde = func.coalesce(referencia.c.ultima, referencia.c.primera)
    quietos = db.execute(
        select(
            Ubicacion.nombre,
            Producto.sku,
            Producto.nombre,
            StockUbicacion.fisico,
            StockUbicacion.fisico * StockUbicacion.cpp,
            referencia.c.ultima,
            desde,
        )
        .join(Ubicacion, Ubicacion.id == StockUbicacion.ubicacion_id)
        .join(Producto, Producto.id == StockUbicacion.producto_id)
        .join(
            referencia,
            and_(
                referencia.c.ubicacion_id == StockUbicacion.ubicacion_id,
                referencia.c.producto_id == StockUbicacion.producto_id,
            ),
        )
        .where(*_condiciones_stock(ctx, f), StockUbicacion.fisico > 0, desde < limite)
        .order_by(desde, Producto.nombre)
    ).all()
    zona = ZoneInfo(get_settings().zona_horaria)
    filas_q = [
        {
            "ubicacion": ub,
            "sku": sku,
            "producto": nombre,
            "stock": fisico,
            "ultima_salida": ultima.astimezone(zona).date() if ultima else None,
            "dias": (hoy() - referencia_dia.astimezone(zona).date()).days,
        }
        | ({"valor": _dinero(valor)} if rent else {})
        for ub, sku, nombre, fisico, valor, ultima, referencia_dia in quietos
    ]
    if rent:
        kpis.append(
            _kpi(
                "inmovilizado",
                f"Inmovilizado (sin salida en {f.dias_sin_movimiento} días)",
                "dinero",
                sum((x["valor"] for x in filas_q), CERO),
            )
        )
    tablas.append(
        Tabla(
            clave="sin_movimiento",
            titulo=f"Sin movimiento en los últimos {f.dias_sin_movimiento} días",
            descripcion=(
                "Con stock y sin ventas ni transferencias de salida desde esa ubicación (lo que "
                "nunca salió se cuenta desde que ingresó)."
            ),
            columnas=[
                Columna(clave="ubicacion", titulo="Ubicación"),
                Columna(clave="sku", titulo="Código"),
                Columna(clave="producto", titulo="Producto"),
                Columna(clave="stock", titulo="Stock", tipo="cantidad"),
                Columna(clave="ultima_salida", titulo="Última salida", tipo="fecha"),
                Columna(clave="dias", titulo="Días sin movimiento", tipo="entero"),
            ]
            + ([Columna(clave="valor", titulo="Valor a costo", tipo="dinero")] if rent else []),
            filas=filas_q,
        )
    )
    textos = _filtros_texto(db, ctx, f, fechas=False)
    return Reporte(
        clave="inventario",
        titulo="Inventario",
        descripcion=(
            f"Stock al día de hoy. Ventas del {f.desde:%d/%m/%Y} al {f.hasta:%d/%m/%Y} para la "
            "rotación."
        ),
        filtros_texto=[f"Ventas del {f.desde:%d/%m/%Y} al {f.hasta:%d/%m/%Y}", *textos],
        con_rentabilidad=rent,
        kpis=kpis,
        series=series,
        tablas=tablas,
    )


# ================================================================ mermas y ajustes


def ajustes(db: Session, ctx: Contexto, f: Filtros) -> Reporte:
    """Ajustes aplicados por motivo y período (unidades y valor a costo)."""
    _validar(f)
    rent = ctx.puede("reportes.rentabilidad")
    fecha = _fecha_local(func.coalesce(Ajuste.resuelto_at, Ajuste.created_at))
    condiciones: list[ColumnElement[bool]] = [
        Ajuste.empresa_id == ctx.empresa_id,
        Ajuste.estado == EstadoAjuste.APLICADO,
        fecha.between(f.desde, f.hasta),
    ]
    if f.ubicacion_id:
        condiciones.append(Ajuste.ubicacion_id == f.ubicacion_id)
    if f.producto_id:
        condiciones.append(AjusteLinea.producto_id == f.producto_id)
    if f.categoria_id:
        condiciones.append(Producto.categoria_id == f.categoria_id)
    filas_db = db.execute(
        select(
            fecha,
            Ajuste.id,
            Ajuste.motivo,
            Producto.sku,
            Producto.nombre,
            AjusteLinea.cantidad_base,
            AjusteLinea.valor,
        )
        .join(AjusteLinea, AjusteLinea.ajuste_id == Ajuste.id)
        .join(Producto, Producto.id == AjusteLinea.producto_id)
        .where(*condiciones)
    ).all()

    por_motivo: dict[MotivoAjuste, list[Any]] = defaultdict(lambda: [set(), CERO, CERO, CERO])
    por_periodo: dict[date, dict[str, Decimal]] = {
        p: defaultdict(lambda: CERO) for p in periodos(f.desde, f.hasta, f.agrupacion)
    }
    por_producto: dict[tuple[str, str], list[Decimal]] = defaultdict(lambda: [CERO, CERO])
    for dia, ajuste_id, motivo, sku, nombre, cantidad, valor in filas_db:
        m = por_motivo[motivo]
        m[0].add(ajuste_id)
        m[1 if cantidad < 0 else 2] += abs(cantidad)
        m[3] += valor
        por_periodo[inicio_periodo(dia, f.agrupacion)][motivo.value] += -valor
        p = por_producto[(sku, nombre)]
        p[0] += cantidad
        p[1] += valor
    filas_motivo = [
        {
            "motivo": MOTIVOS[motivo],
            "ajustes": len(m[0]),
            "salidas": m[1],
            "entradas": m[2],
        }
        | ({"valor": _dinero(m[3])} if rent else {})
        for motivo, m in sorted(por_motivo.items(), key=lambda x: x[1][3])
    ]
    perdidas = -sum((m[3] for m in por_motivo.values() if m[3] < 0), CERO)
    kpis = [_kpi("ajustes", "Ajustes aplicados", "entero", sum(x["ajustes"] for x in filas_motivo))]
    series: list[Serie] = []
    if rent:
        kpis += [
            _kpi("perdidas", "Pérdidas (Bs a costo)", "dinero", _dinero(perdidas)),
            _kpi(
                "neto",
                "Efecto neto en el inventario",
                "dinero",
                _dinero(-perdidas + sum((m[3] for m in por_motivo.values() if m[3] > 0), CERO)),
            ),
        ]
        motivos_usados = [m for m in MOTIVOS if m in por_motivo]
        series.append(
            Serie(
                clave="perdidas",
                titulo="Pérdidas por motivo (Bs a costo; negativo = aumentó el stock)",
                tipo="dinero",
                forma="barras",
                claves=[
                    Columna(clave=m.value, titulo=MOTIVOS[m], tipo="dinero") for m in motivos_usados
                ],
                puntos=[
                    {"etiqueta": etiqueta_periodo(d, f.agrupacion)}
                    | {m.value: _dinero(v.get(m.value)) for m in motivos_usados}
                    for d, v in por_periodo.items()
                ],
            )
        )
    columnas_motivo = [
        Columna(clave="motivo", titulo="Motivo"),
        Columna(clave="ajustes", titulo="Ajustes", tipo="entero"),
        Columna(clave="salidas", titulo="Unidades descontadas", tipo="cantidad"),
        Columna(clave="entradas", titulo="Unidades agregadas", tipo="cantidad"),
    ] + ([Columna(clave="valor", titulo="Valor (Bs)", tipo="dinero")] if rent else [])
    filas_producto = [
        {"sku": sku, "producto": nombre, "cantidad": v[0]}
        | ({"valor": _dinero(v[1])} if rent else {})
        for (sku, nombre), v in sorted(por_producto.items(), key=lambda x: x[1][1])
    ]
    return Reporte(
        clave="ajustes",
        titulo="Mermas y ajustes",
        descripcion=(
            "Ajustes aplicados (incluidas las mermas registradas al alistar). Valores a costo: "
            "negativo = pérdida de inventario."
        ),
        filtros_texto=_filtros_texto(db, ctx, f),
        con_rentabilidad=rent,
        kpis=kpis,
        series=series,
        tablas=[
            Tabla(
                clave="motivos", titulo="Por motivo", columnas=columnas_motivo, filas=filas_motivo
            ),
            Tabla(
                clave="productos",
                titulo="Por producto",
                columnas=[
                    Columna(clave="sku", titulo="Código"),
                    Columna(clave="producto", titulo="Producto"),
                    Columna(clave="cantidad", titulo="Unidades (+/-)", tipo="cantidad"),
                ]
                + ([Columna(clave="valor", titulo="Valor (Bs)", tipo="dinero")] if rent else []),
                filas=filas_producto,
            ),
        ],
    )


# ================================================================ precios de compra


def precios_compra(db: Session, ctx: Contexto, f: Filtros) -> Reporte:
    """Historial del costo unitario de compra por producto y proveedor."""
    _exigir_rentabilidad(ctx)
    _validar(f)
    condiciones: list[ColumnElement[bool]] = [
        Compra.empresa_id == ctx.empresa_id,
        Compra.estado == EstadoCompra.REGISTRADA,
        Compra.fecha.between(f.desde, f.hasta),
    ]
    if f.ubicacion_id:
        condiciones.append(Compra.ubicacion_id == f.ubicacion_id)
    if f.producto_id:
        condiciones.append(CompraLinea.producto_id == f.producto_id)
    if f.categoria_id:
        condiciones.append(Producto.categoria_id == f.categoria_id)
    filas_db = db.execute(
        select(
            Compra.fecha,
            Compra.numero,
            Proveedor.nombre,
            Producto.sku,
            Producto.nombre,
            CompraLinea.presentacion_nombre,
            CompraLinea.cantidad,
            CompraLinea.precio_presentacion,
            CompraLinea.cantidad_base,
            CompraLinea.costo_unitario_base,
        )
        .join(CompraLinea, CompraLinea.compra_id == Compra.id)
        .join(Producto, Producto.id == CompraLinea.producto_id)
        .join(Proveedor, Proveedor.id == Compra.proveedor_id)
        .where(*condiciones)
        .order_by(Compra.fecha, Compra.numero, CompraLinea.orden)
    ).all()
    detalle: list[dict[str, Any]] = [
        {
            "fecha": fecha,
            "compra": numero,
            "proveedor": proveedor,
            "sku": sku,
            "producto": nombre,
            "presentacion": presentacion,
            "cantidad": cantidad,
            "precio_presentacion": _dinero(precio),
            "costo_unitario": costo.quantize(Decimal("0.0001")),
        }
        for (fecha, numero, proveedor, sku, nombre, presentacion, cantidad, precio, _, costo) in (
            filas_db
        )
    ]
    resumen: dict[tuple[str, str], list[Any]] = {}
    for fila, (*_, cantidad_base, costo) in zip(detalle, filas_db, strict=True):
        clave = (fila["sku"], fila["producto"])
        r = resumen.setdefault(clave, [costo, costo, CERO, CERO, costo, fila["fecha"], 0])
        r[0] = min(r[0], costo)
        r[1] = max(r[1], costo)
        r[2] += cantidad_base
        r[3] += cantidad_base * costo
        r[4], r[5] = costo, fila["fecha"]
        r[6] += 1
    filas_resumen = [
        {
            "sku": sku,
            "producto": nombre,
            "compras": r[6],
            "minimo": r[0].quantize(Decimal("0.0001")),
            "maximo": r[1].quantize(Decimal("0.0001")),
            "promedio": (r[3] / r[2]).quantize(Decimal("0.0001")) if r[2] else None,
            "ultimo": r[4].quantize(Decimal("0.0001")),
            "fecha_ultimo": r[5],
            "variacion": _variacion(r[4], r[0]) if r[0] != r[4] else Decimal(0),
        }
        for (sku, nombre), r in sorted(resumen.items(), key=lambda x: x[0][1])
    ]
    series: list[Serie] = []
    if f.producto_id and detalle:
        proveedores = sorted({x["proveedor"] for x in detalle})
        claves = {p: f"p{i}" for i, p in enumerate(proveedores)}
        puntos: dict[date, dict[str, Any]] = {}
        for x in detalle:
            punto = puntos.setdefault(x["fecha"], {"etiqueta": f"{x['fecha']:%d/%m/%Y}"})
            punto[claves[x["proveedor"]]] = x["costo_unitario"]
        series.append(
            Serie(
                clave="historial",
                titulo="Costo unitario por proveedor",
                tipo="dinero",
                forma="linea",
                claves=[Columna(clave=claves[p], titulo=p, tipo="dinero") for p in proveedores],
                puntos=list(puntos.values()),
            )
        )
    return Reporte(
        clave="precios_compra",
        titulo="Precios de compra",
        descripcion=(
            "Costo por unidad base (incluye los costos adicionales prorrateados). Elija un "
            "producto para ver el gráfico por proveedor."
        ),
        filtros_texto=_filtros_texto(db, ctx, f),
        con_rentabilidad=True,
        kpis=[
            _kpi("compras", "Líneas de compra", "entero", len(detalle)),
            _kpi("productos", "Productos comprados", "entero", len(filas_resumen)),
        ],
        series=series,
        tablas=[
            Tabla(
                clave="resumen",
                titulo="Resumen por producto",
                columnas=[
                    Columna(clave="sku", titulo="Código"),
                    Columna(clave="producto", titulo="Producto"),
                    Columna(clave="compras", titulo="Compras", tipo="entero"),
                    Columna(clave="minimo", titulo="Mínimo", tipo="dinero"),
                    Columna(clave="maximo", titulo="Máximo", tipo="dinero"),
                    Columna(clave="promedio", titulo="Promedio ponderado", tipo="dinero"),
                    Columna(clave="ultimo", titulo="Último", tipo="dinero"),
                    Columna(clave="fecha_ultimo", titulo="Fecha último", tipo="fecha"),
                    Columna(clave="variacion", titulo="Último vs. mínimo", tipo="porcentaje"),
                ],
                filas=filas_resumen,
            ),
            Tabla(
                clave="detalle",
                titulo="Detalle de compras",
                columnas=[
                    Columna(clave="fecha", titulo="Fecha", tipo="fecha"),
                    Columna(clave="compra", titulo="Compra", tipo="entero"),
                    Columna(clave="proveedor", titulo="Proveedor"),
                    Columna(clave="sku", titulo="Código"),
                    Columna(clave="producto", titulo="Producto"),
                    Columna(clave="presentacion", titulo="Presentación"),
                    Columna(clave="cantidad", titulo="Cantidad", tipo="cantidad"),
                    Columna(clave="precio_presentacion", titulo="Precio", tipo="dinero"),
                    Columna(clave="costo_unitario", titulo="Costo unitario", tipo="dinero"),
                ],
                filas=detalle,
            ),
        ],
    )


# ================================================================ usuarios y lectura automática


def usuarios(db: Session, ctx: Contexto, f: Filtros) -> Reporte:
    """Pedidos registrados, confirmados y entregados por usuario, y precisión de la lectura."""
    _validar(f)

    def contar(
        columna_usuario: Any, columna_fecha: Any, *, es_fecha: bool = False
    ) -> dict[uuid.UUID, int]:
        fecha = columna_fecha if es_fecha else _fecha_local(columna_fecha)
        condiciones = [
            Pedido.empresa_id == ctx.empresa_id,
            columna_usuario.is_not(None),
            fecha.between(f.desde, f.hasta),
        ]
        if f.ubicacion_id:
            condiciones.append(Pedido.ubicacion_id == f.ubicacion_id)
        if f.cadena_id:
            condiciones.append(Pedido.cadena_id == f.cadena_id)
        return dict(
            db.execute(
                select(columna_usuario, func.count()).where(*condiciones).group_by(columna_usuario)
            ).all()
        )

    registrados = contar(Pedido.responsable_id, Pedido.created_at)
    confirmados = contar(Pedido.confirmado_por_id, Pedido.confirmado_at)
    alistados = contar(Pedido.alistado_por_id, Pedido.alistado_at)
    entregados = contar(Pedido.entregado_por_id, Pedido.entregado_at)

    # Lecturas medidas: las que se confirmaron (se compara lo leído con lo confirmado).
    fecha_conf = _fecha_local(Pedido.confirmado_at)
    condiciones_l: list[ColumnElement[bool]] = [
        Pedido.empresa_id == ctx.empresa_id,
        Lectura.precision.is_not(None),
        fecha_conf.between(f.desde, f.hasta),
    ]
    if f.ubicacion_id:
        condiciones_l.append(Pedido.ubicacion_id == f.ubicacion_id)
    if f.cadena_id:
        condiciones_l.append(Pedido.cadena_id == f.cadena_id)
    lecturas = db.execute(
        select(fecha_conf, Pedido.responsable_id, Lectura.plantilla, Lectura.precision)
        .join(Pedido, Pedido.id == Lectura.pedido_id)
        .where(*condiciones_l)
    ).all()
    por_usuario: dict[uuid.UUID, list[Decimal]] = defaultdict(list)
    por_plantilla: dict[str, list[Decimal]] = defaultdict(list)
    por_periodo: dict[date, list[Decimal]] = {
        p: [] for p in periodos(f.desde, f.hasta, f.agrupacion)
    }
    for dia, usuario_id, plantilla, precision in lecturas:
        if precision is None:
            continue
        por_usuario[usuario_id].append(precision)
        por_plantilla[plantilla or "—"].append(precision)
        por_periodo[inicio_periodo(dia, f.agrupacion)].append(precision)

    def promedio(valores: list[Decimal]) -> Decimal | None:
        return (sum(valores, CERO) / len(valores)).quantize(Decimal("0.01")) if valores else None

    ids = set(registrados) | set(confirmados) | set(alistados) | set(entregados) | set(por_usuario)
    nombres = (
        dict(db.execute(select(Usuario.id, Usuario.nombre).where(Usuario.id.in_(ids))).all())
        if ids
        else {}
    )
    filas: list[dict[str, Any]] = sorted(
        (
            {
                "usuario": nombres.get(uid, "—"),
                "registrados": registrados.get(uid, 0),
                "confirmados": confirmados.get(uid, 0),
                "alistados": alistados.get(uid, 0),
                "entregados": entregados.get(uid, 0),
                "lecturas": len(por_usuario.get(uid, [])),
                "correccion": (
                    (100 - p).quantize(Decimal("0.01"))
                    if (p := promedio(por_usuario.get(uid, []))) is not None
                    else None
                ),
            }
            for uid in ids
        ),
        key=lambda x: (-x["registrados"], x["usuario"]),
    )
    NOMBRES_PLANTILLA = {
        "hipermaxi_recepcion": "Nota de recepción Hipermaxi",
        "hipermaxi": "OC Hipermaxi",
        "generica": "Lectura genérica",
    }
    todas = [p for valores in por_plantilla.values() for p in valores]
    return Reporte(
        clave="usuarios",
        titulo="Usuarios y lectura automática",
        descripcion=(
            "Pedidos por usuario según la fecha de cada acción. La precisión de la lectura es el % "
            "de campos que no se corrigieron antes de confirmar."
        ),
        filtros_texto=_filtros_texto(db, ctx, f),
        con_rentabilidad=ctx.puede("reportes.rentabilidad"),
        kpis=[
            _kpi("registrados", "Pedidos registrados", "entero", sum(registrados.values())),
            _kpi("entregados", "Pedidos entregados", "entero", sum(entregados.values())),
            _kpi("lecturas", "Lecturas medidas", "entero", len(todas)),
            _kpi("precision", "Precisión de la lectura", "porcentaje", promedio(todas)),
        ],
        series=[
            Serie(
                clave="precision",
                titulo="Precisión de la lectura automática",
                tipo="porcentaje",
                forma="linea",
                claves=[Columna(clave="precision", titulo="Precisión", tipo="porcentaje")],
                puntos=[
                    {"etiqueta": etiqueta_periodo(d, f.agrupacion), "precision": promedio(v)}
                    for d, v in por_periodo.items()
                ],
            )
        ],
        tablas=[
            Tabla(
                clave="usuarios",
                titulo="Rendimiento por usuario",
                columnas=[
                    Columna(clave="usuario", titulo="Usuario"),
                    Columna(clave="registrados", titulo="Registrados", tipo="entero"),
                    Columna(clave="confirmados", titulo="Confirmados", tipo="entero"),
                    Columna(clave="alistados", titulo="Alistados", tipo="entero"),
                    Columna(clave="entregados", titulo="Entregados", tipo="entero"),
                    Columna(clave="lecturas", titulo="Lecturas medidas", tipo="entero"),
                    Columna(clave="correccion", titulo="Campos corregidos", tipo="porcentaje"),
                ],
                filas=filas,
            ),
            Tabla(
                clave="plantillas",
                titulo="Precisión por formato",
                columnas=[
                    Columna(clave="formato", titulo="Formato"),
                    Columna(clave="lecturas", titulo="Lecturas", tipo="entero"),
                    Columna(clave="precision", titulo="Precisión", tipo="porcentaje"),
                ],
                filas=[
                    {
                        "formato": NOMBRES_PLANTILLA.get(nombre, nombre),
                        "lecturas": len(v),
                        "precision": promedio(v),
                    }
                    for nombre, v in sorted(por_plantilla.items())
                ],
            ),
        ],
    )


REPORTES = {
    "ganancias": ganancias,
    "productos": productos,
    "clientes": clientes,
    "inventario": inventario,
    "ajustes": ajustes,
    "precios_compra": precios_compra,
    "usuarios": usuarios,
}
