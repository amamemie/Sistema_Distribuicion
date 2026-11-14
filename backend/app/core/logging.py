"""Logs estructurados en JSON y middleware de registro de solicitudes."""

import json
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from datetime import UTC, datetime

from fastapi import Request, Response

id_solicitud: ContextVar[str | None] = ContextVar("id_solicitud", default=None)


class FormatoJSON(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        datos: dict[str, object] = {
            "fecha": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "nivel": record.levelname,
            "logger": record.name,
            "mensaje": record.getMessage(),
        }
        rid = id_solicitud.get()
        if rid:
            datos["id_solicitud"] = rid
        extra = getattr(record, "datos", None)
        if isinstance(extra, dict):
            datos.update(extra)
        if record.exc_info:
            datos["excepcion"] = self.formatException(record.exc_info)
        return json.dumps(datos, ensure_ascii=False, default=str)


def configurar_logging(nivel: str = "INFO") -> None:
    manejador = logging.StreamHandler()
    manejador.setFormatter(FormatoJSON())
    raiz = logging.getLogger()
    raiz.handlers = [manejador]
    raiz.setLevel(nivel)


_log_http = logging.getLogger("app.http")


async def middleware_registro(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    token = id_solicitud.set(rid)
    inicio = time.perf_counter()
    try:
        respuesta = await call_next(request)
    finally:
        id_solicitud.reset(token)
    duracion_ms = round((time.perf_counter() - inicio) * 1000, 1)
    respuesta.headers["X-Request-ID"] = rid
    _log_http.info(
        "solicitud",
        extra={
            "datos": {
                "id_solicitud": rid,
                "metodo": request.method,
                "ruta": request.url.path,
                "estado": respuesta.status_code,
                "duracion_ms": duracion_ms,
            }
        },
    )
    return respuesta
