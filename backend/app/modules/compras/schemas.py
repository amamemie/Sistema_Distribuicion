import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.core.schemas import Esquema
from app.modules.compras.models import CondicionPago, EstadoCompra


class CompraLineaEntrada(BaseModel):
    producto_id: uuid.UUID
    presentacion_id: uuid.UUID | None = None  # None = unidad base
    cantidad: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    precio_presentacion: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    lote_codigo: str | None = Field(default=None, max_length=60)
    lote_vencimiento: date | None = None


class CompraCostoEntrada(BaseModel):
    concepto: str = Field(min_length=1, max_length=80)
    monto: Decimal = Field(gt=0, max_digits=14, decimal_places=2)


class CompraEntrada(BaseModel):
    proveedor_id: uuid.UUID
    ubicacion_id: uuid.UUID
    fecha: date
    numero_documento: str | None = Field(default=None, max_length=60)
    observaciones: str | None = Field(default=None, max_length=500)
    lineas: list[CompraLineaEntrada] = Field(min_length=1)
    costos: list[CompraCostoEntrada] = []
    con_factura: bool = True  # da crédito fiscal (IVA)
    condicion_pago: CondicionPago = CondicionPago.CONTADO  # casi siempre al contado (D-29)
    fecha_vencimiento: date | None = None  # obligatoria a crédito


class AnulacionEntrada(BaseModel):
    motivo: str = Field(min_length=5, max_length=500)


class Referencia(Esquema):
    id: uuid.UUID
    nombre: str


class CompraLineaSalida(BaseModel):
    producto_id: uuid.UUID
    producto_sku: str
    producto_nombre: str
    unidad_base: str
    presentacion_nombre: str
    factor: Decimal
    cantidad: Decimal
    precio_presentacion: Decimal
    subtotal: Decimal
    prorrateo: Decimal
    cantidad_base: Decimal
    costo_unitario_base: Decimal
    lote_codigo: str | None
    lote_vencimiento: date | None


class CompraCostoSalida(Esquema):
    concepto: str
    monto: Decimal


class CompraResumen(BaseModel):
    id: uuid.UUID
    numero: int
    fecha: date
    numero_documento: str | None
    proveedor: Referencia
    ubicacion: Referencia
    estado: EstadoCompra
    total: Decimal
    con_factura: bool
    condicion_pago: CondicionPago
    fecha_vencimiento: date | None
    fecha_pago: date | None
    usuario_nombre: str
    created_at: datetime


class CompraDetalle(CompraResumen):
    subtotal: Decimal
    costos_adicionales: Decimal
    observaciones: str | None
    lineas: list[CompraLineaSalida]
    costos: list[CompraCostoSalida]
    anulacion_motivo: str | None
    anulado_at: datetime | None


class PrecioHistorico(BaseModel):
    fecha: date
    compra_numero: int
    proveedor: Referencia
    producto_id: uuid.UUID
    producto_nombre: str
    presentacion_nombre: str
    precio_presentacion: Decimal
    costo_unitario_base: Decimal
