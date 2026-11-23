import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeftRight,
  Boxes,
  ChartLine,
  ClipboardCheck,
  ClipboardList,
  History,
  House,
  MapPin,
  Menu,
  Package,
  PackageCheck,
  ShieldCheck,
  ShoppingCart,
  SlidersHorizontal,
  Store,
  Truck,
  Users,
  Wallet,
  X,
  type LucideIcon,
} from 'lucide-react'
import { domAnimation, LazyMotion, m, MotionConfig } from 'motion/react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router'
import { api } from '../lib/api'
import { CLAVE_YO, PERMISOS_PEDIDOS, PERMISOS_REPORTES, PERMISOS_REPOSICION, usePuedeAlguno, useYo } from '../lib/sesion'
import { Campana } from './Campana'
import { CambiarPassword } from './CambiarPassword'
import { BotonTema, Marca, MenuUsuario, SelectorIdioma } from './Controles'

interface Enlace {
  a: string
  texto: string
  icono: LucideIcon
  permiso?: string | string[]
}

const SECCIONES: { titulo?: string; enlaces: Enlace[] }[] = [
  { enlaces: [{ a: '/', texto: 'Inicio', icono: House }] },
  {
    titulo: 'Operación',
    enlaces: [
      { a: '/pedidos', texto: 'Pedidos', icono: ClipboardList, permiso: PERMISOS_PEDIDOS },
      { a: '/inventario', texto: 'Stock', icono: Boxes, permiso: 'inventario.ver' },
      { a: '/reposicion', texto: 'Reposición', icono: PackageCheck, permiso: PERMISOS_REPOSICION },
      { a: '/compras', texto: 'Compras', icono: ShoppingCart, permiso: 'compras.registrar' },
      { a: '/transferencias', texto: 'Transferencias', icono: ArrowLeftRight, permiso: 'inventario.ver' },
      { a: '/ajustes', texto: 'Ajustes', icono: SlidersHorizontal, permiso: 'inventario.ver' },
      { a: '/conteos', texto: 'Conteos físicos', icono: ClipboardCheck, permiso: 'inventario.ver' },
    ],
  },
  {
    titulo: 'Catálogo',
    enlaces: [
      { a: '/productos', texto: 'Productos', icono: Package, permiso: 'catalogo.ver' },
      { a: '/proveedores', texto: 'Proveedores', icono: Truck, permiso: 'catalogo.ver' },
      { a: '/clientes', texto: 'Clientes', icono: Store, permiso: 'catalogo.ver' },
    ],
  },
  {
    titulo: 'Análisis',
    enlaces: [
      { a: '/reportes', texto: 'Reportes', icono: ChartLine, permiso: PERMISOS_REPORTES },
      { a: '/finanzas', texto: 'Finanzas', icono: Wallet, permiso: 'finanzas.ver' },
    ],
  },
  {
    titulo: 'Administración',
    enlaces: [
      { a: '/usuarios', texto: 'Usuarios', icono: Users, permiso: 'usuarios.ver' },
      { a: '/roles', texto: 'Roles y permisos', icono: ShieldCheck, permiso: 'roles.ver' },
      { a: '/ubicaciones', texto: 'Ubicaciones', icono: MapPin, permiso: 'ubicaciones.gestionar' },
      { a: '/auditoria', texto: 'Auditoría', icono: History, permiso: 'auditoria.ver' },
    ],
  },
]

export function Layout() {
  const { t } = useTranslation()
  const { data: yo } = useYo()
  const puede = usePuedeAlguno()
  const ubicacion = useLocation()
  const [menuAbierto, setMenuAbierto] = useState(false)
  const [cambiandoClave, setCambiandoClave] = useState(false)
  const queryClient = useQueryClient()
  const navegar = useNavigate()

  const salir = useMutation({
    mutationFn: () => api<void>('/auth/logout', { metodo: 'POST' }),
    onSettled: () => {
      queryClient.setQueryData(CLAVE_YO, null)
      queryClient.removeQueries({ predicate: (q) => q.queryKey[0] !== CLAVE_YO[0] })
      navegar('/login', { replace: true })
    },
  })

  const secciones = SECCIONES.map((s) => ({ ...s, enlaces: s.enlaces.filter((e) => !e.permiso || puede(e.permiso)) })).filter(
    (s) => s.enlaces.length > 0,
  )

  return (
    <MotionConfig reducedMotion="user">
      <LazyMotion features={domAnimation} strict>
        <a
          href="#contenido"
          className="fixed top-2 left-2 z-50 -translate-y-16 rounded-lg bg-acento px-3 py-2 text-sm font-medium text-sobre-acento shadow-lg transition-transform focus-visible:translate-y-0"
        >
          {t('Saltar al contenido')}
        </a>
        <div className="min-h-dvh lg:grid lg:grid-cols-[15.5rem_1fr]">
          {/* Barra lateral (escritorio) / cajón (móvil) */}
          <aside
            aria-label={t('Menú principal')}
            className={`fixed inset-y-0 left-0 z-30 flex w-64 flex-col border-r border-linea bg-superficie transition-transform duration-200 ease-salida lg:sticky lg:top-0 lg:h-dvh lg:w-auto lg:translate-x-0 ${
              menuAbierto ? 'translate-x-0 shadow-[var(--sombra-3)]' : '-translate-x-full'
            }`}
          >
            <div className="flex h-14 shrink-0 items-center gap-2.5 px-4">
              <Marca tamano={30} />
              <div className="min-w-0 leading-tight">
                <div className="truncate text-[15px] font-semibold tracking-[-0.2px]">{t('Inventario')}</div>
                <div className="truncate text-xs text-tinta-3">{t('Distribuidora')}</div>
              </div>
              <button
                type="button"
                className="ml-auto inline-grid size-9 place-items-center rounded-lg text-tinta-2 hover:bg-superficie-2 lg:hidden"
                onClick={() => setMenuAbierto(false)}
                aria-label={t('Cerrar menú')}
              >
                <X size={18} aria-hidden />
              </button>
            </div>
            <nav className="flex flex-1 flex-col overflow-y-auto overscroll-contain px-3 pt-1 pb-4">
              {secciones.map((s) => (
                <div key={s.titulo ?? 'inicio'} className="mb-1">
                  {s.titulo && <div className="px-2.5 pt-4 pb-1.5 text-[11px] font-semibold tracking-[0.6px] text-tinta-3 uppercase">{t(s.titulo)}</div>}
                  {s.enlaces.map((e) => (
                    <NavLink
                      key={e.a}
                      to={e.a}
                      end={e.a === '/'}
                      onClick={() => setMenuAbierto(false)}
                      className={({ isActive }) =>
                        `group relative flex min-h-9 items-center gap-2.5 rounded-lg px-2.5 text-sm font-medium transition-colors ${
                          isActive
                            ? 'bg-acento-suave text-acento before:absolute before:inset-y-2 before:-left-3 before:w-[3px] before:rounded-r-full before:bg-acento'
                            : 'text-tinta-2 hover:bg-superficie-2 hover:text-tinta'
                        }`
                      }
                    >
                      {({ isActive }) => (
                        <>
                          <e.icono size={17} aria-hidden className={isActive ? '' : 'text-tinta-3 group-hover:text-tinta-2'} />
                          {t(e.texto)}
                        </>
                      )}
                    </NavLink>
                  ))}
                </div>
              ))}
            </nav>
            <div className="border-t border-linea p-3 sm:hidden">
              <SelectorIdioma />
            </div>
          </aside>
          {menuAbierto && (
            <button
              type="button"
              aria-label={t('Cerrar menú')}
              className="fixed inset-0 z-20 bg-slate-900/40 backdrop-blur-[1px] lg:hidden"
              onClick={() => setMenuAbierto(false)}
            />
          )}

          <div className="flex min-w-0 flex-col">
            <header className="sticky top-0 z-10 flex h-14 items-center gap-2 border-b border-linea bg-superficie/85 px-3 backdrop-blur-md sm:px-5">
              <button
                type="button"
                className="inline-grid size-9 place-items-center rounded-lg text-tinta-2 hover:bg-superficie-2 lg:hidden"
                onClick={() => setMenuAbierto(true)}
                aria-label={t('Abrir menú')}
                aria-expanded={menuAbierto}
              >
                <Menu size={20} aria-hidden />
              </button>
              <div className="ml-auto flex items-center gap-1 sm:gap-1.5">
                <SelectorIdioma className="mr-1 hidden sm:inline-flex" />
                <BotonTema />
                <Campana />
                <MenuUsuario
                  nombre={yo?.nombre}
                  apellido={yo?.apellido}
                  roles={yo?.roles.map((r) => r.nombre).join(', ') ?? ''}
                  onCambiarClave={() => setCambiandoClave(true)}
                  onSalir={() => salir.mutate()}
                />
              </div>
            </header>
            <main id="contenido" tabIndex={-1} className="mx-auto w-full max-w-7xl flex-1 p-4 outline-none sm:p-6">
              <m.div
                key={ubicacion.pathname}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.2, ease: [0.2, 0, 0, 1] }}
              >
                <Outlet />
              </m.div>
            </main>
          </div>
          <CambiarPassword abierto={cambiandoClave} onCerrar={() => setCambiandoClave(false)} />
        </div>
      </LazyMotion>
    </MotionConfig>
  )
}
