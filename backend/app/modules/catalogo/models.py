import uuid
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.models import CANTIDAD, Base, ConFechas, ConId, DeEmpresa


class Categoria(ConId, ConFechas, DeEmpresa, Base):
    __tablename__ = "categoria"
    __table_args__ = (UniqueConstraint("empresa_id", "nombre"),)

    nombre: Mapped[str] = mapped_column(String(80))
    activo: Mapped[bool] = mapped_column(default=True)


class Marca(ConId, ConFechas, DeEmpresa, Base):
    __tablename__ = "marca"
    __table_args__ = (UniqueConstraint("empresa_id", "nombre"),)

    nombre: Mapped[str] = mapped_column(String(80))
    activo: Mapped[bool] = mapped_column(default=True)


class Producto(ConId, ConFechas, DeEmpresa, Base):
    """Producto vendible. Todo el inventario se lleva en su unidad base (la unidad de venta)."""

    __tablename__ = "producto"
    __table_args__ = (
        UniqueConstraint("empresa_id", "sku"),
        Index("ix_producto_codigo_barras", "empresa_id", "codigo_barras"),
    )

    sku: Mapped[str] = mapped_column(String(40))
    nombre: Mapped[str] = mapped_column(String(200))
    descripcion: Mapped[str | None] = mapped_column(String(500))
    categoria_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("categoria.id"), index=True)
    marca_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("marca.id"))
    unidad_base: Mapped[str] = mapped_column(String(30), default="unidad")
    codigo_barras: Mapped[str | None] = mapped_column(String(60))
    controla_vencimiento: Mapped[bool] = mapped_column(default=False)
    activo: Mapped[bool] = mapped_column(default=True)

    categoria: Mapped[Categoria] = relationship(lazy="joined")
    marca: Mapped[Marca | None] = relationship(lazy="joined")
    presentaciones: Mapped[list["Presentacion"]] = relationship(
        lazy="selectin", order_by="Presentacion.factor.desc()", back_populates="producto"
    )


class Presentacion(ConId, ConFechas, Base):
    """Unidad de compra/almacenaje (fardo, caja…) con su equivalencia en unidades base."""

    __tablename__ = "presentacion"
    __table_args__ = (
        UniqueConstraint("producto_id", "nombre"),
        CheckConstraint("factor > 0", name="factor_positivo"),
    )

    producto_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("producto.id"), index=True)
    nombre: Mapped[str] = mapped_column(String(60))
    factor: Mapped[Decimal] = mapped_column(CANTIDAD)
    codigo_barras: Mapped[str | None] = mapped_column(String(60))
    activo: Mapped[bool] = mapped_column(default=True)

    producto: Mapped[Producto] = relationship(back_populates="presentaciones")


class LimiteStock(ConId, Base):
    """Stock mínimo y máximo de un producto en una ubicación (en unidad base)."""

    __tablename__ = "limite_stock"
    __table_args__ = (
        UniqueConstraint("producto_id", "ubicacion_id"),
        CheckConstraint(
            "minimo IS NULL OR maximo IS NULL OR maximo >= minimo", name="rango_valido"
        ),
    )

    producto_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("producto.id"), index=True)
    ubicacion_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ubicacion.id"))
    minimo: Mapped[Decimal | None] = mapped_column(CANTIDAD)
    maximo: Mapped[Decimal | None] = mapped_column(CANTIDAD)
