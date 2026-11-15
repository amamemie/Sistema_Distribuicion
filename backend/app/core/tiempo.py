from datetime import UTC, date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import Date, cast, func
from sqlalchemy.sql.elements import ColumnElement

from app.core.config import get_settings


def ahora() -> datetime:
    return datetime.now(UTC)


def hoy() -> date:
    """Fecha actual en la zona horaria del negocio (America/La_Paz)."""
    return datetime.now(ZoneInfo(get_settings().zona_horaria)).date()


def fecha_local(columna: Any) -> ColumnElement[date]:
    """SQL: fecha de un instante en la zona horaria del negocio."""
    return cast(func.timezone(get_settings().zona_horaria, columna), Date)
