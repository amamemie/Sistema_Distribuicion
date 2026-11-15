"""Reglas que generan las alertas (spec 3.5 y 4.4).

`evaluar` corre cada pocos minutos (Celery beat) y es idempotente: cada condición tiene una clave;
si ya hay una alerta activa con esa clave solo se actualiza. Las alertas de estado se resuelven
solas cuando la condición desaparece; las de evento quedan hasta que alguien las atiende y no se
repiten.
"""

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from statistics import median
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.tiempo import ahora, hoy
from app.modules.alertas import dominio, parametros, reposicion
from app.modules.alertas.models import Alerta, Confianza, EstadoAlerta, Severidad
from app.modules.alertas.notificadores import notificar
from app.modules.catalogo.models import Producto
from app.modules.compras.models import Compra, CompraLinea, EstadoCompra
from app.modules.inventario.dominio import formatear_cantidad as cant
from app.modules.inventario.models import (
    Ajuste,
    ConteoFisico,
    ConteoLinea,
    EstadoAjuste,
    EstadoConteo,
    Lote,
    MotivoAjuste,
    Movimiento,
    StockLote,
    StockUbicacion,
    TipoMovimiento,
)
from app.modules.organizacion.models import Ubicacion
from app.modules.pedidos.models import EstadoPedido, Pedido, PedidoLinea

CERO = Decimal(0)
VENDIDOS = (EstadoPedido.ALISTADO, EstadoPedido.ENTREGADO)
CONFIRMADOS = (EstadoPedido.CONFIRMADO, EstadoPedido.ALISTADO, EstadoPedido.ENTREGADO)
VENTANA_EVENTOS = timedelta(days=30)  # las reglas de evento miran lo ocurrido en este lapso


@dataclass
class AlertaNueva:
    tipo: str
    severidad: Severidad
    clave: str
    titulo: str
    mensaje: str
    permiso: str
    enlace: str | None = None
    ubicacion_id: uuid.UUID | None = None
    producto_id: uuid.UUID | None = None
    datos: dict[str, Any] = field(default_factory=dict)
    auto_resolver: bool = True


# Tipos con resolución automática: si la regla no la vuelve a encontrar, se resuelve.
TIPOS_DE_ESTADO = {
    "quiebre",
    "quiebre_global",
    "stock_bajo",
    "sobre_stock",
    "pedido_sin_stock",
    "lote_vencido",
    "lote_por_vencer",
    "sin_movimiento",
    "oc_duplicada",
}


def _unidades(producto: Producto) -> str:
    return "unidades" if producto.unidad_base == "unidad" else producto.unidad_base


def _dias(valor: Decimal | None) -> str:
    return str(int(valor)) if valor is not None else "?"


def _mediana(valores: list[float]) -> Decimal:
    return Decimal(str(median(valores))).quantize(Decimal("0.01")).normalize()


def _bs(valor: Decimal) -> str:
    return f"Bs {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ================================================================ stock


def _stock(plan: reposicion.Planificacion, p: parametros.Parametros) -> list[AlertaNueva]:
    alertas: list[AlertaNueva] = []
    por_producto: dict[uuid.UUID, list[reposicion.FilaPlan]] = defaultdict(list)
    for f in plan.todas():
        por_producto[f.producto.id].append(f)
        prod, ub = f.producto, f.ubicacion
        es_suc = ub.tipo.value == "SUCURSAL"
        accion = (
            f"Reponer desde {f.origen.nombre}."
            if es_suc and f.origen
            else "Transferir desde un depósito."
            if es_suc
            else f"Comprar a {f.proveedor.nombre}."
            if f.proveedor
            else "Comprar al proveedor."
        )
        enlace = "/reposicion?tab=" + ("transferencias" if es_suc else "compras")
        base: dict[str, Any] = {
            "ubicacion_id": ub.id,
            "producto_id": prod.id,
            "permiso": "inventario.ver",
            "enlace": enlace,
        }
        datos = {
            "disponible": str(f.disponible),
            "punto_reorden": str(f.plan.punto_reorden),
            "cobertura_dias": str(f.plan.cobertura_dias)
            if f.plan.cobertura_dias is not None
            else None,
        }
        if f.con_demanda and f.disponible <= 0:
            alertas.append(
                AlertaNueva(
                    tipo="quiebre",
                    severidad=Severidad.CRITICA,
                    clave=f"quiebre:{ub.id}:{prod.id}",
                    titulo=f"Sin stock: {prod.nombre}",
                    mensaje=(
                        f"{ub.nombre} no tiene unidades disponibles de «{prod.nombre}». {accion}"
                    ),
                    datos=datos,
                    **base,
                )
            )
        elif f.con_demanda and f.disponible <= f.plan.punto_reorden:
            alcance = (
                f" (alcanza para ~{_dias(f.plan.cobertura_dias)} días)"
                if f.plan.cobertura_dias is not None
                else ""
            )
            alertas.append(
                AlertaNueva(
                    tipo="stock_bajo",
                    severidad=Severidad.AVISO,
                    clave=f"stock_bajo:{ub.id}:{prod.id}",
                    titulo=f"Stock bajo: {prod.nombre}",
                    mensaje=(
                        f"{ub.nombre}: quedan {cant(f.disponible)} {_unidades(prod)}{alcance}; "
                        f"conviene reponer al bajar de {cant(f.plan.punto_reorden)}. {accion}"
                    ),
                    datos=datos,
                    **base,
                )
            )
        else:
            limite_dias = (
                p.cobertura_sucursal_dias if es_suc else p.cobertura_deposito_dias
            ) * p.sobre_stock_veces
            excede_max = f.maximo is not None and f.fisico > f.maximo
            # Con poco historial (confianza baja) la cobertura es poco fiable: no se avisa.
            excede_dias = (
                f.maximo is None
                and f.confianza != Confianza.BAJA
                and f.demanda_semanal > 0
                and f.plan.cobertura_dias is not None
                and f.plan.cobertura_dias > Decimal(str(limite_dias))
            )
            if excede_max or excede_dias:
                detalle = (
                    f"supera el máximo de {cant(f.maximo)}"
                    if excede_max and f.maximo is not None
                    else f"alcanza para ~{_dias(f.plan.cobertura_dias)} días al ritmo de venta "
                    "actual"
                )
                alertas.append(
                    AlertaNueva(
                        tipo="sobre_stock",
                        severidad=Severidad.INFO,
                        clave=f"sobre_stock:{ub.id}:{prod.id}",
                        titulo=f"Sobre-stock: {prod.nombre}",
                        mensaje=f"{ub.nombre}: {cant(f.fisico)} {_unidades(prod)}, {detalle}.",
                        datos=datos,
                        **base,
                    )
                )
    for prod_id, filas in por_producto.items():
        if any(f.con_demanda for f in filas) and sum((f.disponible for f in filas), CERO) <= 0:
            nombre = filas[0].producto.nombre
            alertas.append(
                AlertaNueva(
                    tipo="quiebre_global",
                    severidad=Severidad.CRITICA,
                    clave=f"quiebre_global:{prod_id}",
                    titulo=f"Agotado en toda la empresa: {nombre}",
                    mensaje=(
                        f"No hay unidades disponibles de «{nombre}» en ninguna ubicación. "
                        "Hay que comprar."
                    ),
                    permiso="inventario.ver",
                    enlace="/reposicion?tab=compras",
                    producto_id=prod_id,
                )
            )
    return alertas


def _pedidos_sin_stock(db: Session, empresa_id: uuid.UUID) -> list[AlertaNueva]:
    """Pedidos confirmados que no se podrán alistar: el stock vigente no alcanza (p. ej. un
    lote reservado venció)."""
    pedidos = defaultdict(list)
    for ub, prod, nombre, numero, cantidad in db.execute(
        select(
            Pedido.ubicacion_id,
            Producto.id,
            Producto.nombre,
            Pedido.numero,
            PedidoLinea.cantidad_confirmada,
        )
        .join(PedidoLinea, PedidoLinea.pedido_id == Pedido.id)
        .join(Producto, Producto.id == PedidoLinea.producto_id)
        .where(
            Pedido.empresa_id == empresa_id,
            Pedido.estado == EstadoPedido.CONFIRMADO,
            PedidoLinea.cantidad_confirmada > 0,
        )
    ):
        pedidos[(ub, prod, nombre)].append((numero, cantidad))
    if not pedidos:
        return []
    vigente = dict(
        ((ub, prod), cantidad)
        for ub, prod, cantidad in db.execute(
            select(StockLote.ubicacion_id, StockLote.producto_id, func.sum(StockLote.cantidad))
            .join(Lote, Lote.id == StockLote.lote_id)
            .where(
                Lote.empresa_id == empresa_id,
                (Lote.vencimiento.is_(None)) | (Lote.vencimiento >= hoy()),
            )
            .group_by(StockLote.ubicacion_id, StockLote.producto_id)
        )
    )
    alertas = []
    for (ub, prod, nombre), lista in pedidos.items():
        necesario = sum((c for _, c in lista), CERO)
        hay = vigente.get((ub, prod)) or CERO
        if hay < necesario:
            numeros = ", ".join(f"#{n}" for n, _ in sorted(lista))
            alertas.append(
                AlertaNueva(
                    tipo="pedido_sin_stock",
                    severidad=Severidad.CRITICA,
                    clave=f"pedido_sin_stock:{ub}:{prod}",
                    titulo=f"Pedidos sin stock para alistar: {nombre}",
                    mensaje=(
                        f"Los pedidos confirmados {numeros} necesitan {cant(necesario)} de "
                        f"«{nombre}», "
                        f"pero hay {cant(hay)} vigentes en la sucursal."
                    ),
                    permiso="pedidos.alistar",
                    enlace="/pedidos",
                    ubicacion_id=ub,
                    producto_id=prod,
                )
            )
    return alertas


def _lotes(db: Session, empresa_id: uuid.UUID, p: parametros.Parametros) -> list[AlertaNueva]:
    limite = hoy() + timedelta(days=p.dias_aviso_vencimiento)
    alertas = []
    for ub_id, ub_nombre, lote_id, codigo, vence, prod_id, prod_nombre, cantidad in db.execute(
        select(
            Ubicacion.id,
            Ubicacion.nombre,
            Lote.id,
            Lote.codigo,
            Lote.vencimiento,
            Producto.id,
            Producto.nombre,
            StockLote.cantidad,
        )
        .join(Lote, Lote.id == StockLote.lote_id)
        .join(Producto, Producto.id == StockLote.producto_id)
        .join(Ubicacion, Ubicacion.id == StockLote.ubicacion_id)
        .where(Lote.empresa_id == empresa_id, StockLote.cantidad > 0, Lote.vencimiento <= limite)
    ):
        if vence is None:
            continue
        vencido = vence < hoy()
        dias = (vence - hoy()).days
        nombre_lote = f"lote {codigo}" if codigo else "un lote"
        alertas.append(
            AlertaNueva(
                tipo="lote_vencido" if vencido else "lote_por_vencer",
                severidad=Severidad.CRITICA if vencido else Severidad.AVISO,
                clave=f"lote:{ub_id}:{lote_id}:{'vencido' if vencido else 'por_vencer'}",
                titulo=f"{'Lote vencido' if vencido else 'Lote por vencer'}: {prod_nombre}",
                mensaje=(
                    f"{ub_nombre}: {cant(cantidad)} unidades de «{prod_nombre}» ({nombre_lote}) "
                    + (
                        f"vencieron el {vence:%d/%m/%Y}. Dé de baja con un ajuste por vencimiento."
                        if vencido
                        else f"vencen el {vence:%d/%m/%Y} (en {dias} días). Conviene venderlas "
                        "primero."
                    )
                ),
                permiso="inventario.ver",
                enlace=f"/inventario/kardex/{prod_id}",
                ubicacion_id=ub_id,
                producto_id=prod_id,
            )
        )
    return alertas


def sin_movimiento(
    db: Session, empresa_id: uuid.UUID, dias: int
) -> list[tuple[Ubicacion, Producto, Decimal, Decimal, Any]]:
    """Stock sin salidas (ventas ni transferencias) en `dias`. Lo recién ingresado no cuenta:
    se mide desde la última salida o, si nunca salió, desde el primer ingreso (T-18)."""
    referencia = (
        select(
            Movimiento.ubicacion_id,
            Movimiento.producto_id,
            func.coalesce(
                func.max(Movimiento.fecha).filter(
                    Movimiento.tipo.in_((TipoMovimiento.VENTA, TipoMovimiento.TRANSFERENCIA_SALIDA))
                ),
                func.min(Movimiento.fecha),
            ).label("desde"),
        )
        .where(Movimiento.empresa_id == empresa_id)
        .group_by(Movimiento.ubicacion_id, Movimiento.producto_id)
        .subquery()
    )
    limite = ahora() - timedelta(days=dias)
    return [
        (ub, prod, s.fisico, s.fisico * s.cpp, desde)
        for s, ub, prod, desde in db.execute(
            select(StockUbicacion, Ubicacion, Producto, referencia.c.desde)
            .join(Ubicacion, Ubicacion.id == StockUbicacion.ubicacion_id)
            .join(Producto, Producto.id == StockUbicacion.producto_id)
            .join(
                referencia,
                (referencia.c.ubicacion_id == StockUbicacion.ubicacion_id)
                & (referencia.c.producto_id == StockUbicacion.producto_id),
            )
            .where(
                StockUbicacion.empresa_id == empresa_id,
                StockUbicacion.fisico > 0,
                referencia.c.desde < limite,
            )
            .order_by(referencia.c.desde)
        ).all()
    ]


def _sin_movimiento(
    db: Session, empresa_id: uuid.UUID, p: parametros.Parametros
) -> list[AlertaNueva]:
    por_ubicacion: dict[uuid.UUID, list[Any]] = defaultdict(list)
    for fila in sin_movimiento(db, empresa_id, p.dias_sin_movimiento):
        por_ubicacion[fila[0].id].append(fila)
    alertas = []
    for ub_id, filas in por_ubicacion.items():
        ub = filas[0][0]
        nombres = ", ".join(f[1].nombre for f in filas[:3]) + ("…" if len(filas) > 3 else "")
        alertas.append(
            AlertaNueva(
                tipo="sin_movimiento",
                severidad=Severidad.INFO,
                clave=f"sin_movimiento:{ub_id}",
                titulo=f"Productos sin movimiento en {ub.nombre}",
                mensaje=(
                    f"{len(filas)} producto(s) con stock no tuvieron salidas en "
                    f"{p.dias_sin_movimiento} "
                    f"días: {nombres}."
                ),
                permiso="inventario.ver",
                enlace="/reportes?r=inventario",
                ubicacion_id=ub_id,
                datos={
                    "productos": len(filas),
                    "valor": str(sum((f[3] for f in filas), CERO).quantize(Decimal("0.01"))),
                },
            )
        )
    return alertas


def _oc_duplicada(db: Session, empresa_id: uuid.UUID) -> list[AlertaNueva]:
    alertas = []
    for pedido in db.scalars(
        select(Pedido).where(
            Pedido.empresa_id == empresa_id, Pedido.estado == EstadoPedido.BORRADOR
        )
    ):
        avisos = (pedido.confianza or {}).get("avisos") or []
        duplicado = next((a for a in avisos if "ya está registrada" in a), None)
        if duplicado and not pedido.numero_oc:
            alertas.append(
                AlertaNueva(
                    tipo="oc_duplicada",
                    severidad=Severidad.AVISO,
                    clave=f"oc_duplicada:{pedido.id}",
                    titulo=f"Documento repetido en el pedido #{pedido.numero}",
                    mensaje=f"{duplicado} Revise si es el mismo pedido y anule el que sobra.",
                    permiso="pedidos.escanear",
                    enlace=f"/pedidos/{pedido.id}",
                )
            )
    return alertas


# ================================================================ eventos


def _margen(db: Session, empresa_id: uuid.UUID, p: parametros.Parametros) -> list[AlertaNueva]:
    alertas = []
    for pedido in db.scalars(
        select(Pedido).where(
            Pedido.empresa_id == empresa_id,
            Pedido.estado.in_(VENDIDOS),
            Pedido.alistado_at >= ahora() - VENTANA_EVENTOS,
            Pedido.margen.is_not(None),
            Pedido.margen < Decimal(str(p.margen_minimo)),
        )
    ):
        assert pedido.margen is not None
        negativo = pedido.margen < 0
        cliente = " · ".join(x.nombre for x in (pedido.cadena, pedido.sucursal_cliente) if x)
        alertas.append(
            AlertaNueva(
                tipo="margen_negativo" if negativo else "margen_bajo",
                severidad=Severidad.CRITICA if negativo else Severidad.AVISO,
                clave=f"margen:{pedido.id}",
                titulo=f"{'Pérdida' if negativo else 'Margen bajo'} en el pedido #{pedido.numero}",
                mensaje=(
                    f"Pedido #{pedido.numero} ({cliente or 'sin cliente'}): "
                    f"margen {pedido.margen} %, "
                    f"ganancia {_bs(pedido.ganancia or CERO)} sobre {_bs(pedido.ingreso or CERO)}. "
                    f"El mínimo esperado es {p.margen_minimo:g} %."
                ),
                permiso="costos.ver",
                enlace=f"/pedidos/{pedido.id}",
                auto_resolver=False,
            )
        )
    return alertas


def _lineas_confirmadas(db: Session, empresa_id: uuid.UUID, dias: int) -> list[Any]:
    return list(
        db.execute(
            select(
                Pedido.id,
                Pedido.numero,
                Pedido.cadena_id,
                Pedido.confirmado_at,
                PedidoLinea.producto_id,
                Producto.nombre,
                PedidoLinea.cantidad_oc,
                PedidoLinea.precio_oc,
            )
            .join(PedidoLinea, PedidoLinea.pedido_id == Pedido.id)
            .join(Producto, Producto.id == PedidoLinea.producto_id)
            .where(
                Pedido.empresa_id == empresa_id,
                Pedido.estado.in_(CONFIRMADOS),
                Pedido.cadena_id.is_not(None),
                Pedido.confirmado_at >= ahora() - timedelta(days=dias),
            )
            .order_by(Pedido.confirmado_at, Pedido.numero)
        ).all()
    )


def _precios_y_cantidades(db: Session, empresa_id: uuid.UUID) -> list[AlertaNueva]:
    """Precio distinto del último para esa cadena, y cantidades o precios atípicos (4.4)."""
    alertas = []
    desde_eventos = ahora() - VENTANA_EVENTOS
    historia: dict[tuple[Any, Any], list[tuple[Decimal, Decimal]]] = defaultdict(list)
    for pid, numero, cadena, cuando, prod, nombre, cantidad, precio in _lineas_confirmadas(
        db, empresa_id, 365
    ):
        previas = historia[(cadena, prod)]
        if cuando >= desde_eventos and previas:
            ultimo = previas[-1][1]
            if precio != ultimo:
                alertas.append(
                    AlertaNueva(
                        tipo="precio_distinto",
                        severidad=Severidad.INFO,
                        clave=f"precio:{pid}:{prod}",
                        titulo=f"Precio distinto en el pedido #{numero}",
                        mensaje=(
                            f"«{nombre}» se pidió a Bs {precio.normalize():f}; la vez anterior esa "
                            f"cadena pagó Bs {ultimo.normalize():f}."
                        ),
                        permiso="pedidos.confirmar",
                        enlace=f"/pedidos/{pid}",
                        producto_id=prod,
                        auto_resolver=False,
                    )
                )
            for campo, valor, valores in (
                ("cantidad", cantidad, [float(c) for c, _ in previas]),
                ("precio", precio, [float(pr) for _, pr in previas]),
            ):
                if dominio.atipico(float(valor), valores):
                    alertas.append(
                        AlertaNueva(
                            tipo="anomalia_pedido",
                            severidad=Severidad.AVISO,
                            clave=f"anomalia_pedido:{pid}:{prod}:{campo}",
                            titulo=f"{campo.capitalize()} inusual en el pedido #{numero}",
                            mensaje=(
                                f"«{nombre}»: {campo} {cant(valor)}, muy distinta de lo "
                                "habitual para "
                                f"esa cadena (normalmente {cant(_mediana(valores))})."
                            ),
                            permiso="pedidos.confirmar",
                            enlace=f"/pedidos/{pid}",
                            producto_id=prod,
                            auto_resolver=False,
                        )
                    )
        previas.append((cantidad, precio))
    return alertas


def _compras_atipicas(db: Session, empresa_id: uuid.UUID) -> list[AlertaNueva]:
    alertas = []
    desde = hoy() - VENTANA_EVENTOS
    historia: dict[Any, list[float]] = defaultdict(list)
    for linea_id, compra_id, numero, fecha, prod, nombre, costo in db.execute(
        select(
            CompraLinea.id,
            Compra.id,
            Compra.numero,
            Compra.fecha,
            Producto.id,
            Producto.nombre,
            CompraLinea.costo_unitario_base,
        )
        .join(Compra, Compra.id == CompraLinea.compra_id)
        .join(Producto, Producto.id == CompraLinea.producto_id)
        .where(Compra.empresa_id == empresa_id, Compra.estado == EstadoCompra.REGISTRADA)
        .order_by(Compra.fecha, Compra.numero)
    ):
        previos = historia[prod]
        if fecha >= desde and dominio.atipico(float(costo), previos, minimo_historia=3):
            alertas.append(
                AlertaNueva(
                    tipo="anomalia_compra",
                    severidad=Severidad.AVISO,
                    clave=f"anomalia_compra:{linea_id}",
                    titulo=f"Precio de compra inusual: {nombre}",
                    mensaje=(
                        f"Compra #{numero}: «{nombre}» costó Bs {costo.quantize(Decimal('0.01'))} "
                        "por unidad, "
                        "muy distinto de las compras anteriores."
                    ),
                    permiso="costos.ver",
                    enlace=f"/compras/{compra_id}",
                    producto_id=prod,
                    auto_resolver=False,
                )
            )
        previos.append(float(costo))
    return alertas


def _mermas_atipicas(db: Session, empresa_id: uuid.UUID) -> list[AlertaNueva]:
    fecha = func.coalesce(Ajuste.resuelto_at, Ajuste.created_at)
    alertas = []
    historia: dict[MotivoAjuste, list[float]] = defaultdict(list)
    desde = ahora() - VENTANA_EVENTOS
    for ajuste in db.scalars(
        select(Ajuste)
        .where(
            Ajuste.empresa_id == empresa_id,
            Ajuste.estado == EstadoAjuste.APLICADO,
            Ajuste.motivo.in_((MotivoAjuste.MERMA, MotivoAjuste.ROTURA, MotivoAjuste.VENCIMIENTO)),
        )
        .order_by(fecha)
    ):
        valor = float(-ajuste.valor_total)  # pérdida en Bs (positiva)
        previos = historia[ajuste.motivo]
        cuando = ajuste.resuelto_at or ajuste.created_at
        if (
            cuando >= desde
            and valor > 0
            and dominio.atipico(valor, previos)
            and valor > max(previos, default=0)
        ):
            alertas.append(
                AlertaNueva(
                    tipo="anomalia_merma",
                    severidad=Severidad.AVISO,
                    clave=f"anomalia_merma:{ajuste.id}",
                    titulo=f"Pérdida inusual en el ajuste #{ajuste.numero}",
                    mensaje=(
                        f"{ajuste.ubicacion.nombre}: {ajuste.motivo.value.lower()} por "
                        f"{_bs(Decimal(str(valor)))}, mucho más que lo habitual."
                    ),
                    permiso="costos.ver",
                    enlace="/ajustes",
                    ubicacion_id=ajuste.ubicacion_id,
                    auto_resolver=False,
                )
            )
        previos.append(valor)
    return alertas


def _conteos(db: Session, empresa_id: uuid.UUID, p: parametros.Parametros) -> list[AlertaNueva]:
    alertas = []
    for conteo in db.scalars(
        select(ConteoFisico).where(
            ConteoFisico.empresa_id == empresa_id,
            ConteoFisico.estado == EstadoConteo.APROBADO,
            ConteoFisico.aprobado_at >= ahora() - VENTANA_EVENTOS,
        )
    ):
        grandes: list[ConteoLinea] = []
        for linea in conteo.lineas:
            if linea.cantidad_contada is None or linea.cantidad_sistema is None:
                continue
            diferencia = abs(linea.cantidad_contada - linea.cantidad_sistema)
            base = max(abs(linea.cantidad_sistema), Decimal(1))
            if diferencia >= 1 and diferencia * 100 / base >= Decimal(str(p.diferencia_conteo_pct)):
                grandes.append(linea)
        if grandes:
            detalle = "; ".join(
                f"{x.producto.nombre}: sistema {cant(x.cantidad_sistema or CERO)}, "
                f"contado {cant(x.cantidad_contada or CERO)}"
                for x in grandes[:3]
            )
            alertas.append(
                AlertaNueva(
                    tipo="conteo_diferencia",
                    severidad=Severidad.AVISO,
                    clave=f"conteo:{conteo.id}",
                    titulo=f"Diferencias grandes en el conteo #{conteo.numero}",
                    mensaje=(
                        f"{conteo.ubicacion.nombre}: {len(grandes)} producto(s) con diferencia de "
                        f"{p.diferencia_conteo_pct:g} % o más. {detalle}"
                        + ("…" if len(grandes) > 3 else "")
                    ),
                    permiso="inventario.ver",
                    enlace=f"/conteos/{conteo.id}",
                    ubicacion_id=conteo.ubicacion_id,
                    auto_resolver=False,
                )
            )
    return alertas


# ================================================================ evaluación


def evaluar(db: Session, empresa_id: uuid.UUID) -> dict[str, int]:
    """Corre todas las reglas, crea/actualiza/resuelve alertas y hace commit."""
    p = parametros.leer(db, empresa_id)
    plan = reposicion.planificar(db, empresa_id, p)
    nuevas = [
        *_stock(plan, p),
        *_pedidos_sin_stock(db, empresa_id),
        *_lotes(db, empresa_id, p),
        *_sin_movimiento(db, empresa_id, p),
        *_oc_duplicada(db, empresa_id),
        *_margen(db, empresa_id, p),
        *_precios_y_cantidades(db, empresa_id),
        *_compras_atipicas(db, empresa_id),
        *_mermas_atipicas(db, empresa_id),
        *_conteos(db, empresa_id, p),
    ]
    resultado = _aplicar(db, empresa_id, nuevas)
    return resultado


def _aplicar(db: Session, empresa_id: uuid.UUID, nuevas: list[AlertaNueva]) -> dict[str, int]:
    momento = ahora()
    activas = {
        a.clave: a
        for a in db.scalars(
            select(Alerta).where(
                Alerta.empresa_id == empresa_id, Alerta.estado == EstadoAlerta.ACTIVA
            )
        )
    }
    de_evento_vistas = set(
        db.scalars(
            select(Alerta.clave).where(
                Alerta.empresa_id == empresa_id, Alerta.auto_resolver.is_(False)
            )
        )
    )
    creadas: list[Alerta] = []
    actualizadas = resueltas = 0
    claves: set[str] = set()
    for n in nuevas:
        if n.clave in claves:
            continue
        claves.add(n.clave)
        actual = activas.get(n.clave)
        if actual is not None and actual.severidad == n.severidad:
            actual.titulo, actual.mensaje, actual.datos = n.titulo, n.mensaje[:1000], n.datos
            actual.vista_at = momento
            actualizadas += 1
            continue
        if actual is not None:
            # Cambió la gravedad: se cierra la anterior y se avisa de nuevo.
            actual.estado, actual.resuelta_at = EstadoAlerta.RESUELTA, momento
            db.flush()
        elif not n.auto_resolver and n.clave in de_evento_vistas:
            continue  # evento ya avisado (y quizá atendido): no se repite
        alerta = Alerta(
            empresa_id=empresa_id,
            tipo=n.tipo,
            severidad=n.severidad,
            clave=n.clave,
            titulo=n.titulo[:200],
            mensaje=n.mensaje[:1000],
            permiso=n.permiso,
            enlace=n.enlace,
            ubicacion_id=n.ubicacion_id,
            producto_id=n.producto_id,
            datos=n.datos,
            auto_resolver=n.auto_resolver,
            estado=EstadoAlerta.ACTIVA,
            creada_at=momento,
            vista_at=momento,
        )
        db.add(alerta)
        creadas.append(alerta)
    for clave, a in activas.items():
        if (
            a.auto_resolver
            and a.tipo in TIPOS_DE_ESTADO
            and clave not in claves
            and a.estado == EstadoAlerta.ACTIVA
        ):
            a.estado, a.resuelta_at = EstadoAlerta.RESUELTA, momento
            resueltas += 1
    db.commit()
    for alerta in creadas:
        notificar(alerta)
    return {"creadas": len(creadas), "actualizadas": actualizadas, "resueltas": resueltas}
