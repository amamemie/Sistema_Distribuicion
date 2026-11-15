import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.modules.catalogo.schemas import ProductoSalida
from app.modules.inventario.models import EstadoAjuste
from app.modules.pedidos.models import EstadoLectura, EstadoPedido


class Referencia(BaseModel):
    id: uuid.UUID
    nombre: str


# ---------------------------------------------------------------- entrada


class PedidoCrear(BaseModel):
    ubicacion_id: uuid.UUID  # sucursal que despacha
    observaciones: str | None = Field(default=None, max_length=500)


class PedidoLineaEntrada(BaseModel):
    codigo_cliente: str | None = Field(default=None, max_length=60)
    descripcion_cliente: str = Field(min_length=1, max_length=300)
    producto_id: uuid.UUID | None = None
    cantidad_oc: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    precio_oc: Decimal = Field(ge=0, max_digits=14, decimal_places=4)
    total_linea_oc: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    # Lo que se confirmará (D-02): por defecto, lo que pide la OC.
    cantidad_confirmada: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=3)


class PedidoBorradorEntrada(BaseModel):
    ubicacion_id: uuid.UUID
    cadena_id: uuid.UUID | None = None
    sucursal_cliente_id: uuid.UUID | None = None
    numero_oc: str | None = Field(default=None, max_length=60)
    fecha_oc: date | None = None
    fecha_entrega: date | None = None
    emisor: str | None = Field(default=None, max_length=120)
    total_oc: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    observaciones: str | None = Field(default=None, max_length=500)
    lineas: list[PedidoLineaEntrada] = Field(default=[], max_length=500)


class LoteAlistado(BaseModel):
    lote_id: uuid.UUID
    cantidad: Decimal = Field(gt=0, max_digits=14, decimal_places=3)


class AlistarLineaEntrada(BaseModel):
    linea_id: uuid.UUID
    cantidad_alistada: Decimal = Field(ge=0, max_digits=14, decimal_places=3)
    cantidad_merma: Decimal = Field(default=Decimal(0), ge=0, max_digits=14, decimal_places=3)
    lotes: list[LoteAlistado] = []  # vacío = FEFO automático


class AlistarEntrada(BaseModel):
    lineas: list[AlistarLineaEntrada] = Field(min_length=1)
    observacion_merma: str | None = Field(default=None, max_length=300)


class AnularEntrada(BaseModel):
    motivo: str = Field(min_length=5, max_length=500)


class DevolucionLineaEntrada(BaseModel):
    linea_id: uuid.UUID
    cantidad: Decimal = Field(gt=0, max_digits=14, decimal_places=3)


class DevolucionEntrada(BaseModel):
    motivo: str = Field(min_length=5, max_length=500)
    lineas: list[DevolucionLineaEntrada] = Field(min_length=1)


# ---------------------------------------------------------------- salida


class Validacion(BaseModel):
    nivel: Literal["error", "aviso"]  # "error" impide confirmar
    mensaje: str
    linea_id: uuid.UUID | None = None


class DocumentoSalida(BaseModel):
    id: uuid.UUID  # id del archivo
    nombre: str
    tipo_mime: str
    tamano: int


class LoteSalida(BaseModel):
    lote_id: uuid.UUID
    codigo: str | None
    vencimiento: date | None
    cantidad: Decimal
    devuelta: Decimal


class PedidoLineaSalida(BaseModel):
    id: uuid.UUID
    orden: int
    codigo_cliente: str | None
    descripcion_cliente: str
    producto: ProductoSalida | None
    cantidad_oc: Decimal
    precio_oc: Decimal
    total_linea_oc: Decimal | None
    total_calculado: Decimal
    cantidad_confirmada: Decimal
    cantidad_alistada: Decimal | None
    cantidad_merma: Decimal
    cantidad_devuelta: Decimal
    # Ayudas para la revisión (solo antes de alistar).
    disponible: Decimal | None = None
    disponible_depositos: Decimal | None = None
    precio_anterior: Decimal | None = None
    precio_anterior_fecha: date | None = None
    precio_anterior_pedido: int | None = None
    lotes: list[LoteSalida] = []
    # Solo con permiso costos.ver.
    costo_unitario: Decimal | None = None
    costo_total: Decimal | None = None
    ingreso: Decimal | None = None
    ganancia: Decimal | None = None
    margen: Decimal | None = None
    confianza: dict[str, float] | None = None  # lectura automática, por campo (0-1)


class EventoSalida(BaseModel):
    tipo: str
    usuario_nombre: str
    fecha: datetime
    detalle: dict[str, Any] | None


class AjusteRef(BaseModel):
    id: uuid.UUID
    numero: int
    estado: EstadoAjuste


class DevolucionLineaSalida(BaseModel):
    linea_id: uuid.UUID
    descripcion: str
    cantidad: Decimal


class DevolucionSalida(BaseModel):
    id: uuid.UUID
    numero: int
    fecha: datetime
    motivo: str
    usuario_nombre: str
    lineas: list[DevolucionLineaSalida]


class LecturaSalida(BaseModel):
    id: uuid.UUID
    estado: EstadoLectura
    plantilla: str | None
    motor: str | None
    confianza: Decimal | None
    aritmetica_ok: bool | None
    aplicada: bool
    error: str | None
    duracion_ms: int | None
    precision: Decimal | None
    created_at: datetime
    terminada_at: datetime | None


class PrecisionLectura(BaseModel):
    plantilla: str
    lecturas: int
    confirmadas: int
    precision_promedio: Decimal | None
    confianza_promedio: Decimal | None


class PedidoResumen(BaseModel):
    id: uuid.UUID
    numero: int
    estado: EstadoPedido
    numero_oc: str | None
    fecha_oc: date | None
    fecha_entrega: date | None
    cadena: Referencia | None
    sucursal_cliente: Referencia | None
    ubicacion: Referencia
    responsable_id: uuid.UUID
    responsable_nombre: str
    total_oc: Decimal | None
    total_calculado: Decimal
    lineas: int
    documentos: int
    created_at: datetime
    ganancia: Decimal | None = None
    margen: Decimal | None = None


class PedidoDetalle(PedidoResumen):
    emisor: str | None
    observaciones: str | None
    detalle_lineas: list[PedidoLineaSalida]
    detalle_documentos: list[DocumentoSalida]
    eventos: list[EventoSalida]
    validaciones: list[Validacion]
    mermas: list[AjusteRef]
    devoluciones: list[DevolucionSalida]
    anulacion_motivo: str | None
    anulado_desde: EstadoPedido | None
    receptor_nombre: str | None
    entrega_observacion: str | None
    constancia_foto_id: uuid.UUID | None
    constancia_firma_id: uuid.UUID | None
    entregado_at: datetime | None
    ingreso: Decimal | None = None
    costo: Decimal | None = None
    confianza: dict[str, Any] | None = None
    lectura: LecturaSalida | None = None


class Sugerencia(BaseModel):
    producto: ProductoSalida
    fuente: Literal["equivalencia", "codigo", "similitud"]
    puntaje: float
