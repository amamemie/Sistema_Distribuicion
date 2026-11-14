import uuid

from pydantic import BaseModel, Field

from app.core.schemas import Esquema


class SucursalClienteSalida(Esquema):
    id: uuid.UUID
    nombre: str
    direccion: str | None
    telefono: str | None
    contacto: str | None
    activo: bool


class CadenaSalida(Esquema):
    id: uuid.UUID
    nombre: str
    nit: str | None
    telefono: str | None
    correo: str | None
    contacto: str | None
    activo: bool
    sucursales: list[SucursalClienteSalida]


class CadenaEntrada(BaseModel):
    nombre: str = Field(min_length=2, max_length=120)
    nit: str | None = Field(default=None, max_length=30)
    telefono: str | None = Field(default=None, max_length=30)
    correo: str | None = Field(default=None, max_length=254)
    contacto: str | None = Field(default=None, max_length=120)


class CadenaActualizacion(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=120)
    nit: str | None = Field(default=None, max_length=30)
    telefono: str | None = Field(default=None, max_length=30)
    correo: str | None = Field(default=None, max_length=254)
    contacto: str | None = Field(default=None, max_length=120)
    activo: bool | None = None


class SucursalClienteEntrada(BaseModel):
    nombre: str = Field(min_length=2, max_length=120)
    direccion: str | None = Field(default=None, max_length=250)
    telefono: str | None = Field(default=None, max_length=30)
    contacto: str | None = Field(default=None, max_length=120)


class SucursalClienteActualizacion(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=120)
    direccion: str | None = Field(default=None, max_length=250)
    telefono: str | None = Field(default=None, max_length=30)
    contacto: str | None = Field(default=None, max_length=120)
    activo: bool | None = None
