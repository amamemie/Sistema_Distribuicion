"""Finanzas: cobros de los supermercados, gastos operativos (D-27 a D-31).

La cuenta por cobrar no es una tabla aparte: cada pedido ENTREGADO es un documento por cobrar
por su monto facturado (ver `cuentas.py`). Lo que se guarda son los cobros (transferencias) y
cómo se aplicó cada uno a los pedidos, así el saldo siempre cuadra con los pedidos y sus
devoluciones.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Identity,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.models import DINERO, Base, ConFechas, ConId, DeEmpresa
from app.modules.clientes.models import Cadena
from app.modules.documentos.models import Archivo
from app.modules.identidad.models import Usuario
from app.modules.organizacion.models import Ubicacion


class EstadoRegistro(StrEnum):
    REGISTRADO = "REGISTRADO"
    ANULADO = "ANULADO"


def _estado(nombre: str) -> Enum:
    return Enum(EstadoRegistro, name=nombre, native_enum=False, create_constraint=True, length=20)


class Cobro(ConId, ConFechas, DeEmpresa, Base):
    """Transferencia recibida de una cadena. Normalmente cubre todo lo de un mes (D-27)."""

    __tablename__ = "cobro"
    # Monto 0 = cierre de saldo sin transferencia (solo diferencias cerradas con motivo).
    __table_args__ = (CheckConstraint("monto >= 0", name="monto_no_negativo"),)
    __mapper_args__ = {"eager_defaults": True}

    numero: Mapped[int] = mapped_column(BigInteger, Identity(), unique=True)
    cadena_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cadena.id"), index=True)
    fecha: Mapped[date] = mapped_column(Date)
    monto: Mapped[Decimal] = mapped_column(DINERO)
    banco: Mapped[str | None] = mapped_column(String(80))
    referencia: Mapped[str | None] = mapped_column(String(60))  # N.º de operación
    comprobante_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("archivo.id"))
    observaciones: Mapped[str | None] = mapped_column(String(500))
    estado: Mapped[EstadoRegistro] = mapped_column(
        _estado("estado_cobro"), default=EstadoRegistro.REGISTRADO
    )
    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))
    anulacion_motivo: Mapped[str | None] = mapped_column(String(500))
    anulado_por_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuario.id"))
    anulado_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    cadena: Mapped[Cadena] = relationship(lazy="joined")
    comprobante: Mapped[Archivo | None] = relationship(lazy="joined")
    usuario: Mapped[Usuario] = relationship(foreign_keys=[usuario_id], lazy="joined")
    detalles: Mapped[list["CobroDetalle"]] = relationship(
        lazy="selectin", order_by="CobroDetalle.orden"
    )


class CobroDetalle(ConId, Base):
    """Parte del cobro aplicada a un pedido. Si la cadena pagó menos por un error (D-28), la
    `diferencia` se da por cerrada con su motivo; si no se cierra, queda como saldo pendiente."""

    __tablename__ = "cobro_detalle"
    __table_args__ = (
        UniqueConstraint("cobro_id", "pedido_id"),
        CheckConstraint("monto >= 0", name="monto_no_negativo"),
        CheckConstraint("diferencia >= 0", name="diferencia_no_negativa"),
        CheckConstraint("monto + diferencia > 0", name="algo_aplicado"),
        CheckConstraint(
            "diferencia = 0 OR motivo_diferencia IS NOT NULL", name="diferencia_con_motivo"
        ),
    )

    cobro_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cobro.id"), index=True)
    pedido_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pedido.id"), index=True)
    orden: Mapped[int]
    monto: Mapped[Decimal] = mapped_column(DINERO)
    diferencia: Mapped[Decimal] = mapped_column(DINERO, default=Decimal(0))
    motivo_diferencia: Mapped[str | None] = mapped_column(String(300))


class CategoriaGasto(ConId, DeEmpresa, Base):
    __tablename__ = "categoria_gasto"
    __table_args__ = (UniqueConstraint("empresa_id", "nombre"),)

    nombre: Mapped[str] = mapped_column(String(60))
    factura_habitual: Mapped[bool] = mapped_column(default=False)  # sugiere "con factura"
    activo: Mapped[bool] = mapped_column(default=True)


class Gasto(ConId, ConFechas, DeEmpresa, Base):
    """Gasto operativo (gasolina, taxis, sueldos, luz, agua, alquiler… D-31)."""

    __tablename__ = "gasto"
    __table_args__ = (CheckConstraint("monto > 0", name="monto_positivo"),)
    __mapper_args__ = {"eager_defaults": True}

    numero: Mapped[int] = mapped_column(BigInteger, Identity(), unique=True)
    fecha: Mapped[date] = mapped_column(Date, index=True)
    categoria_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("categoria_gasto.id"))
    ubicacion_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ubicacion.id"))
    beneficiario: Mapped[str | None] = mapped_column(String(120))  # a quién se pagó
    descripcion: Mapped[str | None] = mapped_column(String(300))
    monto: Mapped[Decimal] = mapped_column(DINERO)
    con_factura: Mapped[bool] = mapped_column(default=False)  # da crédito fiscal (IVA)
    numero_factura: Mapped[str | None] = mapped_column(String(40))
    comprobante_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("archivo.id"))
    estado: Mapped[EstadoRegistro] = mapped_column(
        _estado("estado_gasto"), default=EstadoRegistro.REGISTRADO
    )
    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))
    anulacion_motivo: Mapped[str | None] = mapped_column(String(500))
    anulado_por_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuario.id"))
    anulado_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    categoria: Mapped[CategoriaGasto] = relationship(lazy="joined")
    ubicacion: Mapped[Ubicacion | None] = relationship(lazy="joined")
    comprobante: Mapped[Archivo | None] = relationship(lazy="joined")
    usuario: Mapped[Usuario] = relationship(foreign_keys=[usuario_id], lazy="joined")


CATEGORIAS_INICIALES: tuple[tuple[str, bool], ...] = (
    ("Gasolina", True),
    ("Taxis", False),
    ("Sueldos", False),
    ("Luz", True),
    ("Agua", True),
    ("Alquiler", False),
)
