"""Pronóstico de demanda por sucursal y producto, a partir de lo vendido (pedidos alistados).

La demanda de un depósito no se pronostica aparte: es la suma de la de las sucursales que
abastece (ver `reposicion.py`), así las reposiciones iniciales no se confunden con ventas.
"""

import math
import uuid
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.tiempo import ahora, hoy
from app.core.tiempo import fecha_local as _fecha_local
from app.modules.alertas import dominio
from app.modules.alertas.models import Pronostico
from app.modules.inventario.models import Movimiento
from app.modules.organizacion.models import TipoUbicacion, Ubicacion
from app.modules.pedidos.models import EstadoPedido, Pedido, PedidoLinea

MAX_SEMANAS = 52


def series_semanales(
    db: Session, empresa_id: uuid.UUID, hasta: date | None = None
) -> dict[tuple[uuid.UUID, uuid.UUID], list[float]]:
    """Unidades vendidas por semana (bloques de 7 días que terminan `hasta`), por (sucursal,
    producto), desde que el producto tuvo stock en esa sucursal."""
    hasta = hasta or hoy()
    desde_max = hasta - timedelta(days=7 * MAX_SEMANAS - 1)
    sucursales = select(Ubicacion.id).where(
        Ubicacion.empresa_id == empresa_id,
        Ubicacion.tipo == TipoUbicacion.SUCURSAL,
        Ubicacion.activo.is_(True),
    )
    inicios = {
        (ub, prod): inicio
        for ub, prod, inicio in db.execute(
            select(
                Movimiento.ubicacion_id,
                Movimiento.producto_id,
                func.min(_fecha_local(Movimiento.fecha)),
            )
            .where(Movimiento.empresa_id == empresa_id, Movimiento.ubicacion_id.in_(sucursales))
            .group_by(Movimiento.ubicacion_id, Movimiento.producto_id)
        )
    }
    dia_venta = _fecha_local(Pedido.alistado_at)
    ventas: dict[tuple[uuid.UUID, uuid.UUID], dict[date, Decimal]] = defaultdict(dict)
    for ub, prod, dia, unidades in db.execute(
        select(
            Pedido.ubicacion_id,
            PedidoLinea.producto_id,
            dia_venta,
            func.sum(
                func.coalesce(PedidoLinea.cantidad_alistada, 0) - PedidoLinea.cantidad_devuelta
            ),
        )
        .join(PedidoLinea, PedidoLinea.pedido_id == Pedido.id)
        .where(
            Pedido.empresa_id == empresa_id,
            Pedido.estado.in_((EstadoPedido.ALISTADO, EstadoPedido.ENTREGADO)),
            PedidoLinea.producto_id.is_not(None),
            dia_venta.between(desde_max, hasta),
        )
        .group_by(Pedido.ubicacion_id, PedidoLinea.producto_id, dia_venta)
    ):
        if prod is not None:
            ventas[(ub, prod)][dia] = unidades or Decimal(0)

    resultado: dict[tuple[uuid.UUID, uuid.UUID], list[float]] = {}
    for clave in set(inicios) | set(ventas):
        inicio = max(
            min(inicios.get(clave, hasta), *ventas.get(clave, {}).keys(), hasta), desde_max
        )
        semanas = min(math.ceil(((hasta - inicio).days + 1) / 7), MAX_SEMANAS)
        serie = [0.0] * semanas
        for dia, unidades in ventas.get(clave, {}).items():
            k = (hasta - dia).days // 7  # 0 = la semana que termina hoy
            if 0 <= k < semanas:
                serie[semanas - 1 - k] += float(unidades)
        resultado[clave] = serie
    return resultado


def recalcular(db: Session, empresa_id: uuid.UUID, hasta: date | None = None) -> int:
    """Recalcula y guarda el pronóstico de cada (sucursal, producto). Devuelve cuántos."""
    momento = ahora()
    series = series_semanales(db, empresa_id, hasta)
    q = Decimal("0.001")
    for (ubicacion_id, producto_id), serie in series.items():
        r = dominio.pronosticar(serie)
        valores = {
            "calculado_at": momento,
            "metodo": r.metodo,
            "semanas": len(serie),
            "demanda_semanal": Decimal(str(r.demanda_semanal)).quantize(q),
            "desviacion_semanal": Decimal(str(r.desviacion_semanal)).quantize(q),
            "error_medio": Decimal(str(r.error_medio)).quantize(q)
            if r.error_medio is not None
            else None,
            "confianza": r.confianza.value,
            "historial": [round(x, 3) for x in serie],
        }
        db.execute(
            pg_insert(Pronostico)
            .values(
                id=uuid.uuid4(),
                empresa_id=empresa_id,
                ubicacion_id=ubicacion_id,
                producto_id=producto_id,
                **valores,
            )
            .on_conflict_do_update(
                index_elements=["empresa_id", "ubicacion_id", "producto_id"], set_=valores
            )
        )
    db.commit()
    return len(series)
