import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router'
import { usePuede, useYo } from '../lib/sesion'

export function RequiereSesion({ children }: { children: ReactNode }) {
  const { data, isPending, isError } = useYo()
  const ubicacion = useLocation()
  if (isPending) {
    return <div className="flex min-h-dvh items-center justify-center text-slate-500">Cargando…</div>
  }
  if (isError || !data) return <Navigate to="/login" replace state={{ desde: ubicacion.pathname }} />
  return children
}

export function RequierePermiso({ permiso, children }: { permiso: string; children: ReactNode }) {
  const puede = usePuede()
  if (!puede(permiso)) {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-6 text-amber-900">
        No tiene permiso para ver esta sección.
      </div>
    )
  }
  return children
}
