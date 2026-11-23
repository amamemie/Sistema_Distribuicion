import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { lazy, StrictMode, Suspense, type ComponentType, type ReactNode } from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter, Link, RouterProvider } from 'react-router'
import { registerSW } from 'virtual:pwa-register'
import { ConIdioma } from './components/ConIdioma'
import { RequierePermiso, RequiereSesion } from './components/Guardias'
import { Layout } from './components/Layout'
import './index.css'
import './i18n'
import { ErrorApi } from './lib/api'
import { CLAVE_YO, PERMISOS_PEDIDOS, PERMISOS_REPORTES, PERMISOS_REPOSICION } from './lib/sesion'
import { Inicio } from './pages/Inicio'
import { Login } from './pages/Login'

// Al publicarse una versión nueva, el service worker se activa y la página se recarga sola.
// Además se busca actualización cada hora y al volver a la app, para no quedar con una versión vieja.
registerSW({
  immediate: true,
  onRegisteredSW(_url, registro) {
    if (!registro) return
    const revisar = () => void registro.update().catch(() => undefined)
    setInterval(revisar, 60 * 60 * 1000)
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') revisar()
    })
  },
})

/** Carga diferida de páginas con exportación con nombre. */
function perezosa<M extends Record<string, unknown>>(cargar: () => Promise<M>, nombre: keyof M) {
  return lazy(() => cargar().then((m) => ({ default: m[nombre] as ComponentType })))
}

const Usuarios = perezosa(() => import('./pages/Usuarios'), 'Usuarios')
const Roles = perezosa(() => import('./pages/Roles'), 'Roles')
const Ubicaciones = perezosa(() => import('./pages/Ubicaciones'), 'Ubicaciones')
const Auditoria = perezosa(() => import('./pages/Auditoria'), 'Auditoria')
const Productos = perezosa(() => import('./pages/catalogo/Productos'), 'Productos')
const Proveedores = perezosa(() => import('./pages/catalogo/Proveedores'), 'Proveedores')
const Clientes = perezosa(() => import('./pages/catalogo/Clientes'), 'Clientes')
const Stock = perezosa(() => import('./pages/inventario/Stock'), 'Stock')
const Kardex = perezosa(() => import('./pages/inventario/Kardex'), 'Kardex')
const Compras = perezosa(() => import('./pages/inventario/Compras'), 'Compras')
const NuevaCompra = perezosa(() => import('./pages/inventario/Compras'), 'NuevaCompra')
const DetalleCompra = perezosa(() => import('./pages/inventario/Compras'), 'DetalleCompra')
const Transferencias = perezosa(() => import('./pages/inventario/Transferencias'), 'Transferencias')
const NuevaTransferencia = perezosa(() => import('./pages/inventario/Transferencias'), 'NuevaTransferencia')
const Ajustes = perezosa(() => import('./pages/inventario/Ajustes'), 'Ajustes')
const NuevoAjuste = perezosa(() => import('./pages/inventario/Ajustes'), 'NuevoAjuste')
const Pedidos = perezosa(() => import('./pages/pedidos/Pedidos'), 'Pedidos')
const NuevoPedido = perezosa(() => import('./pages/pedidos/Pedidos'), 'NuevoPedido')
const DetallePedido = perezosa(() => import('./pages/pedidos/DetallePedido'), 'DetallePedido')
const Conteos = perezosa(() => import('./pages/inventario/Conteos'), 'Conteos')
const DetalleConteo = perezosa(() => import('./pages/inventario/Conteos'), 'DetalleConteo')
const Reportes = perezosa(() => import('./pages/reportes/Reportes'), 'Reportes')
const Alertas = perezosa(() => import('./pages/alertas/Alertas'), 'Alertas')
const Reposicion = perezosa(() => import('./pages/reposicion/Reposicion'), 'Reposicion')
const Finanzas = perezosa(() => import('./pages/finanzas/Finanzas'), 'Finanzas')
const NuevoCobro = perezosa(() => import('./pages/finanzas/NuevoCobro'), 'NuevoCobro')

/** Si cualquier petición responde 401, la sesión expiró: se vuelve al login. */
function alExpirarSesion(error: unknown) {
  if (error instanceof ErrorApi && error.status === 401) {
    queryClient.setQueryData(CLAVE_YO, null)
  }
}

const queryClient = new QueryClient({
  queryCache: new QueryCache({ onError: alExpirarSesion }),
  mutationCache: new MutationCache({ onError: alExpirarSesion }),
  defaultOptions: {
    queries: {
      retry: (intentos, error) => !(error instanceof ErrorApi && error.status < 500) && intentos < 2,
      refetchOnWindowFocus: false,
    },
  },
})

function conPermiso(permiso: string | string[], pagina: ReactNode) {
  return (
    <RequierePermiso permiso={permiso}>
      <Suspense fallback={<p className="text-sm text-slate-500">Cargando…</p>}>{pagina}</Suspense>
    </RequierePermiso>
  )
}

const router = createBrowserRouter([
  { path: '/login', element: <Login /> },
  {
    element: (
      <RequiereSesion>
        <Layout />
      </RequiereSesion>
    ),
    children: [
      { index: true, element: <Inicio /> },
      { path: 'pedidos', element: conPermiso(PERMISOS_PEDIDOS, <Pedidos />) },
      { path: 'pedidos/nuevo', element: conPermiso('pedidos.escanear', <NuevoPedido />) },
      { path: 'pedidos/:pedidoId', element: conPermiso(PERMISOS_PEDIDOS, <DetallePedido />) },
      { path: 'inventario', element: conPermiso('inventario.ver', <Stock />) },
      { path: 'inventario/kardex/:productoId', element: conPermiso('inventario.ver', <Kardex />) },
      { path: 'compras', element: conPermiso('compras.registrar', <Compras />) },
      { path: 'compras/nueva', element: conPermiso('compras.registrar', <NuevaCompra />) },
      { path: 'compras/:compraId', element: conPermiso('compras.registrar', <DetalleCompra />) },
      { path: 'transferencias', element: conPermiso('inventario.ver', <Transferencias />) },
      { path: 'transferencias/nueva', element: conPermiso('inventario.transferir', <NuevaTransferencia />) },
      { path: 'ajustes', element: conPermiso('inventario.ver', <Ajustes />) },
      { path: 'ajustes/nuevo', element: conPermiso('inventario.ajustar', <NuevoAjuste />) },
      { path: 'conteos', element: conPermiso('inventario.ver', <Conteos />) },
      { path: 'conteos/:conteoId', element: conPermiso('inventario.ver', <DetalleConteo />) },
      { path: 'productos', element: conPermiso('catalogo.ver', <Productos />) },
      { path: 'proveedores', element: conPermiso('catalogo.ver', <Proveedores />) },
      { path: 'clientes', element: conPermiso('catalogo.ver', <Clientes />) },
      { path: 'alertas', element: <Suspense fallback={<p className="text-sm text-slate-500">Cargando…</p>}><Alertas /></Suspense> },
      { path: 'reposicion', element: conPermiso(PERMISOS_REPOSICION, <Reposicion />) },
      { path: 'reportes', element: conPermiso(PERMISOS_REPORTES, <Reportes />) },
      { path: 'finanzas', element: conPermiso('finanzas.ver', <Finanzas />) },
      { path: 'finanzas/cobros/nuevo', element: conPermiso('finanzas.cobros', <NuevoCobro />) },
      { path: 'usuarios', element: conPermiso('usuarios.ver', <Usuarios />) },
      { path: 'roles', element: conPermiso('roles.ver', <Roles />) },
      { path: 'ubicaciones', element: conPermiso('ubicaciones.gestionar', <Ubicaciones />) },
      { path: 'auditoria', element: conPermiso('auditoria.ver', <Auditoria />) },
      {
        path: '*',
        element: (
          <div className="py-16 text-center">
            <p className="text-lg font-medium">Página no encontrada</p>
            <Link to="/" className="text-marca-700 underline">
              Volver al inicio
            </Link>
          </div>
        ),
      },
    ],
  },
], { basename: import.meta.env.BASE_URL.replace(/\/$/, '') || '/' })

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <ConIdioma>
        <RouterProvider router={router} />
      </ConIdioma>
    </QueryClientProvider>
  </StrictMode>,
)
