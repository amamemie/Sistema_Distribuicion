from enum import StrEnum
from typing import Any

from sqlalchemy import Enum, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import Base, ConFechas, ConId, DeEmpresa


class TipoUbicacion(StrEnum):
    DEPOSITO = "DEPOSITO"  # guarda mercadería en unidades grandes; no despacha a clientes
    SUCURSAL = "SUCURSAL"  # fracciona, alista y despacha pedidos a supermercados


class Empresa(ConId, ConFechas, Base):
    __tablename__ = "empresa"

    nombre: Mapped[str] = mapped_column(String(150))
    nit: Mapped[str | None] = mapped_column(String(30))
    activo: Mapped[bool] = mapped_column(default=True)
    configuracion: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")


class Ubicacion(ConId, ConFechas, DeEmpresa, Base):
    """Depósito o sucursal de la empresa."""

    __tablename__ = "ubicacion"
    __table_args__ = (UniqueConstraint("empresa_id", "nombre"),)

    nombre: Mapped[str] = mapped_column(String(120))
    tipo: Mapped[TipoUbicacion] = mapped_column(
        Enum(
            TipoUbicacion,
            name="tipo_ubicacion",
            native_enum=False,
            create_constraint=True,
            length=20,
        )
    )
    direccion: Mapped[str | None] = mapped_column(String(250))
    telefono: Mapped[str | None] = mapped_column(String(30))
    activo: Mapped[bool] = mapped_column(default=True)
