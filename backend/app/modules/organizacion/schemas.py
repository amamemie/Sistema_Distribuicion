import uuid

from pydantic import BaseModel, Field

from app.core.schemas import Esquema
from app.modules.organizacion.models import TipoUbicacion


class UbicacionResumen(Esquema):
    id: uuid.UUID
    nombre: str
    tipo: TipoUbicacion


class UbicacionSalida(Esquema):
    id: uuid.UUID
    nombre: str
    tipo: TipoUbicacion
    direccion: str | None
    telefono: str | None
    activo: bool


class UbicacionEntrada(BaseModel):
    nombre: str = Field(min_length=2, max_length=120)
    tipo: TipoUbicacion
    direccion: str | None = Field(default=None, max_length=250)
    telefono: str | None = Field(default=None, max_length=30)


class UbicacionActualizacion(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=120)
    direccion: str | None = Field(default=None, max_length=250)
    telefono: str | None = Field(default=None, max_length=30)
    activo: bool | None = None
