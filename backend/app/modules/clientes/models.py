import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.models import Base, ConFechas, ConId, DeEmpresa


class Cadena(ConId, ConFechas, DeEmpresa, Base):
    """Cadena de supermercados (p. ej. Hipermaxi). El precio de venta es por cadena."""

    __tablename__ = "cadena"
    __table_args__ = (UniqueConstraint("empresa_id", "nombre"),)

    nombre: Mapped[str] = mapped_column(String(120))
    nit: Mapped[str | None] = mapped_column(String(30))
    telefono: Mapped[str | None] = mapped_column(String(30))
    correo: Mapped[str | None] = mapped_column(String(254))
    contacto: Mapped[str | None] = mapped_column(String(120))
    activo: Mapped[bool] = mapped_column(default=True)

    sucursales: Mapped[list["SucursalCliente"]] = relationship(
        lazy="selectin", order_by="SucursalCliente.nombre", back_populates="cadena"
    )


class SucursalCliente(ConId, ConFechas, Base):
    """Sucursal de supermercado / punto de entrega (p. ej. Hipermaxi Obrajes)."""

    __tablename__ = "sucursal_cliente"
    __table_args__ = (UniqueConstraint("cadena_id", "nombre"),)

    cadena_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cadena.id"), index=True)
    nombre: Mapped[str] = mapped_column(String(120))
    direccion: Mapped[str | None] = mapped_column(String(250))
    telefono: Mapped[str | None] = mapped_column(String(30))
    contacto: Mapped[str | None] = mapped_column(String(120))
    activo: Mapped[bool] = mapped_column(default=True)

    cadena: Mapped[Cadena] = relationship(back_populates="sucursales")
