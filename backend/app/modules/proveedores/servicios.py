import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import Conflicto, NoEncontrado, ReglaNegocio
from app.modules.catalogo.models import Producto
from app.modules.identidad import auditoria
from app.modules.identidad.contexto import Contexto
from app.modules.proveedores.models import Proveedor
from app.modules.proveedores.schemas import ProveedorActualizacion, ProveedorEntrada

_CAMPOS = ("nombre", "nit", "telefono", "correo", "direccion", "contacto", "dias_entrega")


def _foto(p: Proveedor) -> dict[str, Any]:
    datos: dict[str, Any] = {c: getattr(p, c) for c in _CAMPOS}
    datos["activo"] = p.activo
    datos["productos"] = sorted(x.sku for x in p.productos)
    return datos


def listar(db: Session, ctx: Contexto) -> list[Proveedor]:
    return list(
        db.scalars(
            select(Proveedor)
            .where(Proveedor.empresa_id == ctx.empresa_id)
            .order_by(Proveedor.nombre)
        )
    )


def obtener(db: Session, ctx: Contexto, proveedor_id: uuid.UUID) -> Proveedor:
    proveedor = db.get(Proveedor, proveedor_id)
    if proveedor is None or proveedor.empresa_id != ctx.empresa_id:
        raise NoEncontrado("El proveedor no existe.")
    return proveedor


def operable(db: Session, ctx: Contexto, proveedor_id: uuid.UUID) -> Proveedor:
    proveedor = obtener(db, ctx, proveedor_id)
    if not proveedor.activo:
        raise ReglaNegocio(f"El proveedor «{proveedor.nombre}» está desactivado.")
    return proveedor


def _nombre_libre(
    db: Session, ctx: Contexto, nombre: str, excepto: uuid.UUID | None = None
) -> None:
    consulta = select(Proveedor.id).where(
        Proveedor.empresa_id == ctx.empresa_id, func.lower(Proveedor.nombre) == nombre.lower()
    )
    if excepto:
        consulta = consulta.where(Proveedor.id != excepto)
    if db.scalar(consulta):
        raise Conflicto("Ya existe un proveedor con ese nombre.")


def _productos(db: Session, ctx: Contexto, ids: list[uuid.UUID]) -> list[Producto]:
    if not ids:
        return []
    productos = list(
        db.scalars(
            select(Producto).where(Producto.id.in_(ids), Producto.empresa_id == ctx.empresa_id)
        )
    )
    if len(productos) != len(set(ids)):
        raise ReglaNegocio("Uno o más productos no existen.")
    return productos


def crear(db: Session, ctx: Contexto, datos: ProveedorEntrada) -> Proveedor:
    nombre = datos.nombre.strip()
    _nombre_libre(db, ctx, nombre)
    proveedor = Proveedor(
        empresa_id=ctx.empresa_id,
        **{c: getattr(datos, c) for c in _CAMPOS if c != "nombre"},
        nombre=nombre,
        productos=_productos(db, ctx, datos.producto_ids),
    )
    db.add(proveedor)
    db.flush()
    auditoria.registrar_ctx(
        db,
        ctx,
        accion="proveedor.crear",
        entidad="proveedor",
        entidad_id=proveedor.id,
        despues=_foto(proveedor),
    )
    db.commit()
    return proveedor


def actualizar(
    db: Session, ctx: Contexto, proveedor_id: uuid.UUID, datos: ProveedorActualizacion
) -> Proveedor:
    proveedor = obtener(db, ctx, proveedor_id)
    antes = _foto(proveedor)
    cambios = datos.model_dump(exclude_unset=True)
    if cambios.get("nombre"):
        cambios["nombre"] = cambios["nombre"].strip()
        _nombre_libre(db, ctx, cambios["nombre"], excepto=proveedor.id)
    for campo in _CAMPOS:
        if campo in cambios and (cambios[campo] is not None or campo != "nombre"):
            setattr(proveedor, campo, cambios[campo])
    if cambios.get("activo") is not None:
        proveedor.activo = cambios["activo"]
    if datos.producto_ids is not None:
        proveedor.productos = _productos(db, ctx, datos.producto_ids)
    despues = _foto(proveedor)
    if despues != antes:
        auditoria.registrar_ctx(
            db,
            ctx,
            accion="proveedor.actualizar",
            entidad="proveedor",
            entidad_id=proveedor.id,
            antes=antes,
            despues=despues,
        )
    db.commit()
    return proveedor
