"""Parámetros de finanzas, guardados en `empresa.configuracion["finanzas"]`."""

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.modules.organizacion.models import Empresa


class ParametrosFinanzas(BaseModel):
    # Los supermercados pagan a fin de mes, a 30-40 días (D-27): pasado este plazo, vencido.
    dias_credito: int = Field(default=40, ge=1, le=365)
    iva_pct: Decimal = Field(default=Decimal(13), ge=0, le=100, decimal_places=2)  # D-30
    it_pct: Decimal = Field(default=Decimal(3), ge=0, le=100, decimal_places=2)  # D-30


def leer(db: Session, empresa_id: Any) -> ParametrosFinanzas:
    empresa = db.get(Empresa, empresa_id)
    datos = (empresa.configuracion or {}).get("finanzas", {}) if empresa else {}
    return ParametrosFinanzas.model_validate(datos)


def guardar(db: Session, empresa_id: Any, parametros: ParametrosFinanzas) -> None:
    """Sin commit: lo hace el servicio que audita el cambio."""
    empresa = db.get(Empresa, empresa_id)
    assert empresa is not None
    empresa.configuracion = {
        **(empresa.configuracion or {}),
        "finanzas": parametros.model_dump(mode="json"),
    }
