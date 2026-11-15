"""Canales de aviso. Por decisión del cliente (D-23) los avisos se ven solo dentro del sistema:
la alerta guardada ya es la notificación (campanita y centro de notificaciones).

Para sumar un canal externo (correo, WhatsApp, Telegram) basta con implementar `Notificador` y
agregarlo a `NOTIFICADORES`; las reglas no cambian.
"""

import logging
from typing import Protocol

from app.modules.alertas.models import Alerta

log = logging.getLogger(__name__)


class Notificador(Protocol):
    nombre: str

    def enviar(self, alerta: Alerta) -> None: ...


NOTIFICADORES: list[Notificador] = []


def notificar(alerta: Alerta) -> None:
    """Envía una alerta nueva por los canales externos configurados (si los hay). Un canal que
    falla no impide los demás ni deshace la alerta."""
    for canal in NOTIFICADORES:
        try:
            canal.enviar(alerta)
        except Exception:
            log.exception("No se pudo enviar la alerta %s por %s", alerta.id, canal.nombre)
