import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel

from app.modules.alertas.models import Confianza, EstadoAlerta, Severidad


class AlertaSalida(BaseModel):
    id: uuid.UUID
    tipo: str
    severidad: Severidad
    titulo: str
    mensaje: str
    enlace: str | None
    ubicacion: str | None
    producto: str | None
    datos: dict[str, Any]
    auto_resolver: bool
    estado: EstadoAlerta
    creada_at: datetime
    resuelta_at: datetime | None
    resuelta_por: str | None
    leida: bool


class ResumenAlertas(BaseModel):
    no_leidas: int
    criticas: int  # activas y críticas (leídas o no)


class MarcarLeidas(BaseModel):
    ids: list[uuid.UUID] | None = None  # None = todas las visibles y activas


class ResultadoEvaluacion(BaseModel):
    creadas: int
    actualizadas: int
    resueltas: int
    pronosticos: int


class Referencia(BaseModel):
    id: uuid.UUID
    nombre: str


class FilaReposicion(BaseModel):
    ubicacion: Referencia
    producto: Referencia
    sku: str
    unidad: str
    disponible: Decimal
    demanda_semanal: Decimal
    cobertura_dias: Decimal | None
    stock_seguridad: Decimal
    punto_reorden: Decimal
    objetivo: Decimal
    confianza: Confianza
    metodo: str
    semanas: int
    con_limites: bool  # se usaron el mínimo/máximo cargados


class SugerenciaTransferenciaSalida(FilaReposicion):
    origen: Referencia
    origen_disponible: Decimal
    cantidad: Decimal
    presentacion: str
    cantidad_presentacion: Decimal
    insuficiente: bool


class SugerenciaCompraSalida(FilaReposicion):
    proveedor: Referencia | None
    dias_entrega: int
    fecha: date
    cantidad: Decimal
    presentacion: str
    cantidad_presentacion: Decimal
    costo_estimado: Decimal | None  # solo con costos.ver


class PronosticoSalida(BaseModel):
    producto: Referencia
    ubicacion: Referencia
    metodo: str
    confianza: Confianza
    semanas: int
    demanda_semanal: Decimal
    error_medio: Decimal | None
    historial: list[float]
    calculado_at: datetime | None
