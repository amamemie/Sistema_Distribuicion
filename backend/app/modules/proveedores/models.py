from sqlalchemy import Column, ForeignKey, String, Table, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.models import Base, ConFechas, ConId, DeEmpresa
from app.modules.catalogo.models import Producto

proveedor_producto = Table(
    "proveedor_producto",
    Base.metadata,
    Column("proveedor_id", ForeignKey("proveedor.id", ondelete="CASCADE"), primary_key=True),
    Column("producto_id", ForeignKey("producto.id", ondelete="CASCADE"), primary_key=True),
)


class Proveedor(ConId, ConFechas, DeEmpresa, Base):
    __tablename__ = "proveedor"
    __table_args__ = (UniqueConstraint("empresa_id", "nombre"),)

    nombre: Mapped[str] = mapped_column(String(150))
    nit: Mapped[str | None] = mapped_column(String(30))
    telefono: Mapped[str | None] = mapped_column(String(30))
    correo: Mapped[str | None] = mapped_column(String(254))
    direccion: Mapped[str | None] = mapped_column(String(250))
    contacto: Mapped[str | None] = mapped_column(String(120))
    activo: Mapped[bool] = mapped_column(default=True)
    # Días que tarda en entregar una compra; vacío = el valor general de la empresa (D-24).
    dias_entrega: Mapped[int | None]

    productos: Mapped[list[Producto]] = relationship(secondary=proveedor_producto, lazy="selectin")
