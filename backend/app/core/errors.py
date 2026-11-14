"""Errores de aplicación con mensajes en español para el usuario final."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class ErrorAplicacion(Exception):
    status_code = 400
    codigo = "error"

    def __init__(self, detalle: str, *, codigo: str | None = None) -> None:
        super().__init__(detalle)
        self.detalle = detalle
        if codigo:
            self.codigo = codigo


class NoAutenticado(ErrorAplicacion):
    status_code = 401
    codigo = "no_autenticado"


class SinPermiso(ErrorAplicacion):
    status_code = 403
    codigo = "sin_permiso"


class NoEncontrado(ErrorAplicacion):
    status_code = 404
    codigo = "no_encontrado"


class Conflicto(ErrorAplicacion):
    status_code = 409
    codigo = "conflicto"


class ReglaNegocio(ErrorAplicacion):
    status_code = 422
    codigo = "regla_negocio"


class DemasiadosIntentos(ErrorAplicacion):
    status_code = 429
    codigo = "demasiados_intentos"


_MENSAJES_VALIDACION = {
    "missing": "Este campo es obligatorio.",
    "string_too_short": "Debe tener al menos {min_length} caracteres.",
    "string_too_long": "Debe tener como máximo {max_length} caracteres.",
    "uuid_parsing": "Identificador inválido.",
    "enum": "Valor no permitido.",
    "literal_error": "Valor no permitido.",
    "bool_parsing": "Debe ser verdadero o falso.",
    "int_parsing": "Debe ser un número entero.",
    "decimal_parsing": "Debe ser un número.",
    "datetime_parsing": "Fecha y hora inválidas.",
    "date_parsing": "Fecha inválida.",
    "json_invalid": "El cuerpo de la solicitud no es JSON válido.",
}


def _traducir(error: dict[str, Any]) -> dict[str, str]:
    tipo = error.get("type", "")
    ctx = error.get("ctx") or {}
    plantilla = _MENSAJES_VALIDACION.get(tipo)
    if plantilla:
        try:
            mensaje = plantilla.format(**ctx)
        except (KeyError, IndexError):
            mensaje = plantilla
    elif tipo == "value_error" and "email" in str(ctx.get("reason", error.get("msg", ""))).lower():
        mensaje = "Correo electrónico inválido."
    else:
        mensaje = "Valor inválido."
    campo = ".".join(str(p) for p in error.get("loc", ()) if p not in ("body", "query", "path"))
    return {"campo": campo, "mensaje": mensaje}


def registrar_manejadores(app: FastAPI) -> None:
    @app.exception_handler(ErrorAplicacion)
    async def _error_aplicacion(_: Request, exc: ErrorAplicacion) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detalle": exc.detalle, "codigo": exc.codigo},
        )

    @app.exception_handler(RequestValidationError)
    async def _error_validacion(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "detalle": "Los datos enviados no son válidos.",
                "codigo": "validacion",
                "errores": [_traducir(e) for e in exc.errors()],
            },
        )

    @app.exception_handler(Exception)
    async def _error_inesperado(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Error no controlado", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={
                "detalle": "Ocurrió un error inesperado. Intente nuevamente o contacte al "
                "administrador.",
                "codigo": "error_interno",
            },
        )
