import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import Conflicto, NoEncontrado, ReglaNegocio, SinPermiso
from app.modules.identidad import auditoria
from app.modules.identidad.contexto import Contexto
from app.modules.organizacion.models import Ubicacion
from app.modules.organizacion.schemas import UbicacionActualizacion, UbicacionEntrada


def _foto(u: Ubicacion) -> dict[str, Any]:
    return {
        "nombre": u.nombre,
        "tipo": u.tipo,
        "direccion": u.direccion,
        "telefono": u.telefono,
        "activo": u.activo,
    }


def obtener(db: Session, ctx: Contexto, ubicacion_id: uuid.UUID) -> Ubicacion:
    ubicacion = db.get(Ubicacion, ubicacion_id)
    if ubicacion is None or ubicacion.empresa_id != ctx.empresa_id:
        raise NoEncontrado("La ubicación no existe.")
    return ubicacion


def tiene_acceso(ctx: Contexto, ubicacion_id: uuid.UUID) -> bool:
    return ctx.puede("ubicaciones.todas") or any(
        u.id == ubicacion_id for u in ctx.usuario.ubicaciones
    )


def operable(db: Session, ctx: Contexto, ubicacion_id: uuid.UUID) -> Ubicacion:
    """Ubicación activa en la que el usuario puede registrar operaciones de inventario."""
    ubicacion = obtener(db, ctx, ubicacion_id)
    if not ubicacion.activo:
        raise ReglaNegocio(f"La ubicación «{ubicacion.nombre}» está inactiva.")
    if not tiene_acceso(ctx, ubicacion_id):
        raise SinPermiso(f"No tiene acceso a la ubicación «{ubicacion.nombre}».")
    return ubicacion


def listar(db: Session, ctx: Contexto, solo_activas: bool = False) -> list[Ubicacion]:
    consulta = select(Ubicacion).where(Ubicacion.empresa_id == ctx.empresa_id)
    if solo_activas:
        consulta = consulta.where(Ubicacion.activo.is_(True))
    return list(db.scalars(consulta.order_by(Ubicacion.tipo, Ubicacion.nombre)))


def _nombre_disponible(
    db: Session, ctx: Contexto, nombre: str, excepto: uuid.UUID | None = None
) -> None:
    consulta = select(Ubicacion.id).where(
        Ubicacion.empresa_id == ctx.empresa_id, func.lower(Ubicacion.nombre) == nombre.lower()
    )
    if excepto:
        consulta = consulta.where(Ubicacion.id != excepto)
    if db.scalar(consulta) is not None:
        raise Conflicto("Ya existe una ubicación con ese nombre.")


def crear(db: Session, ctx: Contexto, datos: UbicacionEntrada) -> Ubicacion:
    nombre = datos.nombre.strip()
    _nombre_disponible(db, ctx, nombre)
    ubicacion = Ubicacion(
        empresa_id=ctx.empresa_id,
        nombre=nombre,
        tipo=datos.tipo,
        direccion=datos.direccion,
        telefono=datos.telefono,
    )
    db.add(ubicacion)
    db.flush()
    auditoria.registrar_ctx(
        db,
        ctx,
        accion="ubicacion.crear",
        entidad="ubicacion",
        entidad_id=ubicacion.id,
        despues=_foto(ubicacion),
    )
    db.commit()
    return ubicacion


def actualizar(
    db: Session, ctx: Contexto, ubicacion_id: uuid.UUID, datos: UbicacionActualizacion
) -> Ubicacion:
    ubicacion = db.get(Ubicacion, ubicacion_id)
    if ubicacion is None or ubicacion.empresa_id != ctx.empresa_id:
        raise NoEncontrado("La ubicación no existe.")
    antes = _foto(ubicacion)
    cambios = datos.model_dump(exclude_unset=True)
    if cambios.get("nombre"):
        cambios["nombre"] = cambios["nombre"].strip()
        _nombre_disponible(db, ctx, cambios["nombre"], excepto=ubicacion.id)
    for campo, valor in cambios.items():
        if valor is not None or campo in ("direccion", "telefono"):
            setattr(ubicacion, campo, valor)
    despues = _foto(ubicacion)
    if despues != antes:
        auditoria.registrar_ctx(
            db,
            ctx,
            accion="ubicacion.actualizar",
            entidad="ubicacion",
            entidad_id=ubicacion.id,
            antes=antes,
            despues=despues,
        )
    db.commit()
    return ubicacion
