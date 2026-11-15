"""Parámetros de alertas y reposición, guardados en `empresa.configuracion["alertas"]`.

Los valores por defecto son las respuestas del cliente (D-23 a D-26).
"""

from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.modules.organizacion.models import Empresa


class Parametros(BaseModel):
    dias_entrega_proveedor: int = Field(default=3, ge=0, le=180)  # D-24 (1 a 3 días)
    dias_reposicion_sucursal: int = Field(
        default=1, ge=0, le=30
    )  # transferencias al instante (D-13)
    cobertura_sucursal_dias: int = Field(default=7, ge=1, le=180)  # D-25
    cobertura_deposito_dias: int = Field(default=30, ge=1, le=365)  # D-25
    margen_minimo: float = Field(default=10, ge=0, le=100)  # D-26: % de margen
    dias_sin_movimiento: int = Field(default=30, ge=1, le=3650)
    dias_aviso_vencimiento: int = Field(default=30, ge=1, le=365)
    diferencia_conteo_pct: float = Field(default=10, ge=0, le=100)
    sobre_stock_veces: float = Field(default=4, ge=1, le=50)  # veces la cobertura deseada


def leer(db: Session, empresa_id: Any) -> Parametros:
    empresa = db.get(Empresa, empresa_id)
    datos = (empresa.configuracion or {}).get("alertas", {}) if empresa else {}
    return Parametros.model_validate(datos)


def guardar(db: Session, empresa_id: Any, parametros: Parametros) -> None:
    """Sin commit: lo hace el servicio que audita el cambio."""
    empresa = db.get(Empresa, empresa_id)
    assert empresa is not None
    empresa.configuracion = {**(empresa.configuracion or {}), "alertas": parametros.model_dump()}
