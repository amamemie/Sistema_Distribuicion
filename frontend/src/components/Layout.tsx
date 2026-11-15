import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeftRight,
  Boxes,
  ChartLine,
  ClipboardCheck,
  ClipboardList,
  History,
  House,
  KeyRound,
  LogOut,
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
  type LucideIcon,
} from 'lucide-react'
import { useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router'
import { api } from '../lib/api'
import { CLAVE_YO, PERMISOS_PEDIDOS, PERMISOS_REPORTES, PERMISOS_REPOSICION, usePuedeAlguno, useYo } from '../lib/sesion'
import { Campana } from './Campana'
import { CambiarPassword } from './CambiarPassword'
import { Boton } from './ui'

interface Enlace {
  a: string
  texto: string
  icono: LucideIcon
  permiso?: string | string[]
  proximamente?: boolean
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
  const { data: yo } = useYo()
  const puede = usePuedeAlguno()
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

  const navegacion = (
    <nav className="flex flex-col gap-1 overflow-y-auto p-3">
      {secciones.map((s) => (
        <div key={s.titulo ?? 'inicio'} className="mb-2">
          {s.titulo && <div className="px-3 pt-2 pb-1 text-[11px] font-semibold tracking-wide text-slate-400 uppercase">{s.titulo}</div>}
      {s.enlaces.map((e) =>
        e.proximamente ? (
          <span
            key={e.a}
            className="flex items-center gap-3 rounded-md px-3 py-2 text-sm text-slate-400"
            title="Disponible en próximas fases"
          >
            <e.icono size={18} />
            {e.texto}
            <span className="ml-auto text-[10px] uppercase">pronto</span>
          </span>
        ) : (
          <NavLink
            key={e.a}
            to={e.a}
            end={e.a === '/'}
            onClick={() => setMenuAbierto(false)}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium ${
                isActive ? 'bg-marca-50 text-marca-800' : 'text-slate-700 hover:bg-slate-100'
              }`
            }
          >
            <e.icono size={18} />
            {e.texto}
          </NavLink>
        ),
      )}
        </div>
      ))}
    </nav>
  )

  return (
    <div className="min-h-dvh lg:grid lg:grid-cols-[16rem_1fr]">
      {/* Barra lateral (escritorio) / cajón (móvil) */}
      <aside
        className={`fixed inset-y-0 left-0 z-30 flex w-64 transform flex-col border-r border-slate-200 bg-white
          transition-transform lg:sticky lg:top-0 lg:h-dvh lg:translate-x-0 ${menuAbierto ? 'translate-x-0' : '-translate-x-full'}`}
      >
        <div className="flex h-16 items-center gap-2 border-b border-slate-200 px-5">
          <img src="/icono.svg" alt="" className="size-8" />
          <span className="font-semibold">Inventario</span>
        </div>
        {navegacion}
      </aside>
      {menuAbierto && (
        <button
          aria-label="Cerrar menú"
          className="fixed inset-0 z-20 bg-slate-900/40 lg:hidden"
          onClick={() => setMenuAbierto(false)}
        />
      )}

      <div className="flex min-w-0 flex-col">
        <header className="sticky top-0 z-10 flex h-16 items-center gap-3 border-b border-slate-200 bg-white/90 px-4 backdrop-blur">
          <Boton
            variante="fantasma"
            className="px-2 lg:hidden"
            onClick={() => setMenuAbierto(true)}
            aria-label="Abrir menú"
          >
            <Menu size={20} />
          </Boton>
          <div className="ml-auto flex items-center gap-2">
            <Campana />
            <div className="hidden text-right sm:block">
              <div className="text-sm font-medium">
                {yo?.nombre} {yo?.apellido}
              </div>
              <div className="text-xs text-slate-500">{yo?.roles.map((r) => r.nombre).join(', ')}</div>
            </div>
            <Boton
              variante="fantasma"
              className="px-2"
              onClick={() => setCambiandoClave(true)}
              aria-label="Cambiar contraseña"
              title="Cambiar contraseña"
            >
              <KeyRound size={18} />
            </Boton>
            <Boton
              variante="fantasma"
              className="px-2"
              onClick={() => salir.mutate()}
              aria-label="Cerrar sesión"
              title="Cerrar sesión"
            >
              <LogOut size={18} />
            </Boton>
          </div>
        </header>
        <main className="mx-auto w-full max-w-7xl flex-1 p-4 sm:p-6">
          <Outlet />
        </main>
      </div>
      <CambiarPassword abierto={cambiandoClave} onCerrar={() => setCambiandoClave(false)} />
    </div>
  )
}
