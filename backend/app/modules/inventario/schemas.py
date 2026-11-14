import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.modules.inventario.models import (
    EstadoAjuste,
    EstadoConteo,
    EstadoDocumento,
    MotivoAjuste,
    TipoMovimiento,
)
from app.modules.organizacion.models import TipoUbicacion

CANTIDAD_POSITIVA = Field(gt=0, max_digits=14, decimal_places=3)


class Referencia(BaseModel):
    id: uuid.UUID
    nombre: str


# ---------------------------------------------------------------- stock


class StockEnUbicacion(BaseModel):
    ubicacion_id: uuid.UUID
    ubicacion_nombre: str
    ubicacion_tipo: TipoUbicacion
    fisico: Decimal
    comprometido: Decimal
    disponible: Decimal
    desglose: str
    minimo: Decimal | None
    maximo: Decimal | None
    bajo_minimo: bool
    cpp: Decimal | None  # solo con permiso costos.ver
    valor: Decimal | None


class StockProducto(BaseModel):
    producto_id: uuid.UUID
    sku: str
    nombre: str
    categoria: str
    unidad_base: str
    controla_vencimiento: bool
    ubicaciones: list[StockEnUbicacion]
    total_fisico: Decimal
    total_disponible: Decimal
    total_desglose: str
    valor_total: Decimal | None


class LoteEnStock(BaseModel):
    lote_id: uuid.UUID
    ubicacion_id: uuid.UUID
    ubicacion_nombre: str
    codigo: str | None
    vencimiento: date | None
    vencido: bool
    dias_para_vencer: int | None
    cantidad: Decimal
    fecha_ingreso: datetime
    costo_unitario: Decimal | None


class MovimientoKardex(BaseModel):
    id: int
    fecha: datetime
    tipo: TipoMovimiento
    ubicacion: Referencia
    documento: str
    origen_tipo: str
    origen_id: uuid.UUID
    lote_codigo: str | None
    entrada: Decimal | None
    salida: Decimal | None
    saldo: Decimal
    usuario_nombre: str
    motivo: str | None
    costo_unitario: Decimal | None
    costo_total: Decimal | None
    cpp_despues: Decimal | None


class ResultadoVerificacion(BaseModel):
    correcto: bool
    saldos_revisados: int
    diferencias: list[str]


# ---------------------------------------------------------------- líneas de documentos


class LineaCantidad(BaseModel):
    producto_id: uuid.UUID
    presentacion_id: uuid.UUID | None = None
    cantidad: Decimal = CANTIDAD_POSITIVA


class LineaDocumentoSalida(BaseModel):
    producto_id: uuid.UUID
    producto_sku: str
    producto_nombre: str
    unidad_base: str
    presentacion_nombre: str
    factor: Decimal
    cantidad: Decimal
    cantidad_base: Decimal
    costo_unitario: Decimal | None


# ---------------------------------------------------------------- transferencias


class TransferenciaLineaEntrada(LineaCantidad):
    lote_id: uuid.UUID | None = None


class TransferenciaEntrada(BaseModel):
    origen_id: uuid.UUID
    destino_id: uuid.UUID
    observaciones: str | None = Field(default=None, max_length=500)
    lineas: list[TransferenciaLineaEntrada] = Field(min_length=1)


class TransferenciaSalida(BaseModel):
    id: uuid.UUID
    numero: int
    fecha: datetime
    origen: Referencia
    destino: Referencia
    estado: EstadoDocumento
    observaciones: str | None
    usuario_nombre: str
    lineas: list[LineaDocumentoSalida]
    anulacion_motivo: str | None


class AnulacionEntrada(BaseModel):
    motivo: str = Field(min_length=5, max_length=500)


# ---------------------------------------------------------------- ajustes


class AjusteLineaEntrada(LineaCantidad):
    sentido: Literal["AUMENTO", "DISMINUCION"]
    lote_id: uuid.UUID | None = None  # disminución: lote específico (opcional)
    costo_unitario: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=6)
    lote_codigo: str | None = Field(default=None, max_length=60)  # aumento
    lote_vencimiento: date | None = None  # aumento de productos con vencimiento


class AjusteEntrada(BaseModel):
    ubicacion_id: uuid.UUID
    motivo: MotivoAjuste
    observacion: str = Field(min_length=3, max_length=500)
    lineas: list[AjusteLineaEntrada] = Field(min_length=1)


class ResolucionEntrada(BaseModel):
    nota: str | None = Field(default=None, max_length=500)


class AjusteLineaSalida(LineaDocumentoSalida):
    sentido: Literal["AUMENTO", "DISMINUCION"]
    lote_codigo: str | None
    lote_vencimiento: date | None
    valor: Decimal | None


class AjusteSalida(BaseModel):
    id: uuid.UUID
    numero: int
    fecha: datetime
    ubicacion: Referencia
    motivo: MotivoAjuste
    observacion: str
    estado: EstadoAjuste
    valor_total: Decimal | None
    solicitado_por: str
    resuelto_por: str | None
    resuelto_at: datetime | None
    resolucion_nota: str | None
    conteo_id: uuid.UUID | None
    pedido_id: uuid.UUID | None
    lineas: list[AjusteLineaSalida]


# ---------------------------------------------------------------- conteos


class ConteoEntrada(BaseModel):
    ubicacion_id: uuid.UUID
    observaciones: str | None = Field(default=None, max_length=500)
    cargar_productos_con_stock: bool = True
    categoria_id: uuid.UUID | None = None


class ConteoLineaEntrada(BaseModel):
    producto_id: uuid.UUID
    cantidad_contada: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=3)
    vencimiento: date | None = None


class ConteoLineaSalida(BaseModel):
    producto_id: uuid.UUID
    producto_sku: str
    producto_nombre: str
    unidad_base: str
    controla_vencimiento: bool
    cantidad_sistema: Decimal  # actual (o la fijada al aprobar)
    cantidad_contada: Decimal | None
    diferencia: Decimal | None
    vencimiento: date | None
    valor_diferencia: Decimal | None


class ConteoSalida(BaseModel):
    id: uuid.UUID
    numero: int
    fecha: datetime
    ubicacion: Referencia
    estado: EstadoConteo
    observaciones: str | None
    usuario_nombre: str
    aprobado_at: datetime | None
    ajuste_id: uuid.UUID | None
    lineas: list[ConteoLineaSalida]
