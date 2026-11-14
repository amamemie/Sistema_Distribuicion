import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import Conflicto, NoEncontrado
from app.modules.clientes.models import Cadena, SucursalCliente
from app.modules.clientes.schemas import (
    CadenaActualizacion,
    CadenaEntrada,
    SucursalClienteActualizacion,
    SucursalClienteEntrada,
)
from app.modules.identidad import auditoria
from app.modules.identidad.contexto import Contexto

_CAMPOS_CADENA = ("nombre", "nit", "telefono", "correo", "contacto", "activo")
_CAMPOS_SUCURSAL = ("nombre", "direccion", "telefono", "contacto", "activo")


def _foto(obj: Any, campos: tuple[str, ...]) -> dict[str, Any]:
    return {c: getattr(obj, c) for c in campos}


def _aplicar(obj: Any, cambios: dict[str, Any], campos: tuple[str, ...]) -> None:
    for campo in campos:
        if campo in cambios and (cambios[campo] is not None or campo not in ("nombre", "activo")):
            valor = cambios[campo]
            setattr(obj, campo, valor.strip() if campo == "nombre" else valor)


def listar(db: Session, ctx: Contexto) -> list[Cadena]:
    return list(
        db.scalars(
            select(Cadena).where(Cadena.empresa_id == ctx.empresa_id).order_by(Cadena.nombre)
        )
    )


def obtener(db: Session, ctx: Contexto, cadena_id: uuid.UUID) -> Cadena:
    cadena = db.get(Cadena, cadena_id)
    if cadena is None or cadena.empresa_id != ctx.empresa_id:
        raise NoEncontrado("La cadena no existe.")
    return cadena


def _nombre_cadena_libre(
    db: Session, ctx: Contexto, nombre: str, excepto: uuid.UUID | None = None
) -> None:
    consulta = select(Cadena.id).where(
        Cadena.empresa_id == ctx.empresa_id, func.lower(Cadena.nombre) == nombre.lower()
    )
    if excepto:
        consulta = consulta.where(Cadena.id != excepto)
    if db.scalar(consulta):
        raise Conflicto("Ya existe una cadena con ese nombre.")


def crear(db: Session, ctx: Contexto, datos: CadenaEntrada) -> Cadena:
    _nombre_cadena_libre(db, ctx, datos.nombre.strip())
    cadena = Cadena(empresa_id=ctx.empresa_id)
    _aplicar(cadena, datos.model_dump(), _CAMPOS_CADENA)
    db.add(cadena)
    db.flush()
    auditoria.registrar_ctx(
        db,
        ctx,
        accion="cadena.crear",
        entidad="cadena",
        entidad_id=cadena.id,
        despues=_foto(cadena, _CAMPOS_CADENA),
    )
    db.commit()
    db.refresh(cadena)
    return cadena


def actualizar(
    db: Session, ctx: Contexto, cadena_id: uuid.UUID, datos: CadenaActualizacion
) -> Cadena:
    cadena = obtener(db, ctx, cadena_id)
    antes = _foto(cadena, _CAMPOS_CADENA)
    cambios = datos.model_dump(exclude_unset=True)
    if cambios.get("nombre"):
        _nombre_cadena_libre(db, ctx, cambios["nombre"].strip(), excepto=cadena.id)
    _aplicar(cadena, cambios, _CAMPOS_CADENA)
    despues = _foto(cadena, _CAMPOS_CADENA)
    if despues != antes:
        auditoria.registrar_ctx(
            db,
            ctx,
            accion="cadena.actualizar",
            entidad="cadena",
            entidad_id=cadena.id,
            antes=antes,
            despues=despues,
        )
    db.commit()
    return cadena


def _nombre_sucursal_libre(
    db: Session, cadena_id: uuid.UUID, nombre: str, excepto: uuid.UUID | None = None
) -> None:
    consulta = select(SucursalCliente.id).where(
        SucursalCliente.cadena_id == cadena_id, func.lower(SucursalCliente.nombre) == nombre.lower()
    )
    if excepto:
        consulta = consulta.where(SucursalCliente.id != excepto)
    if db.scalar(consulta):
        raise Conflicto("La cadena ya tiene una sucursal con ese nombre.")


def crear_sucursal(
    db: Session, ctx: Contexto, cadena_id: uuid.UUID, datos: SucursalClienteEntrada
) -> SucursalCliente:
    cadena = obtener(db, ctx, cadena_id)
    _nombre_sucursal_libre(db, cadena.id, datos.nombre.strip())
    sucursal = SucursalCliente(cadena_id=cadena.id)
    _aplicar(sucursal, datos.model_dump(), _CAMPOS_SUCURSAL)
    db.add(sucursal)
    db.flush()
    auditoria.registrar_ctx(
        db,
        ctx,
        accion="sucursal_cliente.crear",
        entidad="sucursal_cliente",
        entidad_id=sucursal.id,
        despues={"cadena": cadena.nombre, **_foto(sucursal, _CAMPOS_SUCURSAL)},
    )
    db.commit()
    return sucursal


def actualizar_sucursal(
    db: Session, ctx: Contexto, sucursal_id: uuid.UUID, datos: SucursalClienteActualizacion
) -> SucursalCliente:
    sucursal = db.get(SucursalCliente, sucursal_id)
    if sucursal is None or sucursal.cadena.empresa_id != ctx.empresa_id:
        raise NoEncontrado("La sucursal de supermercado no existe.")
    antes = _foto(sucursal, _CAMPOS_SUCURSAL)
    cambios = datos.model_dump(exclude_unset=True)
    if cambios.get("nombre"):
        _nombre_sucursal_libre(
            db, sucursal.cadena_id, cambios["nombre"].strip(), excepto=sucursal.id
        )
    _aplicar(sucursal, cambios, _CAMPOS_SUCURSAL)
    despues = _foto(sucursal, _CAMPOS_SUCURSAL)
    if despues != antes:
        auditoria.registrar_ctx(
            db,
            ctx,
            accion="sucursal_cliente.actualizar",
            entidad="sucursal_cliente",
            entidad_id=sucursal.id,
            antes=antes,
            despues=despues,
        )
    db.commit()
    return sucursal
