import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter, Link, RouterProvider } from 'react-router'
import { Layout } from './components/Layout'
import './index.css'
import { ErrorApi } from './lib/api'
import { RequierePermiso, RequiereSesion } from './components/Guardias'
import { CLAVE_YO } from './lib/sesion'
import { Auditoria } from './pages/Auditoria'
import { Inicio } from './pages/Inicio'
import { Login } from './pages/Login'
import { Roles } from './pages/Roles'
import { Ubicaciones } from './pages/Ubicaciones'
import { Usuarios } from './pages/Usuarios'

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
      {
        path: 'usuarios',
        element: (
          <RequierePermiso permiso="usuarios.ver">
            <Usuarios />
          </RequierePermiso>
        ),
      },
      {
        path: 'roles',
        element: (
          <RequierePermiso permiso="roles.ver">
            <Roles />
          </RequierePermiso>
        ),
      },
      {
        path: 'ubicaciones',
        element: (
          <RequierePermiso permiso="ubicaciones.gestionar">
            <Ubicaciones />
          </RequierePermiso>
        ),
      },
      {
        path: 'auditoria',
        element: (
          <RequierePermiso permiso="auditoria.ver">
            <Auditoria />
          </RequierePermiso>
        ),
      },
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
])

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
)
