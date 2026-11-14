import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import BigInteger, Date, DateTime, Enum, ForeignKey, Identity, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.models import CANTIDAD, COSTO_UNITARIO, DINERO, Base, ConFechas, ConId, DeEmpresa
from app.modules.catalogo.models import Producto
from app.modules.identidad.models import Usuario
from app.modules.inventario.models import Lote
from app.modules.organizacion.models import Ubicacion
from app.modules.proveedores.models import Proveedor


class EstadoCompra(StrEnum):
    REGISTRADA = "REGISTRADA"
    ANULADA = "ANULADA"


class Compra(ConId, ConFechas, DeEmpresa, Base):
    __tablename__ = "compra"
    __mapper_args__ = {"eager_defaults": True}

    numero: Mapped[int] = mapped_column(BigInteger, Identity(), unique=True)
    proveedor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("proveedor.id"), index=True)
    ubicacion_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ubicacion.id"))
    fecha: Mapped[date] = mapped_column(Date)
    numero_documento: Mapped[str | None] = mapped_column(String(60))
    estado: Mapped[EstadoCompra] = mapped_column(
        Enum(
            EstadoCompra, name="estado_compra", native_enum=False, create_constraint=True, length=20
        ),
        default=EstadoCompra.REGISTRADA,
    )
    subtotal: Mapped[Decimal] = mapped_column(DINERO)
    costos_adicionales: Mapped[Decimal] = mapped_column(DINERO)
    total: Mapped[Decimal] = mapped_column(DINERO)
    observaciones: Mapped[str | None] = mapped_column(String(500))
    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))
    anulacion_motivo: Mapped[str | None] = mapped_column(String(500))
    anulado_por_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuario.id"))
    anulado_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    proveedor: Mapped[Proveedor] = relationship(lazy="joined")
    ubicacion: Mapped[Ubicacion] = relationship(lazy="joined")
    usuario: Mapped[Usuario] = relationship(foreign_keys=[usuario_id], lazy="joined")
    lineas: Mapped[list["CompraLinea"]] = relationship(
        lazy="selectin", order_by="CompraLinea.orden"
    )
    costos: Mapped[list["CompraCosto"]] = relationship(lazy="selectin")


class CompraLinea(ConId, Base):
    __tablename__ = "compra_linea"

    compra_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("compra.id"), index=True)
    orden: Mapped[int]
    producto_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("producto.id"), index=True)
    presentacion_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("presentacion.id"))
    presentacion_nombre: Mapped[str] = mapped_column(String(60))
    factor: Mapped[Decimal] = mapped_column(CANTIDAD)  # congelado al registrar
    cantidad: Mapped[Decimal] = mapped_column(CANTIDAD)  # en la presentación
    precio_presentacion: Mapped[Decimal] = mapped_column(DINERO)
    subtotal: Mapped[Decimal] = mapped_column(DINERO)
    prorrateo: Mapped[Decimal] = mapped_column(DINERO)  # parte de los costos adicionales
    cantidad_base: Mapped[Decimal] = mapped_column(CANTIDAD)
    costo_unitario_base: Mapped[Decimal] = mapped_column(COSTO_UNITARIO)
    lote_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lote.id"))

    producto: Mapped[Producto] = relationship(lazy="joined")
    lote: Mapped[Lote] = relationship(lazy="joined")


class CompraCosto(ConId, Base):
    """Costo adicional prorrateable (flete, carga, descarga…)."""

    __tablename__ = "compra_costo"

    compra_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("compra.id"), index=True)
    concepto: Mapped[str] = mapped_column(String(80))
    monto: Mapped[Decimal] = mapped_column(DINERO)
