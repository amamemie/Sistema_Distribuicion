import uuid

from pydantic import BaseModel, Field

from app.core.schemas import Esquema


class ProductoMinimo(Esquema):
    id: uuid.UUID
    sku: str
    nombre: str


class ProveedorSalida(Esquema):
    id: uuid.UUID
    nombre: str
    nit: str | None
    telefono: str | None
    correo: str | None
    direccion: str | None
    contacto: str | None
    activo: bool
    productos: list[ProductoMinimo]


class ProveedorEntrada(BaseModel):
    nombre: str = Field(min_length=2, max_length=150)
    nit: str | None = Field(default=None, max_length=30)
    telefono: str | None = Field(default=None, max_length=30)
    correo: str | None = Field(default=None, max_length=254)
    direccion: str | None = Field(default=None, max_length=250)
    contacto: str | None = Field(default=None, max_length=120)
    producto_ids: list[uuid.UUID] = []


class ProveedorActualizacion(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=150)
    nit: str | None = Field(default=None, max_length=30)
    telefono: str | None = Field(default=None, max_length=30)
    correo: str | None = Field(default=None, max_length=254)
    direccion: str | None = Field(default=None, max_length=250)
    contacto: str | None = Field(default=None, max_length=120)
    activo: bool | None = None
    producto_ids: list[uuid.UUID] | None = None
