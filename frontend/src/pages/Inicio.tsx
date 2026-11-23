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
  Plus,
  Receipt,
  ShoppingCart,
  Store,
  Truck,
  Users,
  Wallet,
  type LucideIcon,
} from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { CifraAnimada } from '../components/Cifra'
import { Escena } from '../components/escena/Escena'
import { Insignia, Tarjeta } from '../components/ui'
import { api } from '../lib/api'
import { fechaLargaHoy, formatearBs, formatearCantidad, formatearDia, hoyLaPaz } from '../lib/formato'
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

function saludo(): string {
  const hora = Number(new Intl.DateTimeFormat('en-GB', { timeZone: 'America/La_Paz', hour: 'numeric', hourCycle: 'h23' }).format(new Date()))
  return hora < 12 ? 'Buenos días' : hora < 19 ? 'Buenas tardes' : 'Buenas noches'
}

/** Pantalla de inicio: lo que hay que atender hoy, accesos rápidos y primeros pasos. */
export function Inicio() {
  const { t } = useTranslation()
  const { data: yo } = useYo()
  const puede = usePuede()
  const puedeAlguno = usePuedeAlguno()
  const verPedidos = puedeAlguno(PERMISOS_PEDIDOS)
  const alertas = useQuery({ queryKey: ['alertas', 'resumen'], queryFn: () => api<ResumenAlertas>('/alertas/resumen') })
  // El saludo se calcula una vez al abrir la pantalla.
  const [hola] = useState(saludo)

  return (
    <div className="space-y-5">
      <Portada nombre={yo?.nombre ?? ''} hola={t(hola)} criticas={alertas.data?.criticas ?? 0} verPedidos={verPedidos} />

      <PrimerosPasos />

      <section aria-label={t('Resumen')} className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {verPedidos && <CifraPedidos estado="BORRADOR" titulo={t('Por revisar y confirmar')} icono={ClipboardList} />}
        {verPedidos && <CifraPedidos estado="CONFIRMADO" titulo={t('Por alistar')} icono={PackageCheck} />}
        {verPedidos && <CifraPedidos estado="ALISTADO" titulo={t('Por entregar')} icono={Truck} />}
        <Cifra
          titulo={t('Alertas sin leer')}
          numero={alertas.data?.no_leidas}
          formato={formatearCantidad}
          icono={Bell}
          a="/alertas"
          tono={(alertas.data?.criticas ?? 0) > 0 ? 'rojo' : undefined}
        />
        {puede('finanzas.ver') && <CifraPorCobrar />}
        {puede('reportes.rentabilidad') && <CifraVentasMes />}
      </section>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        {verPedidos && <UltimosPedidos />}
        <AccesosRapidos />
      </div>
    </div>
  )
}

// ================================================================ portada

function Portada({ nombre, hola, criticas, verPedidos }: { nombre: string; hola: string; criticas: number; verPedidos: boolean }) {
  const { t } = useTranslation()
  const puede = usePuede()
  const porEntregar = useQuery({
    queryKey: ['inicio', 'pedidos', 'ALISTADO'],
    queryFn: () => api<Pagina<PedidoResumen>>('/pedidos', { params: { estado: 'ALISTADO', tamano: 1 } }),
    enabled: verPedidos,
  })
  const deuda = useQuery({
    queryKey: ['por-cobrar', '', false],
    queryFn: () => api<PorCobrar>('/finanzas/por-cobrar'),
    enabled: puede('finanzas.ver'),
  })
  const partes: string[] = []
  if (porEntregar.data) partes.push(t('{{n}} pedido(s) por entregar', { n: porEntregar.data.total }))
  if (deuda.data && Number(deuda.data.total_pendiente) > 0) partes.push(t('{{monto}} por cobrar', { monto: formatearBs(deuda.data.total_pendiente) }))

  return (
    <section
      className="relative isolate overflow-hidden rounded-2xl border border-linea"
      style={{ background: 'radial-gradient(120% 120% at 10% 0%, var(--escena-fondo-1) 0%, var(--escena-fondo-2) 50%, var(--escena-fondo-3) 100%)' }}
    >
      <Escena variante="portada" className="pointer-events-none absolute inset-y-0 right-0 -z-10 hidden w-[58%] sm:block" />
      <div className="max-w-xl animate-[entra_.5s_var(--ease-entrada)_both] p-6 sm:p-8">
        <p className="text-[13px] text-tinta-3 first-letter:uppercase">{fechaLargaHoy()}</p>
        <h1 className="mt-1 text-[28px] leading-tight font-semibold tracking-[-0.8px] sm:text-[34px]">
          {hola}, {nombre}
        </h1>
        <p className="mt-2 text-[15px] text-tinta-2">
          {partes.length > 0 ? t('Hoy: {{resumen}}.', { resumen: partes.join(t(' y ')) }) : t('Este es el resumen de hoy: pedidos por atender, avisos y lo que falta cobrar.')}
        </p>
        <div className="mt-5 flex flex-wrap gap-2">
          {puede('pedidos.escanear') && (
            <Link to="/pedidos/nuevo" className="inline-flex min-h-10 items-center gap-2 rounded-lg bg-acento px-4 text-sm font-medium text-sobre-acento shadow-sm transition-colors hover:bg-acento-hover active:translate-y-px">
              <Plus size={16} aria-hidden /> {t('Nuevo pedido')}
            </Link>
          )}
          {puede('finanzas.cobros') && (
            <Link to="/finanzas/cobros/nuevo" className="inline-flex min-h-10 items-center gap-2 rounded-lg border border-linea bg-superficie px-4 text-sm font-medium text-tinta shadow-sm transition-colors hover:bg-superficie-2 active:translate-y-px">
              {t('Registrar cobro')}
            </Link>
          )}
        </div>
        {criticas > 0 && (
          <Link to="/alertas" className="mt-4 inline-flex items-center gap-2 rounded-lg bg-peligro-suave px-3 py-2 text-sm font-medium text-peligro transition-colors hover:brightness-95">
            <AlertTriangle size={16} aria-hidden /> {t('Hay {{n}} alerta(s) crítica(s) por revisar', { n: criticas })}
            <ArrowRight size={14} aria-hidden />
          </Link>
        )}
      </div>
    </section>
  )
}

// ================================================================ cifras

function Cifra({
  titulo,
  numero,
  formato,
  detalle,
  icono: Icono,
  a,
  tono,
}: {
  titulo: string
  numero: number | undefined
  formato: (n: number) => string
  detalle?: string
  icono: LucideIcon
  a: string
  tono?: 'rojo'
}) {
  return (
    <Link to={a} className="group block rounded-xl">
      <Tarjeta className="h-full p-4 transition-[transform,box-shadow,border-color] duration-150 ease-salida group-hover:-translate-y-0.5 group-hover:border-linea-fuerte/40 group-hover:shadow-(--sombra-2)">
        <div className="flex items-start justify-between gap-2">
          <p className="text-xs font-medium text-tinta-3">{titulo}</p>
          <span className={`inline-grid size-7 shrink-0 place-items-center rounded-lg ${tono === 'rojo' ? 'bg-peligro-suave text-peligro' : 'bg-acento-suave text-acento'}`}>
            <Icono size={15} aria-hidden />
          </span>
        </div>
        <p className={`mt-2 text-[26px] leading-tight font-semibold tracking-[-0.6px] ${tono === 'rojo' ? 'text-peligro' : 'text-tinta'}`}>
          {numero === undefined ? <span className="esqueleto inline-block h-7 w-16 rounded-md align-middle" /> : <CifraAnimada valor={numero} formato={formato} />}
        </p>
        {detalle && <p className={`mt-1 text-xs ${tono === 'rojo' ? 'text-peligro' : 'text-tinta-3'}`}>{detalle}</p>}
      </Tarjeta>
    </Link>
  )
}

function CifraPedidos({ estado, titulo, icono }: { estado: EstadoPedido; titulo: string; icono: LucideIcon }) {
  const datos = useQuery({
    queryKey: ['inicio', 'pedidos', estado],
    queryFn: () => api<Pagina<PedidoResumen>>('/pedidos', { params: { estado, tamano: 1 } }),
  })
  return <Cifra titulo={titulo} numero={datos.data?.total} formato={(n) => formatearCantidad(Math.round(n))} icono={icono} a={`/pedidos?estado=${estado}`} />
}

function CifraPorCobrar() {
  const { t } = useTranslation()
  const datos = useQuery({ queryKey: ['por-cobrar', '', false], queryFn: () => api<PorCobrar>('/finanzas/por-cobrar') })
  const vencido = Number(datos.data?.total_vencido ?? 0)
  return (
    <Cifra
      titulo={t('Por cobrar a supermercados')}
      numero={datos.data ? Number(datos.data.total_pendiente) : undefined}
      formato={formatearBs}
      detalle={datos.data ? (vencido > 0 ? t('Vencido: {{monto}}', { monto: formatearBs(vencido) }) : t('Nada vencido')) : undefined}
      icono={Wallet}
      a="/finanzas"
      tono={vencido > 0 ? 'rojo' : undefined}
    />
  )
}

function CifraVentasMes() {
  const { t } = useTranslation()
  const hoy = hoyLaPaz()
  const datos = useQuery({
    queryKey: ['inicio', 'ventas-mes', hoy],
    queryFn: () => api<Reporte>('/reportes/ganancias', { params: { desde: `${hoy.slice(0, 8)}01`, hasta: hoy, agrupacion: 'mes' } }),
  })
  const kpi = (clave: string) => datos.data?.kpis.find((k) => k.clave === clave)?.valor
  const ganancia = kpi('ganancia')
  return (
    <Cifra
      titulo={t('Ventas de este mes')}
      numero={datos.data ? Number(kpi('ingreso') ?? 0) : undefined}
      formato={formatearBs}
      detalle={ganancia !== undefined && ganancia !== null ? t('Ganancia: {{monto}}', { monto: formatearBs(ganancia) }) : undefined}
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
  const { t } = useTranslation()
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
          <h2 className="text-[17px] font-semibold tracking-[-0.2px]">{t('Primeros pasos')}</h2>
          <p className="text-sm text-tinta-3">{t('Para empezar a trabajar con los datos de la empresa.')}</p>
        </div>
        <p className="text-sm font-medium text-tinta-2 tabular-nums">{t('{{hechos}} de {{total}} listos', { hechos, total: pasos.length })}</p>
      </div>
      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-superficie-2" role="progressbar" aria-valuenow={hechos} aria-valuemin={0} aria-valuemax={pasos.length} aria-label={t('Primeros pasos')}>
        <div className="h-full rounded-full bg-acento transition-[width] duration-500 ease-salida" style={{ width: `${(hechos / pasos.length) * 100}%` }} />
      </div>
      <ol className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {pasos.map((p) => (
          <li key={p.a}>
            <Link
              to={p.a}
              className={`flex h-full items-start gap-3 rounded-lg border p-3 transition-colors ${
                p.hecho ? 'border-linea bg-superficie-2/60' : 'border-linea hover:border-acento/40 hover:bg-acento-suave'
              }`}
            >
              {p.hecho ? (
                <CheckCircle2 size={20} className="mt-0.5 shrink-0 text-exito" aria-label={t('Listo')} />
              ) : (
                <Circle size={20} className="mt-0.5 shrink-0 text-tinta-3" aria-label={t('Pendiente')} />
              )}
              <span>
                <span className={`block text-sm font-medium ${p.hecho ? 'text-tinta-3 line-through' : 'text-tinta'}`}>{t(p.titulo)}</span>
                <span className="block text-xs text-tinta-3">{t(p.detalle)}</span>
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
  const { t } = useTranslation()
  const puedeAlguno = usePuedeAlguno()
  const accesos = ACCESOS.filter((a) => puedeAlguno(a.permiso))
  if (accesos.length === 0) return null
  return (
    <section>
      <h2 className="mb-2 text-sm font-semibold text-tinta">{t('Accesos rápidos')}</h2>
      <div className="grid grid-cols-2 gap-2.5">
        {accesos.map((a) => (
          <Link
            key={a.a}
            to={a.a}
            className="group flex min-h-12 items-center gap-3 rounded-xl border border-linea bg-superficie p-2.5 text-sm font-medium text-tinta transition-[transform,box-shadow,border-color] duration-150 ease-salida hover:-translate-y-0.5 hover:border-linea-fuerte/40 hover:shadow-(--sombra-2)"
          >
            <span className="inline-grid size-8 shrink-0 place-items-center rounded-lg bg-acento-suave text-acento">
              <a.icono size={17} aria-hidden />
            </span>
            {t(a.texto)}
          </Link>
        ))}
      </div>
    </section>
  )
}

// ================================================================ últimos pedidos

const TONO_ESTADO: Record<EstadoPedido, 'gris' | 'azul' | 'ambar' | 'verde' | 'rojo'> = {
  BORRADOR: 'gris',
  CONFIRMADO: 'azul',
  ALISTADO: 'ambar',
  ENTREGADO: 'verde',
  ANULADO: 'rojo',
}

function UltimosPedidos() {
  const { t } = useTranslation()
  const pedidos = useQuery({
    queryKey: ['inicio', 'ultimos-pedidos'],
    queryFn: () => api<Pagina<PedidoResumen>>('/pedidos', { params: { tamano: 6 } }),
  })
  return (
    <section>
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-tinta">{t('Últimos pedidos')}</h2>
        <Link to="/pedidos" className="inline-flex items-center gap-1 text-sm font-medium text-acento hover:underline">
          {t('Ver todos')} <ArrowRight size={14} aria-hidden />
        </Link>
      </div>
      {pedidos.data?.items.length === 0 ? (
        <Tarjeta className="p-6 text-center text-sm text-tinta-3">
          {t('Todavía no hay pedidos. Cuando llegue una nota de recepción, súbala desde')}{' '}
          <Link to="/pedidos/nuevo" className="font-medium text-acento underline">
            {t('Nuevo pedido')}
          </Link>
          .
        </Tarjeta>
      ) : (
        <Tarjeta className="divide-y divide-linea overflow-hidden">
          {!pedidos.data &&
            Array.from({ length: 4 }, (_, i) => (
              <div key={i} className="flex items-center gap-3 px-4 py-3.5">
                <span className="esqueleto h-4 flex-1 rounded" />
                <span className="esqueleto h-4 w-20 rounded" />
              </div>
            ))}
          {pedidos.data?.items.map((p, i) => (
            <Link
              key={p.id}
              to={`/pedidos/${p.id}`}
              className="flex animate-[entra_.35s_var(--ease-entrada)_both] items-center gap-3 px-4 py-3 transition-colors hover:bg-superficie-2/60"
              style={{ animationDelay: `${Math.min(i, 7) * 30}ms` }}
            >
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-tinta">
                  #{p.numero} · <span translate="no">{p.sucursal_cliente?.nombre ?? p.cadena?.nombre ?? t('Sin cliente')}</span>
                </p>
                <p className="truncate text-xs text-tinta-3">
                  {p.numero_oc ? `O/C ${p.numero_oc} · ` : ''}
                  {formatearDia(p.fecha_oc ?? p.created_at.slice(0, 10))}
                </p>
              </div>
              <span className="hidden text-sm text-tinta-2 tabular-nums sm:inline">{formatearBs(p.total_oc ?? p.total_calculado)}</span>
              <Insignia tono={TONO_ESTADO[p.estado]}>{t(NOMBRE_ESTADO_PEDIDO[p.estado])}</Insignia>
            </Link>
          ))}
        </Tarjeta>
      )}
    </section>
  )
}
