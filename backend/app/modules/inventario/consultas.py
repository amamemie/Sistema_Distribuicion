"""Consultas de solo lectura: stock, lotes, kardex y verificación del libro."""

import uuid
from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from app.core.errors import ReglaNegocio
from app.core.schemas import Pagina
from app.core.tiempo import hoy
from app.modules.catalogo import servicios as catalogo
from app.modules.catalogo.models import LimiteStock, Producto
from app.modules.identidad.contexto import Contexto
from app.modules.inventario import dominio
from app.modules.inventario.models import (
    Ajuste,
    Lote,
    Movimiento,
    StockLote,
    StockUbicacion,
    Transferencia,
)
from app.modules.inventario.schemas import (
    LoteEnStock,
    MovimientoKardex,
    Referencia,
    ResultadoVerificacion,
    StockEnUbicacion,
    StockProducto,
)
from app.modules.organizacion.models import Ubicacion

CERO = Decimal(0)


def _presentaciones(p: Producto) -> list[tuple[str, Decimal]]:
    return [(x.nombre, x.factor) for x in p.presentaciones if x.activo]


def stock(
    db: Session,
    ctx: Contexto,
    *,
    ubicacion_id: uuid.UUID | None,
    buscar: str | None,
    categoria_id: uuid.UUID | None,
    solo_con_stock: bool,
    pagina: int,
    tamano: int,
) -> Pagina[StockProducto]:
    ver_costos = ctx.puede("costos.ver")
    consulta_ubic = select(Ubicacion).where(
        Ubicacion.empresa_id == ctx.empresa_id, Ubicacion.activo.is_(True)
    )
    if ubicacion_id:
        consulta_ubic = consulta_ubic.where(Ubicacion.id == ubicacion_id)
    ubicaciones = list(db.scalars(consulta_ubic.order_by(Ubicacion.tipo, Ubicacion.nombre)))
    ids_ubic = [u.id for u in ubicaciones]

    filtros = [Producto.empresa_id == ctx.empresa_id, Producto.activo.is_(True)]
    if buscar:
        patron = f"%{buscar.strip()}%"
        filtros.append(
            Producto.nombre.ilike(patron)
            | Producto.sku.ilike(patron)
            | (Producto.codigo_barras == buscar.strip())
        )
    if categoria_id:
        filtros.append(Producto.categoria_id == categoria_id)
    if solo_con_stock:
        filtros.append(
            exists().where(
                StockUbicacion.producto_id == Producto.id,
                StockUbicacion.ubicacion_id.in_(ids_ubic),
                StockUbicacion.fisico > 0,
            )
        )
    total = db.scalar(select(func.count()).select_from(Producto).where(*filtros)) or 0
    productos = list(
        db.scalars(
            select(Producto)
            .where(*filtros)
            .order_by(Producto.nombre)
            .offset((pagina - 1) * tamano)
            .limit(tamano)
        )
    )
    ids_prod = [p.id for p in productos]
    saldos = {
        (s.producto_id, s.ubicacion_id): s
        for s in db.scalars(
            select(StockUbicacion).where(
                StockUbicacion.producto_id.in_(ids_prod), StockUbicacion.ubicacion_id.in_(ids_ubic)
            )
        )
    }
    limites = {
        (lim.producto_id, lim.ubicacion_id): lim
        for lim in db.scalars(select(LimiteStock).where(LimiteStock.producto_id.in_(ids_prod)))
    }

    filas: list[StockProducto] = []
    for p in productos:
        pres = _presentaciones(p)
        en_ubicaciones: list[StockEnUbicacion] = []
        total_fisico = total_disponible = valor_total = CERO
        for u in ubicaciones:
            s = saldos.get((p.id, u.id))
            fisico = s.fisico if s else CERO
            comprometido = s.comprometido if s else CERO
            cpp = s.cpp if s else CERO
            disponible = fisico - comprometido
            lim = limites.get((p.id, u.id))
            minimo = lim.minimo if lim else None
            valor = dominio.redondear(fisico * cpp, dominio.Q_DINERO)
            total_fisico += fisico
            total_disponible += disponible
            valor_total += valor
            en_ubicaciones.append(
                StockEnUbicacion(
                    ubicacion_id=u.id,
                    ubicacion_nombre=u.nombre,
                    ubicacion_tipo=u.tipo,
                    fisico=fisico,
                    comprometido=comprometido,
                    disponible=disponible,
                    desglose=dominio.desglose(fisico, pres, p.unidad_base),
                    minimo=minimo,
                    maximo=lim.maximo if lim else None,
                    bajo_minimo=minimo is not None and disponible < minimo,
                    cpp=cpp if ver_costos else None,
                    valor=valor if ver_costos else None,
                )
            )
        filas.append(
            StockProducto(
                producto_id=p.id,
                sku=p.sku,
                nombre=p.nombre,
                categoria=p.categoria.nombre,
                unidad_base=p.unidad_base,
                controla_vencimiento=p.controla_vencimiento,
                ubicaciones=en_ubicaciones,
                total_fisico=total_fisico,
                total_disponible=total_disponible,
                total_desglose=dominio.desglose(total_fisico, pres, p.unidad_base),
                valor_total=valor_total if ver_costos else None,
            )
        )
    return Pagina(items=filas, total=total, pagina=pagina, tamano=tamano)


def lotes(
    db: Session, ctx: Contexto, producto_id: uuid.UUID, ubicacion_id: uuid.UUID | None
) -> list[LoteEnStock]:
    catalogo.obtener_producto(db, ctx, producto_id)
    ver_costos = ctx.puede("costos.ver")
    consulta = (
        select(StockLote, Lote, Ubicacion)
        .join(Lote, Lote.id == StockLote.lote_id)
        .join(Ubicacion, Ubicacion.id == StockLote.ubicacion_id)
        .where(StockLote.producto_id == producto_id, StockLote.cantidad > 0)
        .order_by(Ubicacion.nombre, Lote.vencimiento.asc().nulls_last(), Lote.fecha_ingreso)
    )
    if ubicacion_id:
        consulta = consulta.where(StockLote.ubicacion_id == ubicacion_id)
    fecha_hoy = hoy()
    resultado = []
    for sl, lote, ubic in db.execute(consulta):
        dias = (lote.vencimiento - fecha_hoy).days if lote.vencimiento else None
        resultado.append(
            LoteEnStock(
                lote_id=lote.id,
                ubicacion_id=ubic.id,
                ubicacion_nombre=ubic.nombre,
                codigo=lote.codigo,
                vencimiento=lote.vencimiento,
                vencido=dias is not None and dias < 0,
                dias_para_vencer=dias,
                cantidad=sl.cantidad,
                fecha_ingreso=lote.fecha_ingreso,
                costo_unitario=lote.costo_unitario if ver_costos else None,
            )
        )
    return resultado


def _documentos(db: Session, movimientos: list[Movimiento]) -> dict[uuid.UUID, str]:
    from app.modules.compras.models import Compra  # evita importación circular
    from app.modules.pedidos.models import Devolucion, Pedido

    por_tipo: dict[str, set[uuid.UUID]] = defaultdict(set)
    for m in movimientos:
        por_tipo[m.origen_tipo].add(m.origen_id)
    nombres: dict[uuid.UUID, str] = {}
    modelos: dict[str, tuple[Any, str]] = {
        "COMPRA": (Compra, "Compra"),
        "TRANSFERENCIA": (Transferencia, "Transferencia"),
        "AJUSTE": (Ajuste, "Ajuste"),
        "PEDIDO": (Pedido, "Pedido"),
        "DEVOLUCION": (Devolucion, "Devolución"),
    }
    for tipo, ids in por_tipo.items():
        if tipo in modelos:
            modelo, etiqueta = modelos[tipo]
            for doc_id, numero in db.execute(
                select(modelo.id, modelo.numero).where(modelo.id.in_(ids))
            ):
                nombres[doc_id] = f"{etiqueta} #{numero}"
    return nombres


def kardex(
    db: Session,
    ctx: Contexto,
    *,
    producto_id: uuid.UUID,
    ubicacion_id: uuid.UUID | None,
    desde: date | None,
    hasta: date | None,
    pagina: int,
    tamano: int,
) -> Pagina[MovimientoKardex]:
    catalogo.obtener_producto(db, ctx, producto_id)
    if desde and hasta and desde > hasta:
        raise ReglaNegocio("La fecha inicial no puede ser posterior a la final.")
    ver_costos = ctx.puede("costos.ver")
    filtros = [Movimiento.empresa_id == ctx.empresa_id, Movimiento.producto_id == producto_id]
    if ubicacion_id:
        filtros.append(Movimiento.ubicacion_id == ubicacion_id)
    if desde:
        filtros.append(func.date(func.timezone("America/La_Paz", Movimiento.fecha)) >= desde)
    if hasta:
        filtros.append(func.date(func.timezone("America/La_Paz", Movimiento.fecha)) <= hasta)
    total = db.scalar(select(func.count()).select_from(Movimiento).where(*filtros)) or 0
    movimientos = list(
        db.scalars(
            select(Movimiento)
            .where(*filtros)
            .order_by(Movimiento.id.desc())
            .offset((pagina - 1) * tamano)
            .limit(tamano)
        )
    )
    documentos = _documentos(db, movimientos)
    items = [
        MovimientoKardex(
            id=m.id,
            fecha=m.fecha,
            tipo=m.tipo,
            ubicacion=Referencia(id=m.ubicacion.id, nombre=m.ubicacion.nombre),
            documento=documentos.get(m.origen_id, m.origen_tipo.title()),
            origen_tipo=m.origen_tipo,
            origen_id=m.origen_id,
            lote_codigo=m.lote.codigo if m.lote else None,
            entrada=m.cantidad if m.cantidad > 0 else None,
            salida=-m.cantidad if m.cantidad < 0 else None,
            saldo=m.saldo_despues,
            usuario_nombre=m.usuario.nombre_completo,
            motivo=m.motivo,
            costo_unitario=m.costo_unitario if ver_costos else None,
            costo_total=m.costo_total if ver_costos else None,
            cpp_despues=m.cpp_despues if ver_costos else None,
        )
        for m in movimientos
    ]
    return Pagina(items=items, total=total, pagina=pagina, tamano=tamano)


def verificar(db: Session, ctx: Contexto) -> ResultadoVerificacion:
    """Recalcula los saldos desde el libro de movimientos y los compara con los materializados."""
    diferencias: list[str] = []
    libro = {
        (ub, prod): cant
        for ub, prod, cant in db.execute(
            select(Movimiento.ubicacion_id, Movimiento.producto_id, func.sum(Movimiento.cantidad))
            .where(Movimiento.empresa_id == ctx.empresa_id)
            .group_by(Movimiento.ubicacion_id, Movimiento.producto_id)
        )
    }
    saldos = {
        (s.ubicacion_id, s.producto_id): s
        for s in db.scalars(
            select(StockUbicacion).where(StockUbicacion.empresa_id == ctx.empresa_id)
        )
    }
    por_lotes = {
        (ub, prod): cant
        for ub, prod, cant in db.execute(
            select(StockLote.ubicacion_id, StockLote.producto_id, func.sum(StockLote.cantidad))
            .join(Lote, Lote.id == StockLote.lote_id)
            .where(Lote.empresa_id == ctx.empresa_id)
            .group_by(StockLote.ubicacion_id, StockLote.producto_id)
        )
    }
    lotes_libro: dict[tuple[Any, Any], Decimal] = {
        (ub, lote): cant
        for ub, lote, cant in db.execute(
            select(Movimiento.ubicacion_id, Movimiento.lote_id, func.sum(Movimiento.cantidad))
            .where(Movimiento.empresa_id == ctx.empresa_id, Movimiento.lote_id.is_not(None))
            .group_by(Movimiento.ubicacion_id, Movimiento.lote_id)
        )
    }
    lotes_saldo: dict[tuple[Any, Any], Decimal] = {
        (sl.ubicacion_id, sl.lote_id): sl.cantidad
        for sl in db.scalars(
            select(StockLote)
            .join(Lote, Lote.id == StockLote.lote_id)
            .where(Lote.empresa_id == ctx.empresa_id)
        )
    }
    for clave in set(libro) | set(saldos):
        esperado = libro.get(clave, CERO)
        actual = saldos[clave].fisico if clave in saldos else CERO
        if esperado != actual:
            diferencias.append(f"Saldo {clave}: libro {esperado}, materializado {actual}")
        if por_lotes.get(clave, CERO) != actual:
            diferencias.append(f"Lotes {clave}: suma {por_lotes.get(clave, CERO)}, saldo {actual}")
    # Comprometido = lo reservado por pedidos confirmados.
    from app.modules.pedidos.servicios import reservado_por_pedidos  # evita importación circular

    reservado = reservado_por_pedidos(db, ctx.empresa_id)
    for clave in set(reservado) | {k for k, s in saldos.items() if s.comprometido}:
        esperado = reservado.get(clave, CERO)
        actual = saldos[clave].comprometido if clave in saldos else CERO
        if esperado != actual:
            diferencias.append(
                f"Comprometido {clave}: pedidos confirmados {esperado}, materializado {actual}"
            )
    for clave in set(lotes_libro) | set(lotes_saldo):
        if lotes_libro.get(clave, CERO) != lotes_saldo.get(clave, CERO):
            diferencias.append(
                f"Lote {clave}: libro {lotes_libro.get(clave, CERO)}, "
                f"materializado {lotes_saldo.get(clave, CERO)}"
            )
    return ResultadoVerificacion(
        correcto=not diferencias, saldos_revisados=len(saldos), diferencias=diferencias
    )
