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
      className="relative inline-grid size-9 place-items-center rounded-lg text-tinta-2 transition-colors hover:bg-superficie-2 hover:text-tinta"
    >
      <Bell size={18} aria-hidden />
      {n > 0 && (
        <span
          className={`absolute -top-0.5 -right-0.5 min-w-4 rounded-full px-1 text-center text-[10px] leading-4 font-semibold tabular-nums ring-2 ring-superficie ${
            criticas ? 'bg-peligro text-white dark:text-[#2e1517]' : 'bg-acento text-sobre-acento'
          }`}
        >
          {n > 99 ? '99+' : n}
        </span>
      )}
    </Link>
  )
}
