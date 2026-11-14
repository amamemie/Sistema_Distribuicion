import uuid
from decimal import Decimal

from pydantic import BaseModel, Field

from app.core.schemas import Esquema

CANTIDAD_POSITIVA = Field(gt=0, max_digits=14, decimal_places=3)


class NombreEntrada(BaseModel):
    nombre: str = Field(min_length=1, max_length=80)


class NombreActualizacion(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=80)
    activo: bool | None = None


class CategoriaSalida(Esquema):
    id: uuid.UUID
    nombre: str
    activo: bool


class MarcaSalida(CategoriaSalida):
    pass


class PresentacionSalida(Esquema):
    id: uuid.UUID
    nombre: str
    factor: Decimal
    codigo_barras: str | None
    activo: bool


class PresentacionEntrada(BaseModel):
    nombre: str = Field(min_length=1, max_length=60)
    factor: Decimal = CANTIDAD_POSITIVA
    codigo_barras: str | None = Field(default=None, max_length=60)


class PresentacionActualizacion(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=60)
    factor: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=3)
    codigo_barras: str | None = Field(default=None, max_length=60)
    activo: bool | None = None


class LimiteSalida(Esquema):
    ubicacion_id: uuid.UUID
    minimo: Decimal | None
    maximo: Decimal | None


class LimiteEntrada(BaseModel):
    ubicacion_id: uuid.UUID
    minimo: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=3)
    maximo: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=3)


class ProductoSalida(Esquema):
    id: uuid.UUID
    sku: str
    nombre: str
    descripcion: str | None
    categoria: CategoriaSalida
    marca: MarcaSalida | None
    unidad_base: str
    codigo_barras: str | None
    controla_vencimiento: bool
    activo: bool
    presentaciones: list[PresentacionSalida]


class ProductoDetalle(ProductoSalida):
    limites: list[LimiteSalida]


class ProductoEntrada(BaseModel):
    sku: str = Field(min_length=1, max_length=40)
    nombre: str = Field(min_length=2, max_length=200)
    descripcion: str | None = Field(default=None, max_length=500)
    categoria_id: uuid.UUID
    marca_id: uuid.UUID | None = None
    unidad_base: str = Field(default="unidad", min_length=1, max_length=30)
    codigo_barras: str | None = Field(default=None, max_length=60)
    controla_vencimiento: bool = False
    presentaciones: list[PresentacionEntrada] = []


class ProductoActualizacion(BaseModel):
    sku: str | None = Field(default=None, min_length=1, max_length=40)
    nombre: str | None = Field(default=None, min_length=2, max_length=200)
    descripcion: str | None = Field(default=None, max_length=500)
    categoria_id: uuid.UUID | None = None
    marca_id: uuid.UUID | None = None
    unidad_base: str | None = Field(default=None, min_length=1, max_length=30)
    codigo_barras: str | None = Field(default=None, max_length=60)
    controla_vencimiento: bool | None = None
    activo: bool | None = None
