"""Formato común de todos los reportes: indicadores, series (gráficos) y tablas.

Un mismo `Reporte` lo dibuja el navegador y lo exporta el servidor a Excel o PDF, así cada
reporte nuevo se puede exportar sin código adicional.
"""

import uuid
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field

TipoDato = Literal["texto", "entero", "cantidad", "dinero", "porcentaje", "fecha"]


class Agrupacion(StrEnum):
    DIA = "dia"
    SEMANA = "semana"
    MES = "mes"
    ANIO = "anio"


class Filtros(BaseModel):
    desde: date
    hasta: date
    ubicacion_id: uuid.UUID | None = None
    cadena_id: uuid.UUID | None = None
    sucursal_cliente_id: uuid.UUID | None = None
    categoria_id: uuid.UUID | None = None
    producto_id: uuid.UUID | None = None
    agrupacion: Agrupacion = Agrupacion.DIA
    dias_sin_movimiento: int = Field(default=30, ge=1, le=3650)


class Kpi(BaseModel):
    clave: str
    titulo: str
    tipo: TipoDato
    valor: Decimal | int | None
    anterior: Decimal | int | None = None  # mismo indicador en el período anterior
    variacion: Decimal | None = None  # % de cambio contra el período anterior


class Columna(BaseModel):
    clave: str
    titulo: str
    tipo: TipoDato = "texto"


class Tabla(BaseModel):
    clave: str
    titulo: str
    descripcion: str | None = None
    columnas: list[Columna]
    filas: list[dict[str, Any]]


class Serie(BaseModel):
    """Datos de un gráfico: un punto por etiqueta (fecha o categoría) y un valor por clave."""

    clave: str
    titulo: str
    tipo: TipoDato
    forma: Literal["linea", "barras"] = "linea"
    eje: Literal["tiempo", "categoria"] = "tiempo"  # categoría: barras horizontales con nombre
    claves: list[Columna]  # cada serie del gráfico (p. ej. ingreso, costo, ganancia)
    puntos: list[dict[str, Any]]  # {"etiqueta": "...", <clave>: valor}


class Reporte(BaseModel):
    clave: str
    titulo: str
    descripcion: str
    filtros_texto: list[str]  # filtros aplicados, legibles (para la exportación)
    con_rentabilidad: bool  # si incluye costos y ganancias (permiso reportes.rentabilidad)
    kpis: list[Kpi] = []
    series: list[Serie] = []
    tablas: list[Tabla] = []
