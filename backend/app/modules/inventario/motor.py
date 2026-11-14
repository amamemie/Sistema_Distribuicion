"""Motor de inventario: ÚNICO punto del sistema que modifica el stock.

Reglas:
- Toda variación de stock genera un `Movimiento` (libro inmutable).
- Antes de modificar un saldo se bloquea su fila (`SELECT … FOR UPDATE`). Para evitar
  bloqueos cruzados, los documentos con varias líneas llaman a `bloquear()` primero, que
  ordena las filas siempre de la misma manera.
- Las salidas se valoran al CPP de la ubicación; las entradas recalculan el CPP.
- Las salidas consumen lotes: el indicado, o FEFO (vence primero) y luego FIFO.
- Estas funciones NO hacen commit: lo hace el servicio que las llama.
"""

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.errors import ReglaNegocio
from app.core.tiempo import hoy
from app.modules.catalogo.models import Producto
from app.modules.identidad.contexto import Contexto
from app.modules.inventario import dominio
from app.modules.inventario.models import (
    Lote,
    Movimiento,
    StockLote,
    StockUbicacion,
    TipoMovimiento,
)
from app.modules.organizacion.models import Ubicacion

CERO = Decimal(0)


@dataclass(frozen=True)
class Origen:
    """Documento que provoca el movimiento (compra, transferencia, ajuste, pedido…)."""

    tipo: str
    id: uuid.UUID


def _stock(
    db: Session, empresa_id: uuid.UUID, ubicacion_id: uuid.UUID, producto_id: uuid.UUID
) -> StockUbicacion:
    db.execute(
        pg_insert(StockUbicacion)
        .values(
            id=uuid.uuid4(),
            empresa_id=empresa_id,
            ubicacion_id=ubicacion_id,
            producto_id=producto_id,
            fisico=CERO,
            comprometido=CERO,
            cpp=CERO,
        )
        .on_conflict_do_nothing(index_elements=["ubicacion_id", "producto_id"])
    )
    return db.scalars(
        select(StockUbicacion)
        .where(
            StockUbicacion.ubicacion_id == ubicacion_id, StockUbicacion.producto_id == producto_id
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    ).one()


def bloquear(
    db: Session, ctx: Contexto, pares: Iterable[tuple[uuid.UUID, uuid.UUID]]
) -> dict[tuple[uuid.UUID, uuid.UUID], StockUbicacion]:
    """Bloquea los saldos (ubicación, producto) en orden determinista y los devuelve."""
    return {
        (ub, prod): _stock(db, ctx.empresa_id, ub, prod)
        for ub, prod in sorted(set(pares), key=lambda p: (str(p[0]), str(p[1])))
    }


def _stock_lote(db: Session, ubicacion_id: uuid.UUID, lote: Lote) -> StockLote:
    db.execute(
        pg_insert(StockLote)
        .values(
            id=uuid.uuid4(),
            ubicacion_id=ubicacion_id,
            lote_id=lote.id,
            producto_id=lote.producto_id,
            cantidad=CERO,
        )
        .on_conflict_do_nothing(index_elements=["ubicacion_id", "lote_id"])
    )
    return db.scalars(
        select(StockLote)
        .where(StockLote.ubicacion_id == ubicacion_id, StockLote.lote_id == lote.id)
        .with_for_update(of=StockLote)
        .execution_options(populate_existing=True)
    ).one()


def nuevo_lote(
    db: Session,
    ctx: Contexto,
    *,
    producto_id: uuid.UUID,
    costo_unitario: Decimal,
    origen: Origen,
    codigo: str | None = None,
    vencimiento: object = None,
    proveedor_id: uuid.UUID | None = None,
) -> Lote:
    lote = Lote(
        id=uuid.uuid4(),
        empresa_id=ctx.empresa_id,
        producto_id=producto_id,
        codigo=codigo,
        vencimiento=vencimiento,
        costo_unitario=costo_unitario,
        proveedor_id=proveedor_id,
        origen_tipo=origen.tipo,
        origen_id=origen.id,
    )
    db.add(lote)
    db.flush()
    return lote


def entrada(
    db: Session,
    ctx: Contexto,
    *,
    tipo: TipoMovimiento,
    ubicacion_id: uuid.UUID,
    lote: Lote,
    cantidad: Decimal,
    costo_unitario: Decimal,
    origen: Origen,
    motivo: str | None = None,
    revierte_id: int | None = None,
) -> Movimiento:
    if cantidad <= 0:
        raise ValueError("La cantidad de una entrada debe ser positiva.")
    stock = _stock(db, ctx.empresa_id, ubicacion_id, lote.producto_id)
    stock.cpp = dominio.cpp_al_ingresar(stock.fisico, stock.cpp, cantidad, costo_unitario)
    stock.fisico += cantidad
    _stock_lote(db, ubicacion_id, lote).cantidad += cantidad
    movimiento = Movimiento(
        empresa_id=ctx.empresa_id,
        tipo=tipo,
        ubicacion_id=ubicacion_id,
        producto_id=lote.producto_id,
        lote_id=lote.id,
        cantidad=cantidad,
        costo_unitario=costo_unitario,
        costo_total=dominio.redondear(cantidad * costo_unitario, dominio.Q_VALOR),
        saldo_despues=stock.fisico,
        cpp_despues=stock.cpp,
        origen_tipo=origen.tipo,
        origen_id=origen.id,
        usuario_id=ctx.usuario.id,
        motivo=motivo,
        revierte_id=revierte_id,
    )
    db.add(movimiento)
    db.flush()
    return movimiento


def _asignar_lotes(
    db: Session,
    ubicacion_id: uuid.UUID,
    producto_id: uuid.UUID,
    cantidad: Decimal,
    lote_id: uuid.UUID | None,
    excluir_vencidos: bool,
) -> list[tuple[StockLote, Decimal]]:
    consulta = (
        select(StockLote)
        .join(Lote, Lote.id == StockLote.lote_id)
        .where(
            StockLote.ubicacion_id == ubicacion_id,
            StockLote.producto_id == producto_id,
            StockLote.cantidad > 0,
        )
        .order_by(Lote.vencimiento.asc().nulls_last(), Lote.fecha_ingreso, Lote.id)
        .with_for_update(of=StockLote)
        .execution_options(populate_existing=True)
    )
    if lote_id is not None:
        consulta = consulta.where(StockLote.lote_id == lote_id)
    if excluir_vencidos:
        consulta = consulta.where(or_(Lote.vencimiento.is_(None), Lote.vencimiento >= hoy()))
    asignaciones: list[tuple[StockLote, Decimal]] = []
    pendiente = cantidad
    for stock_lote in db.scalars(consulta):
        tomar = min(pendiente, stock_lote.cantidad)
        asignaciones.append((stock_lote, tomar))
        pendiente -= tomar
        if pendiente == 0:
            break
    if pendiente > 0:
        if lote_id is not None:
            raise ReglaNegocio("El lote elegido no tiene stock suficiente en esa ubicación.")
        if excluir_vencidos:
            raise ReglaNegocio(
                "No hay stock suficiente en lotes vigentes (hay unidades vencidas que no se "
                "pueden despachar)."
            )
        raise ReglaNegocio("El stock por lotes no coincide con el saldo. Ejecute la verificación.")
    return asignaciones


def _mensaje_insuficiente(
    db: Session,
    ubicacion_id: uuid.UUID,
    producto_id: uuid.UUID,
    disponible: Decimal,
    pedido: Decimal,
) -> str:
    producto = db.get(Producto, producto_id)
    ubicacion = db.get(Ubicacion, ubicacion_id)
    unidad = producto.unidad_base if producto else ""
    return (
        f"Stock insuficiente de «{producto.nombre if producto else producto_id}» en "
        f"«{ubicacion.nombre if ubicacion else ubicacion_id}»: disponible "
        f"{dominio.formatear_cantidad(disponible)} {unidad}, se necesitan "
        f"{dominio.formatear_cantidad(pedido)}."
    )


def salida(
    db: Session,
    ctx: Contexto,
    *,
    tipo: TipoMovimiento,
    ubicacion_id: uuid.UUID,
    producto_id: uuid.UUID,
    cantidad: Decimal,
    origen: Origen,
    lote_id: uuid.UUID | None = None,
    excluir_vencidos: bool = False,
    consume_reserva: bool = False,
    costo_unitario: Decimal | None = None,
    motivo: str | None = None,
    revierte_id: int | None = None,
) -> list[Movimiento]:
    """Retira stock. Devuelve un movimiento por cada lote consumido.

    - `consume_reserva`: la salida usa stock comprometido (alistado de pedidos, Fase 2).
      Si es False, solo puede usar el stock disponible (físico - comprometido).
    - `costo_unitario`: solo para anular un ingreso; si se omite se usa el CPP.
    """
    if cantidad <= 0:
        raise ValueError("La cantidad de una salida debe ser positiva.")
    stock = _stock(db, ctx.empresa_id, ubicacion_id, producto_id)
    disponible = stock.fisico if consume_reserva else stock.fisico - stock.comprometido
    if cantidad > disponible:
        raise ReglaNegocio(
            _mensaje_insuficiente(db, ubicacion_id, producto_id, disponible, cantidad)
        )

    movimientos: list[Movimiento] = []
    for stock_lote, tomar in _asignar_lotes(
        db, ubicacion_id, producto_id, cantidad, lote_id, excluir_vencidos
    ):
        if costo_unitario is None:
            costo = stock.cpp
        else:
            costo = costo_unitario
            stock.cpp = dominio.cpp_al_retirar_a_costo(stock.fisico, stock.cpp, tomar, costo)
        stock.fisico -= tomar
        stock_lote.cantidad -= tomar
        movimiento = Movimiento(
            empresa_id=ctx.empresa_id,
            tipo=tipo,
            ubicacion_id=ubicacion_id,
            producto_id=producto_id,
            lote_id=stock_lote.lote_id,
            cantidad=-tomar,
            costo_unitario=costo,
            costo_total=dominio.redondear(-tomar * costo, dominio.Q_VALOR),
            saldo_despues=stock.fisico,
            cpp_despues=stock.cpp,
            origen_tipo=origen.tipo,
            origen_id=origen.id,
            usuario_id=ctx.usuario.id,
            motivo=motivo,
            revierte_id=revierte_id,
        )
        db.add(movimiento)
        movimientos.append(movimiento)
    db.flush()
    return movimientos


def revertir(db: Session, ctx: Contexto, origen: Origen, motivo: str) -> list[Movimiento]:
    """Anula todos los movimientos de un documento con movimientos de signo contrario.

    Cada reverso usa el mismo lote y el mismo costo unitario que el movimiento original.
    Falla si alguna unidad ingresada ya no está disponible (fue vendida o transferida).
    """
    originales = list(
        db.scalars(
            select(Movimiento)
            .where(
                Movimiento.origen_tipo == origen.tipo,
                Movimiento.origen_id == origen.id,
                Movimiento.revierte_id.is_(None),
                Movimiento.tipo != TipoMovimiento.ANULACION,
            )
            .order_by(Movimiento.id)
        )
    )
    bloquear(db, ctx, ((m.ubicacion_id, m.producto_id) for m in originales))
    reversos: list[Movimiento] = []
    for m in reversed(originales):
        if m.cantidad > 0:
            reversos += salida(
                db,
                ctx,
                tipo=TipoMovimiento.ANULACION,
                ubicacion_id=m.ubicacion_id,
                producto_id=m.producto_id,
                cantidad=m.cantidad,
                origen=origen,
                lote_id=m.lote_id,
                costo_unitario=m.costo_unitario,
                motivo=motivo,
                revierte_id=m.id,
            )
        else:
            lote = db.get(Lote, m.lote_id)
            assert lote is not None
            reversos.append(
                entrada(
                    db,
                    ctx,
                    tipo=TipoMovimiento.ANULACION,
                    ubicacion_id=m.ubicacion_id,
                    lote=lote,
                    cantidad=-m.cantidad,
                    costo_unitario=m.costo_unitario,
                    origen=origen,
                    motivo=motivo,
                    revierte_id=m.id,
                )
            )
    return reversos
