import { useQuery } from '@tanstack/react-query'
import { Bell } from 'lucide-react'
import { Link } from 'react-router'
import { api } from '../lib/api'
import type { ResumenAlertas } from '../lib/tipos'

/** Campanita del encabezado: alertas sin leer (se consulta cada minuto). */
export function Campana() {
  const resumen = useQuery({
    queryKey: ['alertas', 'resumen'],
    queryFn: () => api<ResumenAlertas>('/alertas/resumen'),
    refetchInterval: 60_000,
    refetchIntervalInBackground: false,
  })
  const n = resumen.data?.no_leidas ?? 0
  const criticas = (resumen.data?.criticas ?? 0) > 0
  const texto = n === 0 ? 'Alertas: no hay nuevas' : `Alertas: ${n} sin leer${criticas ? ', hay críticas' : ''}`
  return (
    <Link
      to="/alertas"
      aria-label={texto}
      title={texto}
      className="relative inline-flex min-h-10 items-center rounded-md px-2 text-slate-700 hover:bg-slate-100"
    >
      <Bell size={18} />
      {n > 0 && (
        <span
          className={`absolute top-1 right-0.5 min-w-4 rounded-full px-1 text-center text-[10px] leading-4 font-semibold text-white ${
            criticas ? 'bg-red-600' : 'bg-marca-600'
          }`}
        >
          {n > 99 ? '99+' : n}
        </span>
      )}
    </Link>
  )
}
