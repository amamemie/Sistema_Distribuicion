import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

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
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.models import (
    CANTIDAD,
    COSTO_UNITARIO,
    DINERO,
    PORCENTAJE,
    PRECIO,
    Base,
    ConFechas,
    ConId,
    DeEmpresa,
)
from app.modules.catalogo.models import Producto
from app.modules.clientes.models import Cadena, SucursalCliente
from app.modules.documentos.models import Archivo
from app.modules.identidad.models import Usuario
from app.modules.inventario.models import Lote
from app.modules.organizacion.models import Ubicacion


class EstadoPedido(StrEnum):
    BORRADOR = "BORRADOR"
    CONFIRMADO = "CONFIRMADO"
    ALISTADO = "ALISTADO"
    ENTREGADO = "ENTREGADO"
    ANULADO = "ANULADO"


def _enum(clase: type[StrEnum], nombre: str) -> Enum:
    return Enum(clase, name=nombre, native_enum=False, create_constraint=True, length=20)


class Pedido(ConId, ConFechas, DeEmpresa, Base):
    """Pedido de un supermercado. Nace de una OC (D-06) y la despacha una sucursal."""

    __tablename__ = "pedido"
    __table_args__ = (
        # Una OC no se registra dos veces para la misma cadena (salvo que se haya anulado).
        Index(
            "uq_pedido_oc_vigente",
            "empresa_id",
            "cadena_id",
            text("upper(numero_oc)"),
            unique=True,
            postgresql_where=text(
                "estado <> 'ANULADO' AND numero_oc IS NOT NULL AND cadena_id IS NOT NULL"
            ),
        ),
        Index("ix_pedido_estado", "empresa_id", "estado"),
    )
    __mapper_args__ = {"eager_defaults": True}

    numero: Mapped[int] = mapped_column(BigInteger, Identity(), unique=True)
    estado: Mapped[EstadoPedido] = mapped_column(
        _enum(EstadoPedido, "estado_pedido"), default=EstadoPedido.BORRADOR
    )
    ubicacion_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ubicacion.id"))
    cadena_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cadena.id"))
    sucursal_cliente_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sucursal_cliente.id"))
    numero_oc: Mapped[str | None] = mapped_column(String(60))
    fecha_oc: Mapped[date | None] = mapped_column(Date)
    fecha_entrega: Mapped[date | None] = mapped_column(Date)
    emisor: Mapped[str | None] = mapped_column(String(120))
    total_oc: Mapped[Decimal | None] = mapped_column(DINERO)  # total impreso en la OC
    observaciones: Mapped[str | None] = mapped_column(String(500))

    responsable_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"), index=True)
    confirmado_por_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuario.id"))
    confirmado_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    alistado_por_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuario.id"))
    alistado_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    entregado_por_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuario.id"))
    entregado_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    anulado_por_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuario.id"))
    anulado_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    anulacion_motivo: Mapped[str | None] = mapped_column(String(500))
    anulado_desde: Mapped[EstadoPedido | None] = mapped_column(
        _enum(EstadoPedido, "estado_pedido_anulado")
    )

    # Rentabilidad (se calcula al alistar y se recalcula con devoluciones).
    ingreso: Mapped[Decimal | None] = mapped_column(DINERO)
    costo: Mapped[Decimal | None] = mapped_column(DINERO)
    ganancia: Mapped[Decimal | None] = mapped_column(DINERO)
    margen: Mapped[Decimal | None] = mapped_column(PORCENTAJE)

    # Constancia de entrega (opcional).
    receptor_nombre: Mapped[str | None] = mapped_column(String(120))
    entrega_observacion: Mapped[str | None] = mapped_column(String(500))
    constancia_foto_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("archivo.id"))
    constancia_firma_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("archivo.id"))
    # Confianza de la lectura automática por campo de cabecera (0-1).
    confianza: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    ubicacion: Mapped[Ubicacion] = relationship(lazy="joined")
    cadena: Mapped[Cadena | None] = relationship(lazy="joined")
    sucursal_cliente: Mapped[SucursalCliente | None] = relationship(lazy="joined")
    responsable: Mapped[Usuario] = relationship(foreign_keys=[responsable_id], lazy="joined")
    lineas: Mapped[list["PedidoLinea"]] = relationship(
        lazy="selectin", order_by="PedidoLinea.orden", cascade="all, delete-orphan"
    )
    documentos: Mapped[list["PedidoDocumento"]] = relationship(
        lazy="selectin", order_by="PedidoDocumento.orden"
    )
    eventos: Mapped[list["PedidoEvento"]] = relationship(
        lazy="selectin", order_by="PedidoEvento.id"
    )


class PedidoDocumento(ConId, Base):
    """Página o archivo de la OC (fotos y/o PDF, en orden)."""

    __tablename__ = "pedido_documento"

    pedido_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pedido.id"), index=True)
    archivo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("archivo.id"))
    orden: Mapped[int]
    activo: Mapped[bool] = mapped_column(default=True)  # se puede quitar en borrador

    archivo: Mapped[Archivo] = relationship(lazy="joined")


class PedidoLinea(ConId, Base):
    """Línea de la OC. Cantidades y precios por unidad base (D-10)."""

    __tablename__ = "pedido_linea"
    __table_args__ = (
        CheckConstraint("cantidad_oc > 0", name="cantidad_oc_positiva"),
        CheckConstraint("precio_oc >= 0", name="precio_no_negativo"),
        CheckConstraint("cantidad_confirmada >= 0", name="confirmada_no_negativa"),
        CheckConstraint(
            "cantidad_alistada IS NULL OR cantidad_alistada <= cantidad_confirmada",
            name="alistada_menor_confirmada",
        ),
        CheckConstraint(
            "cantidad_devuelta <= coalesce(cantidad_alistada, 0)", name="devuelta_menor_alistada"
        ),
    )

    pedido_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pedido.id"), index=True)
    orden: Mapped[int]
    codigo_cliente: Mapped[str | None] = mapped_column(String(60))
    descripcion_cliente: Mapped[str] = mapped_column(String(300))
    producto_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("producto.id"), index=True)
    cantidad_oc: Mapped[Decimal] = mapped_column(CANTIDAD)
    precio_oc: Mapped[Decimal] = mapped_column(PRECIO)
    total_linea_oc: Mapped[Decimal | None] = mapped_column(DINERO)  # impreso en la OC
    cantidad_confirmada: Mapped[Decimal] = mapped_column(CANTIDAD)
    cantidad_alistada: Mapped[Decimal | None] = mapped_column(CANTIDAD)
    cantidad_merma: Mapped[Decimal] = mapped_column(CANTIDAD, default=Decimal(0))
    cantidad_devuelta: Mapped[Decimal] = mapped_column(CANTIDAD, default=Decimal(0))
    costo_unitario: Mapped[Decimal | None] = mapped_column(COSTO_UNITARIO)  # congelado
    costo_total: Mapped[Decimal | None] = mapped_column(DINERO)
    ingreso: Mapped[Decimal | None] = mapped_column(DINERO)
    ganancia: Mapped[Decimal | None] = mapped_column(DINERO)
    confianza: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # lectura automática

    producto: Mapped[Producto | None] = relationship(lazy="joined")
    lotes: Mapped[list["PedidoLineaLote"]] = relationship(
        lazy="selectin", order_by="PedidoLineaLote.id", cascade="all, delete-orphan"
    )


class PedidoLineaLote(Base):
    """Lotes que salieron en el alistado, con su costo congelado."""

    __tablename__ = "pedido_linea_lote"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    linea_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pedido_linea.id"), index=True)
    lote_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lote.id"))
    cantidad: Mapped[Decimal] = mapped_column(CANTIDAD)
    costo_unitario: Mapped[Decimal] = mapped_column(COSTO_UNITARIO)
    devuelta: Mapped[Decimal] = mapped_column(CANTIDAD, default=Decimal(0))

    lote: Mapped[Lote] = relationship(lazy="joined")


class PedidoEvento(Base):
    """Historia del pedido: quién hizo qué y cuándo (complementa la auditoría)."""

    __tablename__ = "pedido_evento"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    pedido_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pedido.id"), index=True)
    tipo: Mapped[str] = mapped_column(String(30))
    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    detalle: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    usuario: Mapped[Usuario] = relationship(lazy="joined")


class Devolucion(ConId, DeEmpresa, Base):
    """Devolución de un supermercado después de la entrega (D-12): vuelve al stock."""

    __tablename__ = "devolucion"
    __mapper_args__ = {"eager_defaults": True}

    numero: Mapped[int] = mapped_column(BigInteger, Identity(), unique=True)
    pedido_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pedido.id"), index=True)
    motivo: Mapped[str] = mapped_column(String(500))
    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    usuario: Mapped[Usuario] = relationship(lazy="joined")
    lineas: Mapped[list["DevolucionLinea"]] = relationship(lazy="selectin")


class DevolucionLinea(ConId, Base):
    __tablename__ = "devolucion_linea"
    __table_args__ = (CheckConstraint("cantidad > 0", name="cantidad_positiva"),)

    devolucion_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("devolucion.id"), index=True)
    pedido_linea_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pedido_linea.id"))
    cantidad: Mapped[Decimal] = mapped_column(CANTIDAD)
    costo_total: Mapped[Decimal] = mapped_column(DINERO)
    ingreso: Mapped[Decimal] = mapped_column(DINERO)


class Equivalencia(ConId, DeEmpresa, Base):
    """Cómo llama una cadena a un producto nuestro (por código o por descripción).
    Se aprende al confirmar pedidos: cada vez hay menos que emparejar a mano (4.2)."""

    __tablename__ = "equivalencia"
    __table_args__ = (UniqueConstraint("cadena_id", "clave"),)

    cadena_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cadena.id"))
    clave: Mapped[str] = mapped_column(String(320))  # "C:<código>" o "D:<descripción>"
    codigo_cliente: Mapped[str | None] = mapped_column(String(60))
    descripcion_cliente: Mapped[str | None] = mapped_column(String(300))
    producto_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("producto.id"), index=True)
    usos: Mapped[int] = mapped_column(default=1)
    ultimo_uso: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    producto: Mapped[Producto] = relationship(lazy="joined")


class EstadoLectura(StrEnum):
    PENDIENTE = "PENDIENTE"
    PROCESANDO = "PROCESANDO"
    COMPLETADA = "COMPLETADA"
    FALLIDA = "FALLIDA"


class Lectura(ConId, DeEmpresa, Base):
    """Intento de lectura automática de la OC. Guarda el texto crudo del OCR, el resultado
    interpretado y, al confirmar, lo que el usuario corrigió (dataset para medir precisión)."""

    __tablename__ = "lectura_oc"

    pedido_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pedido.id"), index=True)
    estado: Mapped[EstadoLectura] = mapped_column(
        _enum(EstadoLectura, "estado_lectura"), default=EstadoLectura.PENDIENTE
    )
    reemplazar: Mapped[bool] = mapped_column(default=False)  # sobrescribe lo ya cargado
    motor: Mapped[str | None] = mapped_column(String(40))
    plantilla: Mapped[str | None] = mapped_column(String(40))
    palabras: Mapped[list[Any] | None] = mapped_column(JSONB)  # texto crudo con posiciones
    resultado: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    confianza: Mapped[Decimal | None] = mapped_column(PORCENTAJE)
    aritmetica_ok: Mapped[bool | None]
    aplicada: Mapped[bool] = mapped_column(default=False)
    error: Mapped[str | None] = mapped_column(String(500))
    duracion_ms: Mapped[int | None]
    correcciones: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    precision: Mapped[Decimal | None] = mapped_column(PORCENTAJE)  # % de campos sin corregir
    solicitado_por_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    terminada_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
