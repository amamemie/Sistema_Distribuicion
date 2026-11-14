"""Registro en la bitácora de auditoría. Se escribe en la misma transacción que el cambio."""

import uuid
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.modules.identidad.contexto import Contexto
from app.modules.identidad.models import Auditoria


def _json(valor: dict[str, Any] | None) -> dict[str, Any] | None:
    return None if valor is None else jsonable_encoder(valor)


def registrar(
    db: Session,
    *,
    accion: str,
    entidad: str,
    entidad_id: uuid.UUID | str | None = None,
    antes: dict[str, Any] | None = None,
    despues: dict[str, Any] | None = None,
    empresa_id: uuid.UUID | None = None,
    usuario_id: uuid.UUID | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
) -> None:
    db.add(
        Auditoria(
            accion=accion,
            entidad=entidad,
            entidad_id=None if entidad_id is None else str(entidad_id),
            antes=_json(antes),
            despues=_json(despues),
            empresa_id=empresa_id,
            usuario_id=usuario_id,
            ip=ip,
            user_agent=user_agent,
        )
    )


def registrar_ctx(
    db: Session,
    ctx: Contexto,
    *,
    accion: str,
    entidad: str,
    entidad_id: uuid.UUID | str | None = None,
    antes: dict[str, Any] | None = None,
    despues: dict[str, Any] | None = None,
) -> None:
    registrar(
        db,
        accion=accion,
        entidad=entidad,
        entidad_id=entidad_id,
        antes=antes,
        despues=despues,
        empresa_id=ctx.usuario.empresa_id,
        usuario_id=ctx.usuario.id,
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
