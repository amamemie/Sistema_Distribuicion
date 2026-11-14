from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from app.core.config import get_settings


def ahora() -> datetime:
    return datetime.now(UTC)


def hoy() -> date:
    """Fecha actual en la zona horaria del negocio (America/La_Paz)."""
    return datetime.now(ZoneInfo(get_settings().zona_horaria)).date()
