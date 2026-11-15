import { useQuery } from '@tanstack/react-query'
import {
  AlertTriangle,
  ArrowLeftRight,
  ArrowRight,
  Banknote,
  Bell,
  Boxes,
  ChartLine,
  CheckCircle2,
  ClipboardCheck,
  ClipboardList,
  Circle,
  MapPin,
  Package,
  PackageCheck,
  Receipt,
  ShoppingCart,
  Store,
  Truck,
  Users,
  Wallet,
  type LucideIcon,
} from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { Tarjeta } from '../components/ui'
import { api } from '../lib/api'
import { formatearBs, formatearDia, hoyLaPaz } from '../lib/formato'
import { PERMISOS_PEDIDOS, usePuede, usePuedeAlguno, useYo } from '../lib/sesion'
import {
  NOMBRE_ESTADO_PEDIDO,
  type Cadena,
  type CompraResumen,
  type EstadoPedido,
  type Pagina,
  type PedidoResumen,
  type PorCobrar,
  type Producto,
  type Proveedor,
  type Reporte,
  type ResumenAlertas,
  type Ubicacion,
  type Usuario,
} from '../lib/tipos'

const zona = 'America/La_Paz'
const fechaLarga = new Intl.DateTimeFormat('es-BO', { timeZone: zona, weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })

function saludo(): string {
  const hora = Number(new Intl.DateTimeFormat('en-GB', { timeZone: zona, hour: 'numeric', hourCycle: 'h23' }).format(new Date()))
  return hora < 12 ? 'Buenos días' : hora < 19 ? 'Buenas tardes' : 'Buenas noches'
}

/** Pantalla de inicio: lo que hay que atender hoy, accesos rápidos y primeros pasos. */
export function Inicio() {
  const { data: yo } = useYo()
  const puede = usePuede()
  const puedeAlguno = usePuedeAlguno()
  const verPedidos = puedeAlguno(PERMISOS_PEDIDOS)
  const alertas = useQuery({ queryKey: ['alertas', 'resumen'], queryFn: () => api<ResumenAlertas>('/alertas/resumen') })
  // Se calculan una vez al abrir la pantalla.
  const [{ fecha, hola }] = useState(() => ({ fecha: fechaLarga.format(new Date()), hola: saludo() }))

  return (
    <div className="space-y-6">
      <section className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-[#1d4ed8] to-[#1e3a8a] p-6 text-white shadow-sm sm:p-8">
        <div aria-hidden className="absolute -top-16 -right-10 size-56 rounded-full bg-white/10" />
        <div aria-hidden className="absolute -right-24 -bottom-24 size-64 rounded-full bg-white/5" />
        <p className="relative text-sm text-blue-100 first-letter:uppercase">{fecha}</p>
        <h1 className="relative mt-1 text-2xl font-semibold tracking-tight sm:text-3xl">
          {hola}, {yo?.nombre ?? ''}
        </h1>
        <p className="relative mt-2 max-w-xl text-sm text-blue-100">
          Este es el resumen de hoy: pedidos por atender, avisos del sistema y lo que falta cobrar.
        </p>
        {(alertas.data?.criticas ?? 0) > 0 && (
          <Link
            to="/alertas"
            className="relative mt-4 inline-flex items-center gap-2 rounded-lg bg-white/15 px-3 py-2 text-sm font-medium hover:bg-white/25"
          >
            <AlertTriangle size={16} /> Hay {alertas.data?.criticas} alerta(s) crítica(s) por revisar
            <ArrowRight size={14} />
          </Link>
        )}
      </section>

      <PrimerosPasos />

      <section aria-label="Resumen" className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {verPedidos && <CifraPedidos estado="BORRADOR" titulo="Por revisar y confirmar" icono={ClipboardList} />}
        {verPedidos && <CifraPedidos estado="CONFIRMADO" titulo="Por alistar" icono={PackageCheck} />}
        {verPedidos && <CifraPedidos estado="ALISTADO" titulo="Por entregar" icono={Truck} />}
        <Cifra
          titulo="Alertas sin leer"
          valor={alertas.data ? String(alertas.data.no_leidas) : '…'}
          icono={Bell}
          a="/alertas"
          tono={(alertas.data?.criticas ?? 0) > 0 ? 'rojo' : undefined}
        />
        {puede('finanzas.ver') && <CifraPorCobrar />}
        {puede('reportes.rentabilidad') && <CifraVentasMes />}
      </section>

      <AccesosRapidos />

      {verPedidos && <UltimosPedidos />}
    </div>
  )
}

// ================================================================ cifras

function Cifra({
  titulo,
  valor,
  detalle,
  icono: Icono,
  a,
  tono,
}: {
  titulo: string
  valor: string
  detalle?: string
  icono: LucideIcon
  a: string
  tono?: 'rojo'
}) {
  return (
    <Link to={a} className="group block focus-visible:outline-2 focus-visible:outline-marca-600">
      <Tarjeta className="h-full p-4 transition-colors group-hover:border-marca-200">
        <div className="flex items-start justify-between gap-2">
          <p className="text-xs font-medium text-slate-500">{titulo}</p>
          <span className={`rounded-lg p-1.5 ${tono === 'rojo' ? 'bg-red-50 text-red-700' : 'bg-marca-50 text-marca-700'}`}>
            <Icono size={16} aria-hidden />
          </span>
        </div>
        <p className={`mt-2 text-2xl font-semibold tabular-nums ${tono === 'rojo' ? 'text-red-700' : 'text-slate-900'}`}>{valor}</p>
        {detalle && <p className="mt-1 text-xs text-slate-500">{detalle}</p>}
      </Tarjeta>
    </Link>
  )
}

function CifraPedidos({ estado, titulo, icono }: { estado: EstadoPedido; titulo: string; icono: LucideIcon }) {
  const datos = useQuery({
    queryKey: ['inicio', 'pedidos', estado],
    queryFn: () => api<Pagina<PedidoResumen>>('/pedidos', { params: { estado, tamano: 1 } }),
  })
  return <Cifra titulo={titulo} valor={datos.data ? String(datos.data.total) : '…'} icono={icono} a={`/pedidos?estado=${estado}`} />
}

function CifraPorCobrar() {
  const datos = useQuery({ queryKey: ['por-cobrar', '', false], queryFn: () => api<PorCobrar>('/finanzas/por-cobrar') })
  const vencido = Number(datos.data?.total_vencido ?? 0)
  return (
    <Cifra
      titulo="Por cobrar a supermercados"
      valor={datos.data ? formatearBs(datos.data.total_pendiente) : '…'}
      detalle={vencido > 0 ? `Vencido: ${formatearBs(vencido)}` : 'Nada vencido'}
      icono={Wallet}
      a="/finanzas"
      tono={vencido > 0 ? 'rojo' : undefined}
    />
  )
}

function CifraVentasMes() {
  const hoy = hoyLaPaz()
  const datos = useQuery({
    queryKey: ['inicio', 'ventas-mes', hoy],
    queryFn: () => api<Reporte>('/reportes/ganancias', { params: { desde: `${hoy.slice(0, 8)}01`, hasta: hoy, agrupacion: 'mes' } }),
  })
  const kpi = (clave: string) => datos.data?.kpis.find((k) => k.clave === clave)?.valor
  const ganancia = kpi('ganancia')
  return (
    <Cifra
      titulo="Ventas de este mes"
      valor={datos.data ? formatearBs(kpi('ingreso') ?? 0) : '…'}
      detalle={ganancia !== undefined && ganancia !== null ? `Ganancia: ${formatearBs(ganancia)}` : undefined}
      icono={ChartLine}
      a="/reportes?r=ganancias"
    />
  )
}

// ================================================================ primeros pasos

interface Paso {
  titulo: string
  detalle: string
  a: string
  icono: LucideIcon
  permiso: string
  hecho: boolean | undefined
}

/** Lista para empezar a usar el sistema con datos reales. Desaparece cuando todo está hecho. */
function PrimerosPasos() {
  const puede = usePuede()
  const ubicaciones = useQuery({ queryKey: ['ubicaciones'], queryFn: () => api<Ubicacion[]>('/ubicaciones') })
  const proveedores = useQuery({ queryKey: ['proveedores'], queryFn: () => api<Proveedor[]>('/proveedores') })
  const cadenas = useQuery({ queryKey: ['cadenas'], queryFn: () => api<Cadena[]>('/cadenas') })
  const productos = useQuery({
    queryKey: ['inicio', 'productos'],
    queryFn: () => api<Pagina<Producto>>('/productos', { params: { tamano: 1 } }),
    enabled: puede('catalogo.ver'),
  })
  const compras = useQuery({
    queryKey: ['inicio', 'compras'],
    queryFn: () => api<Pagina<CompraResumen>>('/compras', { params: { tamano: 1 } }),
    enabled: puede('compras.registrar'),
  })
  const usuarios = useQuery({ queryKey: ['usuarios'], queryFn: () => api<Usuario[]>('/usuarios'), enabled: puede('usuarios.ver') })

  const pasos: Paso[] = (
    [
      {
        titulo: 'Crear depósitos y sucursales',
        detalle: 'Dónde se guarda y desde dónde se despacha la mercadería.',
        a: '/ubicaciones',
        icono: MapPin,
        permiso: 'ubicaciones.gestionar',
        hecho: ubicaciones.data && ubicaciones.data.length > 0,
      },
      {
        titulo: 'Registrar proveedores',
        detalle: 'A quién se le compra, con sus días de entrega.',
        a: '/proveedores',
        icono: Truck,
        permiso: 'proveedores.gestionar',
        hecho: proveedores.data && proveedores.data.length > 0,
      },
      {
        titulo: 'Cargar productos',
        detalle: 'Con su código de fábrica y presentaciones (fardo, caja).',
        a: '/productos',
        icono: Package,
        permiso: 'catalogo.gestionar',
        hecho: productos.data && productos.data.total > 0,
      },
      {
        titulo: 'Registrar clientes',
        detalle: 'Las cadenas (Hipermaxi…) y sus sucursales de entrega.',
        a: '/clientes',
        icono: Store,
        permiso: 'clientes.gestionar',
        hecho: cadenas.data && cadenas.data.length > 0,
      },
      {
        titulo: 'Cargar el stock inicial',
        detalle: 'Registre una compra con lo que hay hoy en cada depósito.',
        a: '/compras/nueva',
        icono: ShoppingCart,
        permiso: 'compras.registrar',
        hecho: compras.data && compras.data.total > 0,
      },
      {
        titulo: 'Crear los usuarios del equipo',
        detalle: 'Administradores y encargados, cada uno con su rol.',
        a: '/usuarios',
        icono: Users,
        permiso: 'usuarios.gestionar',
        hecho: usuarios.data && usuarios.data.length > 1,
      },
    ] satisfies Paso[]
  ).filter((p) => puede(p.permiso))

  if (pasos.length === 0 || pasos.some((p) => p.hecho === undefined) || pasos.every((p) => p.hecho)) return null
  const hechos = pasos.filter((p) => p.hecho).length

  return (
    <Tarjeta className="p-5">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 className="font-semibold">Primeros pasos</h2>
          <p className="text-sm text-slate-500">Para empezar a trabajar con los datos de la empresa.</p>
        </div>
        <p className="text-sm font-medium text-slate-600">
          {hechos} de {pasos.length} listos
        </p>
      </div>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-100" role="progressbar" aria-valuenow={hechos} aria-valuemin={0} aria-valuemax={pasos.length}>
        <div className="h-full rounded-full bg-emerald-600 transition-all" style={{ width: `${(hechos / pasos.length) * 100}%` }} />
      </div>
      <ol className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {pasos.map((p) => (
          <li key={p.a}>
            <Link
              to={p.a}
              className={`flex h-full items-start gap-3 rounded-lg border p-3 transition-colors ${
                p.hecho ? 'border-slate-200 bg-slate-50' : 'border-slate-200 hover:border-marca-200 hover:bg-marca-50'
              }`}
            >
              {p.hecho ? (
                <CheckCircle2 size={20} className="mt-0.5 shrink-0 text-emerald-600" aria-label="Listo" />
              ) : (
                <Circle size={20} className="mt-0.5 shrink-0 text-slate-400" aria-label="Pendiente" />
              )}
              <span>
                <span className={`block text-sm font-medium ${p.hecho ? 'text-slate-500 line-through' : 'text-slate-900'}`}>{p.titulo}</span>
                <span className="block text-xs text-slate-500">{p.detalle}</span>
              </span>
            </Link>
          </li>
        ))}
      </ol>
    </Tarjeta>
  )
}

// ================================================================ accesos rápidos

interface Acceso {
  texto: string
  a: string
  icono: LucideIcon
  permiso: string | string[]
}

const ACCESOS: Acceso[] = [
  { texto: 'Nuevo pedido', a: '/pedidos/nuevo', icono: ClipboardList, permiso: 'pedidos.escanear' },
  { texto: 'Ver stock', a: '/inventario', icono: Boxes, permiso: 'inventario.ver' },
  { texto: 'Registrar compra', a: '/compras/nueva', icono: ShoppingCart, permiso: 'compras.registrar' },
  { texto: 'Transferir', a: '/transferencias/nueva', icono: ArrowLeftRight, permiso: 'inventario.transferir' },
  { texto: 'Conteo físico', a: '/conteos', icono: ClipboardCheck, permiso: 'inventario.ajustar' },
  { texto: 'Registrar cobro', a: '/finanzas/cobros/nuevo', icono: Banknote, permiso: 'finanzas.cobros' },
  { texto: 'Registrar gasto', a: '/finanzas?pestana=gastos', icono: Receipt, permiso: 'finanzas.gastos' },
  { texto: 'Reportes', a: '/reportes', icono: ChartLine, permiso: ['reportes.operativos', 'reportes.rentabilidad', 'finanzas.ver'] },
]

function AccesosRapidos() {
  const puedeAlguno = usePuedeAlguno()
  const accesos = ACCESOS.filter((a) => puedeAlguno(a.permiso))
  if (accesos.length === 0) return null
  return (
    <section>
      <h2 className="mb-2 text-sm font-semibold text-slate-800">Accesos rápidos</h2>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {accesos.map((a) => (
          <Link
            key={a.a}
            to={a.a}
            className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-3 text-sm font-medium text-slate-800 shadow-sm transition-colors hover:border-marca-200 hover:bg-marca-50"
          >
            <span className="rounded-lg bg-marca-50 p-2 text-marca-700">
              <a.icono size={18} aria-hidden />
            </span>
            {a.texto}
          </Link>
        ))}
      </div>
    </section>
  )
}

// ================================================================ últimos pedidos

const TONO_ESTADO: Record<EstadoPedido, string> = {
  BORRADOR: 'bg-slate-100 text-slate-700',
  CONFIRMADO: 'bg-marca-100 text-marca-800',
  ALISTADO: 'bg-amber-100 text-amber-800',
  ENTREGADO: 'bg-emerald-100 text-emerald-800',
  ANULADO: 'bg-red-100 text-red-800',
}

function UltimosPedidos() {
  const pedidos = useQuery({
    queryKey: ['inicio', 'ultimos-pedidos'],
    queryFn: () => api<Pagina<PedidoResumen>>('/pedidos', { params: { tamano: 6 } }),
  })
  return (
    <section>
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-800">Últimos pedidos</h2>
        <Link to="/pedidos" className="inline-flex items-center gap-1 text-sm text-marca-700 hover:underline">
          Ver todos <ArrowRight size={14} />
        </Link>
      </div>
      {pedidos.data?.items.length === 0 ? (
        <Tarjeta className="p-6 text-center text-sm text-slate-500">
          Todavía no hay pedidos. Cuando llegue una nota de recepción, súbala desde{' '}
          <Link to="/pedidos/nuevo" className="text-marca-700 underline">
            Nuevo pedido
          </Link>
          .
        </Tarjeta>
      ) : (
        <Tarjeta className="divide-y divide-slate-100">
          {pedidos.data?.items.map((p) => (
            <Link key={p.id} to={`/pedidos/${p.id}`} className="flex items-center gap-3 px-4 py-3 hover:bg-slate-50">
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-slate-900">
                  #{p.numero} · {p.sucursal_cliente?.nombre ?? p.cadena?.nombre ?? 'Sin cliente'}
                </p>
                <p className="truncate text-xs text-slate-500">
                  {p.numero_oc ? `O/C ${p.numero_oc} · ` : ''}
                  {formatearDia(p.fecha_oc ?? p.created_at.slice(0, 10))}
                </p>
              </div>
              <span className="hidden text-sm tabular-nums text-slate-700 sm:inline">{formatearBs(p.total_oc ?? p.total_calculado)}</span>
              <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${TONO_ESTADO[p.estado]}`}>{NOMBRE_ESTADO_PEDIDO[p.estado]}</span>
            </Link>
          ))}
        </Tarjeta>
      )}
    </section>
  )
}
