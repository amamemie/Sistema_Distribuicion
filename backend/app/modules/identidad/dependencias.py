"""Dependencias de FastAPI: usuario autenticado, CSRF y permisos."""

import secrets
from collections.abc import Callable
from datetime import UTC, datetime

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import NoAutenticado, SinPermiso
from app.core.security import hash_token
from app.modules.identidad.contexto import Contexto
from app.modules.identidad.models import Sesion

COOKIE_SESION = "sesion"
COOKIE_CSRF = "csrf_token"
CABECERA_CSRF = "X-CSRF-Token"
_METODOS_SEGUROS = {"GET", "HEAD", "OPTIONS"}


def datos_cliente(request: Request) -> tuple[str | None, str | None]:
    ip = request.client.host if request.client else None
    user_agent = (request.headers.get("user-agent") or "")[:300] or None
    return ip, user_agent


def sesion_actual(request: Request, db: Session = Depends(get_db)) -> Sesion:
    token = request.cookies.get(COOKIE_SESION)
    if not token:
        raise NoAutenticado("Debe iniciar sesión.")
    sesion = db.scalar(
        select(Sesion).where(
            Sesion.token_hash == hash_token(token),
            Sesion.revocada_at.is_(None),
            Sesion.expira_at > datetime.now(UTC),
        )
    )
    if sesion is None or not sesion.usuario.activo:
        raise NoAutenticado("Su sesión expiró. Inicie sesión nuevamente.")
    if request.method not in _METODOS_SEGUROS:
        enviado = request.headers.get(CABECERA_CSRF, "")
        if not secrets.compare_digest(enviado, sesion.csrf_token):
            raise SinPermiso("Solicitud rechazada por seguridad. Recargue la página.")
    return sesion


def usuario_actual(request: Request, sesion: Sesion = Depends(sesion_actual)) -> Contexto:
    ip, user_agent = datos_cliente(request)
    return Contexto(usuario=sesion.usuario, ip=ip, user_agent=user_agent)


def requiere(*permisos: str) -> Callable[[Contexto], Contexto]:
    """Exige que el usuario tenga TODOS los permisos indicados."""

    def _verificar(ctx: Contexto = Depends(usuario_actual)) -> Contexto:
        faltantes = set(permisos) - ctx.usuario.permisos
        if faltantes:
            raise SinPermiso("No tiene permiso para realizar esta acción.")
        return ctx

    return _verificar


def requiere_alguno(*permisos: str) -> Callable[[Contexto], Contexto]:
    """Exige que el usuario tenga AL MENOS UNO de los permisos indicados."""

    def _verificar(ctx: Contexto = Depends(usuario_actual)) -> Contexto:
        if not set(permisos) & ctx.usuario.permisos:
            raise SinPermiso("No tiene permiso para realizar esta acción.")
        return ctx

    return _verificar
