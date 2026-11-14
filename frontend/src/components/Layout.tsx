import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Boxes,
  ClipboardList,
  History,
  House,
  LogOut,
  Menu,
  MapPin,
  ChartLine,
  ShieldCheck,
  Users,
  KeyRound,
  type LucideIcon,
} from 'lucide-react'
import { useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router'
import { api } from '../lib/api'
import { CLAVE_YO, usePuede, useYo } from '../lib/sesion'
import { CambiarPassword } from './CambiarPassword'
import { Boton } from './ui'

interface Enlace {
  a: string
  texto: string
  icono: LucideIcon
  permiso?: string
  proximamente?: boolean
}

const ENLACES: Enlace[] = [
  { a: '/', texto: 'Inicio', icono: House },
  { a: '/inventario', texto: 'Inventario', icono: Boxes, proximamente: true },
  { a: '/pedidos', texto: 'Pedidos', icono: ClipboardList, proximamente: true },
  { a: '/reportes', texto: 'Reportes', icono: ChartLine, proximamente: true },
  { a: '/usuarios', texto: 'Usuarios', icono: Users, permiso: 'usuarios.ver' },
  { a: '/roles', texto: 'Roles y permisos', icono: ShieldCheck, permiso: 'roles.ver' },
  { a: '/ubicaciones', texto: 'Ubicaciones', icono: MapPin, permiso: 'ubicaciones.gestionar' },
  { a: '/auditoria', texto: 'Auditoría', icono: History, permiso: 'auditoria.ver' },
]

export function Layout() {
  const { data: yo } = useYo()
  const puede = usePuede()
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

  const enlaces = ENLACES.filter((e) => !e.permiso || puede(e.permiso))

  const navegacion = (
    <nav className="flex flex-col gap-1 p-3">
      {enlaces.map((e) =>
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
    </nav>
  )

  return (
    <div className="min-h-dvh lg:grid lg:grid-cols-[16rem_1fr]">
      {/* Barra lateral (escritorio) / cajón (móvil) */}
      <aside
        className={`fixed inset-y-0 left-0 z-30 w-64 transform border-r border-slate-200 bg-white
          transition-transform lg:static lg:translate-x-0 ${menuAbierto ? 'translate-x-0' : '-translate-x-full'}`}
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
        <main className="mx-auto w-full max-w-6xl flex-1 p-4 sm:p-6">
          <Outlet />
        </main>
      </div>
      <CambiarPassword abierto={cambiandoClave} onCerrar={() => setCambiandoClave(false)} />
    </div>
  )
}
