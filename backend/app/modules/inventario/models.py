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
    Index,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.models import (
    CANTIDAD,
    COSTO_UNITARIO,
    DINERO,
    VALOR,
    Base,
    ConFechas,
    ConId,
    DeEmpresa,
)
from app.modules.catalogo.models import Producto
from app.modules.identidad.models import Usuario
from app.modules.organizacion.models import Ubicacion


def _enum(clase: type[StrEnum], nombre: str) -> Enum:
    return Enum(clase, name=nombre, native_enum=False, create_constraint=True, length=30)


class TipoMovimiento(StrEnum):
    COMPRA = "COMPRA"
    VENTA = "VENTA"
    TRANSFERENCIA_SALIDA = "TRANSFERENCIA_SALIDA"
    TRANSFERENCIA_ENTRADA = "TRANSFERENCIA_ENTRADA"
    AJUSTE_POSITIVO = "AJUSTE_POSITIVO"
    AJUSTE_NEGATIVO = "AJUSTE_NEGATIVO"
    DEVOLUCION_CLIENTE = "DEVOLUCION_CLIENTE"
    DEVOLUCION_PROVEEDOR = "DEVOLUCION_PROVEEDOR"
    ANULACION = "ANULACION"


class Lote(ConId, DeEmpresa, Base):
    """Grupo de unidades que ingresó junto (compra o ajuste). Conserva su costo y vencimiento
    aunque se transfiera entre ubicaciones."""

    __tablename__ = "lote"

    producto_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("producto.id"), index=True)
    codigo: Mapped[str | None] = mapped_column(String(60))
    vencimiento: Mapped[date | None] = mapped_column(Date)
    costo_unitario: Mapped[Decimal] = mapped_column(COSTO_UNITARIO)
    proveedor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("proveedor.id"))
    origen_tipo: Mapped[str] = mapped_column(String(30))
    origen_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    fecha_ingreso: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class StockUbicacion(ConId, DeEmpresa, Base):
    """Saldo materializado por (ubicación, producto). Siempre debe cuadrar con el libro."""

    __tablename__ = "stock_ubicacion"
    __table_args__ = (
        UniqueConstraint("ubicacion_id", "producto_id"),
        CheckConstraint("fisico >= 0", name="fisico_no_negativo"),
        CheckConstraint("comprometido >= 0", name="comprometido_no_negativo"),
        CheckConstraint("comprometido <= fisico", name="comprometido_menor_fisico"),
    )

    ubicacion_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ubicacion.id"))
    producto_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("producto.id"), index=True)
    fisico: Mapped[Decimal] = mapped_column(CANTIDAD, default=Decimal(0))
    comprometido: Mapped[Decimal] = mapped_column(CANTIDAD, default=Decimal(0))
    cpp: Mapped[Decimal] = mapped_column(COSTO_UNITARIO, default=Decimal(0))
    actualizado_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class StockLote(ConId, Base):
    __tablename__ = "stock_lote"
    __table_args__ = (
        UniqueConstraint("ubicacion_id", "lote_id"),
        CheckConstraint("cantidad >= 0", name="cantidad_no_negativa"),
        Index("ix_stock_lote_ubicacion_producto", "ubicacion_id", "producto_id"),
    )

    ubicacion_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ubicacion.id"))
    lote_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lote.id"))
    producto_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("producto.id"))
    cantidad: Mapped[Decimal] = mapped_column(CANTIDAD, default=Decimal(0))

    lote: Mapped[Lote] = relationship(lazy="joined")


class Movimiento(Base):
    """Libro de movimientos (kardex). Inmutable: un trigger impide UPDATE y DELETE."""

    __tablename__ = "movimiento"
    __table_args__ = (
        CheckConstraint("cantidad <> 0", name="cantidad_no_cero"),
        Index("ix_movimiento_producto_ubicacion", "producto_id", "ubicacion_id", "id"),
        Index("ix_movimiento_origen", "origen_tipo", "origen_id"),
        Index("ix_movimiento_fecha", "empresa_id", "fecha"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"))
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    tipo: Mapped[TipoMovimiento] = mapped_column(_enum(TipoMovimiento, "tipo_movimiento"))
    ubicacion_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ubicacion.id"))
    producto_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("producto.id"))
    lote_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("lote.id"))
    cantidad: Mapped[Decimal] = mapped_column(CANTIDAD)  # positiva = entrada, negativa = salida
    costo_unitario: Mapped[Decimal] = mapped_column(COSTO_UNITARIO)  # congelado al registrar
    costo_total: Mapped[Decimal] = mapped_column(VALOR)
    saldo_despues: Mapped[Decimal] = mapped_column(CANTIDAD)  # saldo de la ubicación
    cpp_despues: Mapped[Decimal] = mapped_column(COSTO_UNITARIO)
    origen_tipo: Mapped[str] = mapped_column(String(30))
    origen_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))
    motivo: Mapped[str | None] = mapped_column(String(500))
    revierte_id: Mapped[int | None] = mapped_column(ForeignKey("movimiento.id"))

    ubicacion: Mapped[Ubicacion] = relationship(lazy="joined")
    usuario: Mapped[Usuario] = relationship(lazy="joined")
    lote: Mapped[Lote | None] = relationship(lazy="joined")


# ---------------------------------------------------------------- transferencias


class EstadoDocumento(StrEnum):
    REALIZADA = "REALIZADA"
    ANULADA = "ANULADA"


class Transferencia(ConId, ConFechas, DeEmpresa, Base):
    __tablename__ = "transferencia"
    __table_args__ = (CheckConstraint("origen_id <> destino_id", name="origen_distinto_destino"),)
    __mapper_args__ = {"eager_defaults": True}

    numero: Mapped[int] = mapped_column(BigInteger, Identity(), unique=True)
    origen_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ubicacion.id"))
    destino_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ubicacion.id"))
    estado: Mapped[EstadoDocumento] = mapped_column(
        _enum(EstadoDocumento, "estado_transferencia"), default=EstadoDocumento.REALIZADA
    )
    observaciones: Mapped[str | None] = mapped_column(String(500))
    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))
    anulacion_motivo: Mapped[str | None] = mapped_column(String(500))
    anulado_por_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuario.id"))
    anulado_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    origen: Mapped[Ubicacion] = relationship(foreign_keys=[origen_id], lazy="joined")
    destino: Mapped[Ubicacion] = relationship(foreign_keys=[destino_id], lazy="joined")
    usuario: Mapped[Usuario] = relationship(foreign_keys=[usuario_id], lazy="joined")
    lineas: Mapped[list["TransferenciaLinea"]] = relationship(
        lazy="selectin", order_by="TransferenciaLinea.orden"
    )


class TransferenciaLinea(ConId, Base):
    __tablename__ = "transferencia_linea"

    transferencia_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("transferencia.id"), index=True)
    orden: Mapped[int]
    producto_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("producto.id"))
    presentacion_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("presentacion.id"))
    presentacion_nombre: Mapped[str] = mapped_column(String(60))
    factor: Mapped[Decimal] = mapped_column(CANTIDAD)
    cantidad: Mapped[Decimal] = mapped_column(CANTIDAD)
    cantidad_base: Mapped[Decimal] = mapped_column(CANTIDAD)
    costo_unitario: Mapped[Decimal] = mapped_column(COSTO_UNITARIO)

    producto: Mapped[Producto] = relationship(lazy="joined")


# ---------------------------------------------------------------- ajustes


class MotivoAjuste(StrEnum):
    MERMA = "MERMA"
    ROTURA = "ROTURA"
    VENCIMIENTO = "VENCIMIENTO"
    CONTEO_FISICO = "CONTEO_FISICO"
    CORRECCION = "CORRECCION"
    OTRO = "OTRO"


class EstadoAjuste(StrEnum):
    PENDIENTE = "PENDIENTE"
    APLICADO = "APLICADO"
    RECHAZADO = "RECHAZADO"


class Ajuste(ConId, ConFechas, DeEmpresa, Base):
    __tablename__ = "ajuste"
    __mapper_args__ = {"eager_defaults": True}

    numero: Mapped[int] = mapped_column(BigInteger, Identity(), unique=True)
    ubicacion_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ubicacion.id"))
    motivo: Mapped[MotivoAjuste] = mapped_column(_enum(MotivoAjuste, "motivo_ajuste"))
    observacion: Mapped[str] = mapped_column(String(500))
    estado: Mapped[EstadoAjuste] = mapped_column(_enum(EstadoAjuste, "estado_ajuste"))
    valor_total: Mapped[Decimal] = mapped_column(DINERO, default=Decimal(0))
    solicitado_por_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))
    resuelto_por_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuario.id"))
    resuelto_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolucion_nota: Mapped[str | None] = mapped_column(String(500))
    conteo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("conteo_fisico.id"))

    ubicacion: Mapped[Ubicacion] = relationship(lazy="joined")
    solicitado_por: Mapped[Usuario] = relationship(foreign_keys=[solicitado_por_id], lazy="joined")
    resuelto_por: Mapped[Usuario | None] = relationship(
        foreign_keys=[resuelto_por_id], lazy="joined"
    )
    lineas: Mapped[list["AjusteLinea"]] = relationship(
        lazy="selectin", order_by="AjusteLinea.orden"
    )


class AjusteLinea(ConId, Base):
    __tablename__ = "ajuste_linea"
    __table_args__ = (CheckConstraint("cantidad_base <> 0", name="cantidad_no_cero"),)

    ajuste_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ajuste.id"), index=True)
    orden: Mapped[int]
    producto_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("producto.id"))
    presentacion_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("presentacion.id"))
    presentacion_nombre: Mapped[str] = mapped_column(String(60))
    factor: Mapped[Decimal] = mapped_column(CANTIDAD)
    cantidad: Mapped[Decimal] = mapped_column(CANTIDAD)  # positiva; el signo va en cantidad_base
    cantidad_base: Mapped[Decimal] = mapped_column(CANTIDAD)  # + aumento / - disminución
    lote_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("lote.id"))
    lote_codigo: Mapped[str | None] = mapped_column(String(60))
    lote_vencimiento: Mapped[date | None] = mapped_column(Date)
    costo_unitario: Mapped[Decimal | None] = mapped_column(COSTO_UNITARIO)
    valor: Mapped[Decimal] = mapped_column(DINERO, default=Decimal(0))

    producto: Mapped[Producto] = relationship(lazy="joined")


# ---------------------------------------------------------------- conteo físico


class EstadoConteo(StrEnum):
    ABIERTO = "ABIERTO"
    APROBADO = "APROBADO"
    ANULADO = "ANULADO"


class ConteoFisico(ConId, ConFechas, DeEmpresa, Base):
    __tablename__ = "conteo_fisico"
    __mapper_args__ = {"eager_defaults": True}

    numero: Mapped[int] = mapped_column(BigInteger, Identity(), unique=True)
    ubicacion_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ubicacion.id"))
    estado: Mapped[EstadoConteo] = mapped_column(
        _enum(EstadoConteo, "estado_conteo"), default=EstadoConteo.ABIERTO
    )
    observaciones: Mapped[str | None] = mapped_column(String(500))
    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))
    aprobado_por_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuario.id"))
    aprobado_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    ubicacion: Mapped[Ubicacion] = relationship(lazy="joined")
    usuario: Mapped[Usuario] = relationship(foreign_keys=[usuario_id], lazy="joined")
    lineas: Mapped[list["ConteoLinea"]] = relationship(lazy="selectin")


class ConteoLinea(ConId, Base):
    __tablename__ = "conteo_linea"
    __table_args__ = (
        UniqueConstraint("conteo_id", "producto_id"),
        CheckConstraint("cantidad_contada IS NULL OR cantidad_contada >= 0", name="contada_valida"),
    )

    conteo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conteo_fisico.id"), index=True)
    producto_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("producto.id"))
    cantidad_contada: Mapped[Decimal | None] = mapped_column(CANTIDAD)
    cantidad_sistema: Mapped[Decimal | None] = mapped_column(CANTIDAD)  # se fija al aprobar
    vencimiento: Mapped[date | None] = mapped_column(Date)  # para sobrantes con vencimiento

    producto: Mapped[Producto] = relationship(lazy="joined")
