import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.schemas import Esquema
from app.modules.organizacion.schemas import UbicacionResumen

PASSWORD = Field(min_length=10, max_length=128)


def _normalizar_correo(valor: str) -> str:
    return valor.strip().lower()


class LoginEntrada(BaseModel):
    correo: EmailStr
    password: str = Field(min_length=1, max_length=128)

    _norm = field_validator("correo")(_normalizar_correo)


class CambioPasswordEntrada(BaseModel):
    password_actual: str = Field(min_length=1, max_length=128)
    password_nueva: str = PASSWORD


class PermisoSalida(Esquema):
    codigo: str
    modulo: str
    descripcion: str


class RolResumen(Esquema):
    id: uuid.UUID
    nombre: str


class RolSalida(Esquema):
    id: uuid.UUID
    nombre: str
    descripcion: str | None
    es_sistema: bool
    permisos: list[str]


class RolEntrada(BaseModel):
    nombre: str = Field(min_length=2, max_length=60)
    descripcion: str | None = Field(default=None, max_length=250)
    permisos: list[str] = []


class RolActualizacion(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=60)
    descripcion: str | None = Field(default=None, max_length=250)
    permisos: list[str] | None = None


class UsuarioSalida(Esquema):
    id: uuid.UUID
    nombre: str
    apellido: str
    correo: str
    telefono: str | None
    activo: bool
    ultimo_acceso: datetime | None
    ubicacion_predeterminada_id: uuid.UUID | None
    roles: list[RolResumen]
    ubicaciones: list[UbicacionResumen]


class UsuarioYo(UsuarioSalida):
    permisos: list[str]


class UsuarioEntrada(BaseModel):
    nombre: str = Field(min_length=1, max_length=80)
    apellido: str = Field(min_length=1, max_length=80)
    correo: EmailStr
    telefono: str | None = Field(default=None, max_length=30)
    password: str = PASSWORD
    rol_ids: list[uuid.UUID] = Field(min_length=1)
    ubicacion_ids: list[uuid.UUID] = []
    ubicacion_predeterminada_id: uuid.UUID | None = None

    _norm = field_validator("correo")(_normalizar_correo)


class UsuarioActualizacion(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=80)
    apellido: str | None = Field(default=None, min_length=1, max_length=80)
    correo: EmailStr | None = None
    telefono: str | None = Field(default=None, max_length=30)
    activo: bool | None = None
    rol_ids: list[uuid.UUID] | None = Field(default=None, min_length=1)
    ubicacion_ids: list[uuid.UUID] | None = None
    ubicacion_predeterminada_id: uuid.UUID | None = None

    @field_validator("correo")
    @classmethod
    def _norm(cls, valor: str | None) -> str | None:
        return None if valor is None else _normalizar_correo(valor)


class RestablecerPasswordEntrada(BaseModel):
    password: str = PASSWORD


class AuditoriaSalida(Esquema):
    id: int
    fecha: datetime
    usuario_id: uuid.UUID | None
    usuario_nombre: str | None
    accion: str
    entidad: str
    entidad_id: str | None
    antes: dict[str, Any] | None
    despues: dict[str, Any] | None
    ip: str | None
