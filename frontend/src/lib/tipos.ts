/** Tipos de las respuestas de la API (reflejan los esquemas de Pydantic del backend). */

export type TipoUbicacion = 'DEPOSITO' | 'SUCURSAL'

export interface UbicacionResumen {
  id: string
  nombre: string
  tipo: TipoUbicacion
}

export interface Ubicacion extends UbicacionResumen {
  direccion: string | null
  telefono: string | null
  activo: boolean
}

export interface RolResumen {
  id: string
  nombre: string
}

export interface Rol extends RolResumen {
  descripcion: string | null
  es_sistema: boolean
  permisos: string[]
}

export interface Permiso {
  codigo: string
  modulo: string
  descripcion: string
}

export interface Usuario {
  id: string
  nombre: string
  apellido: string
  correo: string
  telefono: string | null
  activo: boolean
  ultimo_acceso: string | null
  ubicacion_predeterminada_id: string | null
  roles: RolResumen[]
  ubicaciones: UbicacionResumen[]
}

export interface UsuarioYo extends Usuario {
  permisos: string[]
}

export interface RegistroAuditoria {
  id: number
  fecha: string
  usuario_id: string | null
  usuario_nombre: string | null
  accion: string
  entidad: string
  entidad_id: string | null
  antes: Record<string, unknown> | null
  despues: Record<string, unknown> | null
  ip: string | null
}

export interface Pagina<T> {
  items: T[]
  total: number
  pagina: number
  tamano: number
}

export const NOMBRE_TIPO_UBICACION: Record<TipoUbicacion, string> = {
  DEPOSITO: 'Depósito',
  SUCURSAL: 'Sucursal',
}

// ---------------------------------------------------------------- Fase 1: catálogo e inventario
// Los decimales llegan como texto desde la API (precisión exacta); se formatean al mostrarlos.
export type Decimal = string

export interface Referencia {
  id: string
  nombre: string
}

export interface Categoria {
  id: string
  nombre: string
  activo: boolean
}
export type Marca = Categoria

export interface Presentacion {
  id: string
  nombre: string
  factor: Decimal
  codigo_barras: string | null
  activo: boolean
}

export interface Producto {
  id: string
  sku: string
  nombre: string
  descripcion: string | null
  categoria: Categoria
  marca: Marca | null
  unidad_base: string
  codigo_barras: string | null
  controla_vencimiento: boolean
  activo: boolean
  presentaciones: Presentacion[]
}

export interface Limite {
  ubicacion_id: string
  minimo: Decimal | null
  maximo: Decimal | null
}

export interface ProductoDetalle extends Producto {
  limites: Limite[]
}

export interface Proveedor {
  id: string
  nombre: string
  nit: string | null
  telefono: string | null
  correo: string | null
  direccion: string | null
  contacto: string | null
  dias_entrega: number | null
  activo: boolean
  productos: { id: string; sku: string; nombre: string }[]
}

export interface SucursalCliente {
  id: string
  nombre: string
  direccion: string | null
  telefono: string | null
  contacto: string | null
  activo: boolean
}

export interface Cadena {
  id: string
  nombre: string
  nit: string | null
  telefono: string | null
  correo: string | null
  contacto: string | null
  activo: boolean
  sucursales: SucursalCliente[]
}

export interface CompraResumen {
  id: string
  numero: number
  fecha: string
  numero_documento: string | null
  proveedor: Referencia
  ubicacion: Referencia
  estado: 'REGISTRADA' | 'ANULADA'
  total: Decimal
  con_factura: boolean
  condicion_pago: 'CONTADO' | 'CREDITO'
  fecha_vencimiento: string | null
  fecha_pago: string | null
  usuario_nombre: string
  created_at: string
}

export interface CompraLinea {
  producto_id: string
  producto_sku: string
  producto_nombre: string
  unidad_base: string
  presentacion_nombre: string
  factor: Decimal
  cantidad: Decimal
  precio_presentacion: Decimal
  subtotal: Decimal
  prorrateo: Decimal
  cantidad_base: Decimal
  costo_unitario_base: Decimal
  lote_codigo: string | null
  lote_vencimiento: string | null
}

export interface CompraDetalle extends CompraResumen {
  subtotal: Decimal
  costos_adicionales: Decimal
  observaciones: string | null
  lineas: CompraLinea[]
  costos: { concepto: string; monto: Decimal }[]
  anulacion_motivo: string | null
  anulado_at: string | null
}

export interface StockEnUbicacion {
  ubicacion_id: string
  ubicacion_nombre: string
  ubicacion_tipo: TipoUbicacion
  fisico: Decimal
  comprometido: Decimal
  disponible: Decimal
  desglose: string
  minimo: Decimal | null
  maximo: Decimal | null
  bajo_minimo: boolean
  cpp: Decimal | null
  valor: Decimal | null
}

export interface StockProducto {
  producto_id: string
  sku: string
  nombre: string
  categoria: string
  unidad_base: string
  controla_vencimiento: boolean
  ubicaciones: StockEnUbicacion[]
  total_fisico: Decimal
  total_disponible: Decimal
  total_desglose: string
  valor_total: Decimal | null
}

export interface LoteEnStock {
  lote_id: string
  ubicacion_id: string
  ubicacion_nombre: string
  codigo: string | null
  vencimiento: string | null
  vencido: boolean
  dias_para_vencer: number | null
  cantidad: Decimal
  fecha_ingreso: string
  costo_unitario: Decimal | null
}

export type TipoMovimiento =
  | 'COMPRA'
  | 'VENTA'
  | 'TRANSFERENCIA_SALIDA'
  | 'TRANSFERENCIA_ENTRADA'
  | 'AJUSTE_POSITIVO'
  | 'AJUSTE_NEGATIVO'
  | 'DEVOLUCION_CLIENTE'
  | 'DEVOLUCION_PROVEEDOR'
  | 'ANULACION'

export interface MovimientoKardex {
  id: number
  fecha: string
  tipo: TipoMovimiento
  ubicacion: Referencia
  documento: string
  origen_tipo: string
  origen_id: string
  lote_codigo: string | null
  entrada: Decimal | null
  salida: Decimal | null
  saldo: Decimal
  usuario_nombre: string
  motivo: string | null
  costo_unitario: Decimal | null
  costo_total: Decimal | null
  cpp_despues: Decimal | null
}

export interface LineaDocumento {
  producto_id: string
  producto_sku: string
  producto_nombre: string
  unidad_base: string
  presentacion_nombre: string
  factor: Decimal
  cantidad: Decimal
  cantidad_base: Decimal
  costo_unitario: Decimal | null
}

export interface Transferencia {
  id: string
  numero: number
  fecha: string
  origen: Referencia
  destino: Referencia
  estado: 'REALIZADA' | 'ANULADA'
  observaciones: string | null
  usuario_nombre: string
  lineas: LineaDocumento[]
  anulacion_motivo: string | null
}

export type MotivoAjuste = 'MERMA' | 'ROTURA' | 'VENCIMIENTO' | 'CONTEO_FISICO' | 'CORRECCION' | 'OTRO'
export type EstadoAjuste = 'PENDIENTE' | 'APLICADO' | 'RECHAZADO'

export interface AjusteLinea extends LineaDocumento {
  sentido: 'AUMENTO' | 'DISMINUCION'
  lote_codigo: string | null
  lote_vencimiento: string | null
  valor: Decimal | null
}

export interface Ajuste {
  id: string
  numero: number
  fecha: string
  ubicacion: Referencia
  motivo: MotivoAjuste
  observacion: string
  estado: EstadoAjuste
  valor_total: Decimal | null
  solicitado_por: string
  resuelto_por: string | null
  resuelto_at: string | null
  resolucion_nota: string | null
  conteo_id: string | null
  lineas: AjusteLinea[]
}

export interface ConteoLinea {
  producto_id: string
  producto_sku: string
  producto_nombre: string
  unidad_base: string
  controla_vencimiento: boolean
  cantidad_sistema: Decimal
  cantidad_contada: Decimal | null
  diferencia: Decimal | null
  vencimiento: string | null
  valor_diferencia: Decimal | null
}

export interface Conteo {
  id: string
  numero: number
  fecha: string
  ubicacion: Referencia
  estado: 'ABIERTO' | 'APROBADO' | 'ANULADO'
  observaciones: string | null
  usuario_nombre: string
  aprobado_at: string | null
  ajuste_id: string | null
  lineas: ConteoLinea[]
}

export const NOMBRE_MOTIVO: Record<MotivoAjuste, string> = {
  MERMA: 'Merma',
  ROTURA: 'Rotura / mal estado',
  VENCIMIENTO: 'Vencimiento',
  CONTEO_FISICO: 'Conteo físico',
  CORRECCION: 'Corrección',
  OTRO: 'Otro',
}

export const NOMBRE_MOVIMIENTO: Record<TipoMovimiento, string> = {
  COMPRA: 'Compra',
  VENTA: 'Venta',
  TRANSFERENCIA_SALIDA: 'Transferencia (salida)',
  TRANSFERENCIA_ENTRADA: 'Transferencia (entrada)',
  AJUSTE_POSITIVO: 'Ajuste (+)',
  AJUSTE_NEGATIVO: 'Ajuste (−)',
  DEVOLUCION_CLIENTE: 'Devolución de cliente',
  DEVOLUCION_PROVEEDOR: 'Devolución a proveedor',
  ANULACION: 'Anulación',
}

// ---------------------------------------------------------------- pedidos

export type EstadoPedido = 'BORRADOR' | 'CONFIRMADO' | 'ALISTADO' | 'ENTREGADO' | 'ANULADO'

export const NOMBRE_ESTADO_PEDIDO: Record<EstadoPedido, string> = {
  BORRADOR: 'Borrador',
  CONFIRMADO: 'Confirmado',
  ALISTADO: 'Alistado',
  ENTREGADO: 'Entregado',
  ANULADO: 'Anulado',
}

export interface PedidoResumen {
  id: string
  numero: number
  estado: EstadoPedido
  numero_oc: string | null
  fecha_oc: string | null
  fecha_entrega: string | null
  cadena: Referencia | null
  sucursal_cliente: Referencia | null
  ubicacion: Referencia
  responsable_id: string
  responsable_nombre: string
  total_oc: Decimal | null
  total_calculado: Decimal
  lineas: number
  documentos: number
  created_at: string
  ganancia: Decimal | null
  margen: Decimal | null
}

export interface Validacion {
  nivel: 'error' | 'aviso'
  mensaje: string
  linea_id: string | null
}

export interface DocumentoPedido {
  id: string
  nombre: string
  tipo_mime: string
  tamano: number
}

export interface LotePedido {
  lote_id: string
  codigo: string | null
  vencimiento: string | null
  cantidad: Decimal
  devuelta: Decimal
}

export interface PedidoLinea {
  id: string
  orden: number
  codigo_cliente: string | null
  descripcion_cliente: string
  producto: Producto | null
  cantidad_oc: Decimal
  precio_oc: Decimal
  total_linea_oc: Decimal | null
  total_calculado: Decimal
  cantidad_confirmada: Decimal
  cantidad_alistada: Decimal | null
  cantidad_merma: Decimal
  cantidad_devuelta: Decimal
  disponible: Decimal | null
  disponible_depositos: Decimal | null
  precio_anterior: Decimal | null
  precio_anterior_fecha: string | null
  precio_anterior_pedido: number | null
  lotes: LotePedido[]
  costo_unitario: Decimal | null
  costo_total: Decimal | null
  ingreso: Decimal | null
  ganancia: Decimal | null
  margen: Decimal | null
  confianza: Record<string, number> | null
}

export interface EventoPedido {
  tipo: string
  usuario_nombre: string
  fecha: string
  detalle: Record<string, unknown> | null
}

export interface DevolucionPedido {
  id: string
  numero: number
  fecha: string
  motivo: string
  usuario_nombre: string
  lineas: { linea_id: string; descripcion: string; cantidad: Decimal }[]
}

export interface PedidoDetalle extends PedidoResumen {
  emisor: string | null
  observaciones: string | null
  detalle_lineas: PedidoLinea[]
  detalle_documentos: DocumentoPedido[]
  eventos: EventoPedido[]
  validaciones: Validacion[]
  mermas: { id: string; numero: number; estado: EstadoAjuste }[]
  devoluciones: DevolucionPedido[]
  anulacion_motivo: string | null
  anulado_desde: EstadoPedido | null
  receptor_nombre: string | null
  entrega_observacion: string | null
  constancia_foto_id: string | null
  constancia_firma_id: string | null
  entregado_at: string | null
  ingreso: Decimal | null
  costo: Decimal | null
  confianza: (Record<string, unknown> & { avisos?: string[]; destino_texto?: string }) | null
  lectura: LecturaOC | null
}

export type EstadoLectura = 'PENDIENTE' | 'PROCESANDO' | 'COMPLETADA' | 'FALLIDA'

export interface LecturaOC {
  id: string
  estado: EstadoLectura
  plantilla: string | null
  motor: string | null
  confianza: Decimal | null
  aritmetica_ok: boolean | null
  aplicada: boolean
  error: string | null
  duracion_ms: number | null
  precision: Decimal | null
  created_at: string
  terminada_at: string | null
}

export interface Sugerencia {
  producto: Producto
  fuente: 'equivalencia' | 'codigo' | 'similitud'
  puntaje: number
}

// ---------------------------------------------------------------- reportes (Fase 3)

export type TipoDato = 'texto' | 'entero' | 'cantidad' | 'dinero' | 'porcentaje' | 'fecha'

export interface Kpi {
  clave: string
  titulo: string
  tipo: TipoDato
  valor: string | number | null
  anterior: string | number | null
  variacion: string | null
}

export interface ColumnaReporte {
  clave: string
  titulo: string
  tipo: TipoDato
}

export type FilaReporte = Record<string, string | number | null>

export interface TablaReporte {
  clave: string
  titulo: string
  descripcion: string | null
  columnas: ColumnaReporte[]
  filas: FilaReporte[]
}

export interface SerieReporte {
  clave: string
  titulo: string
  tipo: TipoDato
  forma: 'linea' | 'barras'
  eje: 'tiempo' | 'categoria'
  claves: ColumnaReporte[]
  puntos: FilaReporte[]
}

export interface Reporte {
  clave: string
  titulo: string
  descripcion: string
  filtros_texto: string[]
  con_rentabilidad: boolean
  kpis: Kpi[]
  series: SerieReporte[]
  tablas: TablaReporte[]
}

// ---------------------------------------------------------------- alertas y reposición (Fase 4)

export type SeveridadAlerta = 'INFO' | 'AVISO' | 'CRITICA'
export type Confianza = 'BAJA' | 'MEDIA' | 'ALTA'

export interface Alerta {
  id: string
  tipo: string
  severidad: SeveridadAlerta
  titulo: string
  mensaje: string
  enlace: string | null
  ubicacion: string | null
  producto: string | null
  datos: Record<string, unknown>
  auto_resolver: boolean
  estado: 'ACTIVA' | 'RESUELTA'
  creada_at: string
  resuelta_at: string | null
  resuelta_por: string | null
  leida: boolean
}

export interface ResumenAlertas {
  no_leidas: number
  criticas: number
}

export interface ParametrosAlertas {
  dias_entrega_proveedor: number
  dias_reposicion_sucursal: number
  cobertura_sucursal_dias: number
  cobertura_deposito_dias: number
  margen_minimo: number
  dias_sin_movimiento: number
  dias_aviso_vencimiento: number
  diferencia_conteo_pct: number
  sobre_stock_veces: number
}

export interface Referencia {
  id: string
  nombre: string
}

export interface FilaReposicion {
  ubicacion: Referencia
  producto: Referencia
  sku: string
  unidad: string
  disponible: Decimal
  demanda_semanal: Decimal
  cobertura_dias: Decimal | null
  stock_seguridad: Decimal
  punto_reorden: Decimal
  objetivo: Decimal
  confianza: Confianza
  metodo: string
  semanas: number
  con_limites: boolean
}

export interface SugerenciaTransferencia extends FilaReposicion {
  origen: Referencia
  origen_disponible: Decimal
  cantidad: Decimal
  presentacion: string
  cantidad_presentacion: Decimal
  insuficiente: boolean
}

export interface SugerenciaCompra extends FilaReposicion {
  proveedor: Referencia | null
  dias_entrega: number
  fecha: string
  cantidad: Decimal
  presentacion: string
  cantidad_presentacion: Decimal
  costo_estimado: Decimal | null
}

export interface PronosticoProducto {
  producto: Referencia
  ubicacion: Referencia
  metodo: string
  confianza: Confianza
  semanas: number
  demanda_semanal: Decimal
  error_medio: Decimal | null
  historial: number[]
  calculado_at: string | null
}

// ================================================================ finanzas (Fase 5)

export type EstadoCuenta = 'PENDIENTE' | 'PARCIAL' | 'SALDADA' | 'A_FAVOR'
export type EstadoRegistro = 'REGISTRADO' | 'ANULADO'

export interface CuentaPorCobrar {
  pedido_id: string
  numero: number
  numero_oc: string | null
  cadena: Referencia
  sucursal: string | null
  fecha: string
  vencimiento: string
  monto: Decimal
  cobrado: Decimal
  diferencia: Decimal
  saldo: Decimal
  estado: EstadoCuenta
  dias_vencida: number
}

export interface ResumenCadena {
  cadena: Referencia
  pedidos_pendientes: number
  pendiente: Decimal
  vencido: Decimal
  a_favor: Decimal
  mas_antiguo: string | null
}

export interface PorCobrar {
  total_pendiente: Decimal
  total_vencido: Decimal
  cobrado_mes: Decimal
  cadenas: ResumenCadena[]
  cuentas: CuentaPorCobrar[]
}

export interface CobroResumen {
  id: string
  numero: number
  cadena: Referencia
  fecha: string
  monto: Decimal
  diferencias: Decimal
  banco: string | null
  referencia: string | null
  estado: EstadoRegistro
  es_cierre: boolean
  pedidos: number
  usuario_nombre: string
  created_at: string
}

export interface CobroDetalle extends CobroResumen {
  observaciones: string | null
  comprobante_id: string | null
  comprobante_nombre: string | null
  anulacion_motivo: string | null
  anulado_at: string | null
  detalles: {
    pedido_id: string
    pedido_numero: number
    numero_oc: string | null
    sucursal: string | null
    monto: Decimal
    diferencia: Decimal
    motivo_diferencia: string | null
  }[]
}

export interface CategoriaGasto {
  id: string
  nombre: string
  factura_habitual: boolean
  activo: boolean
}

export interface Gasto {
  id: string
  numero: number
  fecha: string
  categoria: Referencia
  ubicacion: Referencia | null
  beneficiario: string | null
  descripcion: string | null
  monto: Decimal
  con_factura: boolean
  numero_factura: string | null
  comprobante_id: string | null
  comprobante_nombre: string | null
  estado: EstadoRegistro
  anulacion_motivo: string | null
  usuario_nombre: string
  created_at: string
}

export interface PaginaGastos extends Pagina<Gasto> {
  suma: Decimal
  por_categoria: { categoria: Referencia; total: Decimal }[]
}

export interface CompraPorPagar {
  id: string
  numero: number
  fecha: string
  proveedor: Referencia
  numero_documento: string | null
  total: Decimal
  fecha_vencimiento: string | null
  dias_para_vencer: number | null
}

export interface ImpuestoMes {
  mes: string
  ventas: Decimal
  iva_debito: Decimal
  compras_con_factura: Decimal
  gastos_con_factura: Decimal
  iva_credito: Decimal
  saldo_anterior: Decimal
  iva_pagar: Decimal
  saldo_siguiente: Decimal
  it: Decimal
  total_pagar: Decimal
}

export interface ParametrosFinanzas {
  dias_credito: number
  iva_pct: Decimal
  it_pct: Decimal
}
