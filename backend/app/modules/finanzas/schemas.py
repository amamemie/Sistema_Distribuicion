import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.modules.finanzas.cuentas import EstadoCuenta
from app.modules.finanzas.models import EstadoRegistro


class Ref(BaseModel):
    id: uuid.UUID
    nombre: str


# ================================================================ por cobrar


class CuentaSalida(BaseModel):
    pedido_id: uuid.UUID
    numero: int
    numero_oc: str | None
    cadena: Ref
    sucursal: str | None
    fecha: date
    vencimiento: date
    monto: Decimal
    cobrado: Decimal
    diferencia: Decimal
    saldo: Decimal
    estado: EstadoCuenta
    dias_vencida: int


class ResumenCadenaSalida(BaseModel):
    cadena: Ref
    pedidos_pendientes: int
    pendiente: Decimal
    vencido: Decimal
    a_favor: Decimal
    mas_antiguo: date | None


class PorCobrar(BaseModel):
    total_pendiente: Decimal
    total_vencido: Decimal
    cobrado_mes: Decimal
    cadenas: list[ResumenCadenaSalida]
    cuentas: list[CuentaSalida]


class CierreSaldoEntrada(BaseModel):
    motivo: str = Field(min_length=3, max_length=300)


class AjusteSaldoEntrada(BaseModel):
    """Rebaja lo que debe una cadena sin transferencia (error reconocido que no se va a pagar)."""

    monto: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    motivo: str = Field(min_length=3, max_length=300)


# ================================================================ cobros


class CobroDetalleEntrada(BaseModel):
    pedido_id: uuid.UUID
    monto: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    # Si la cadena pagó menos por un error (D-28): cerrar lo que falta con su motivo.
    cerrar_diferencia: bool = False
    motivo_diferencia: str | None = Field(default=None, max_length=300)


class CobroEntrada(BaseModel):
    cadena_id: uuid.UUID
    fecha: date
    monto: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    banco: str | None = Field(default=None, max_length=80)
    referencia: str | None = Field(default=None, max_length=60)
    observaciones: str | None = Field(default=None, max_length=500)
    # Sin detalles (lo normal, T-31): el monto se aplica al total que debe la cadena, del pedido
    # más antiguo al más reciente. Con detalles: reparto manual pedido por pedido.
    detalles: list[CobroDetalleEntrada] = Field(default_factory=list, max_length=500)


class AnulacionEntrada(BaseModel):
    motivo: str = Field(min_length=5, max_length=500)


class CobroDetalleSalida(BaseModel):
    pedido_id: uuid.UUID
    pedido_numero: int
    numero_oc: str | None
    sucursal: str | None
    monto: Decimal
    diferencia: Decimal
    motivo_diferencia: str | None


class CobroResumen(BaseModel):
    id: uuid.UUID
    numero: int
    cadena: Ref
    fecha: date
    monto: Decimal
    diferencias: Decimal
    banco: str | None
    referencia: str | None
    estado: EstadoRegistro
    es_cierre: bool  # cierre de saldo sin transferencia
    pedidos: int
    usuario_nombre: str
    created_at: datetime


class CobroDetalleCompleto(CobroResumen):
    observaciones: str | None
    comprobante_id: uuid.UUID | None
    comprobante_nombre: str | None
    anulacion_motivo: str | None
    anulado_at: datetime | None
    detalles: list[CobroDetalleSalida]


# ================================================================ gastos


class CategoriaGastoEntrada(BaseModel):
    nombre: str = Field(min_length=2, max_length=60)
    factura_habitual: bool = False
    activo: bool = True


class CategoriaGastoSalida(BaseModel):
    id: uuid.UUID
    nombre: str
    factura_habitual: bool
    activo: bool


class GastoEntrada(BaseModel):
    fecha: date
    categoria_id: uuid.UUID
    ubicacion_id: uuid.UUID | None = None
    beneficiario: str | None = Field(default=None, max_length=120)
    descripcion: str | None = Field(default=None, max_length=300)
    monto: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    con_factura: bool = False
    numero_factura: str | None = Field(default=None, max_length=40)


class GastoSalida(BaseModel):
    id: uuid.UUID
    numero: int
    fecha: date
    categoria: Ref
    ubicacion: Ref | None
    beneficiario: str | None
    descripcion: str | None
    monto: Decimal
    con_factura: bool
    numero_factura: str | None
    comprobante_id: uuid.UUID | None
    comprobante_nombre: str | None
    estado: EstadoRegistro
    anulacion_motivo: str | None
    usuario_nombre: str
    created_at: datetime


class TotalCategoria(BaseModel):
    categoria: Ref
    total: Decimal


class PaginaGastos(BaseModel):
    items: list[GastoSalida]
    total: int
    pagina: int
    tamano: int
    suma: Decimal  # de todos los gastos vigentes que cumplen el filtro
    por_categoria: list[TotalCategoria]


# ================================================================ por pagar


class CompraPorPagar(BaseModel):
    id: uuid.UUID
    numero: int
    fecha: date
    proveedor: Ref
    numero_documento: str | None
    total: Decimal
    fecha_vencimiento: date | None
    dias_para_vencer: int | None  # negativo = vencida


class PagoCompraEntrada(BaseModel):
    fecha: date


# ================================================================ impuestos


class ImpuestoMes(BaseModel):
    mes: date  # primer día del mes
    ventas: Decimal  # facturado (entregas del mes)
    iva_debito: Decimal
    compras_con_factura: Decimal
    gastos_con_factura: Decimal
    iva_credito: Decimal
    saldo_anterior: Decimal  # crédito fiscal que venía de meses anteriores
    iva_pagar: Decimal
    saldo_siguiente: Decimal  # crédito fiscal que pasa al mes siguiente
    it: Decimal
    total_pagar: Decimal
