/** Escena de la distribuidora: 3D si el equipo puede, imagen fija si no (DESIGN.md §6). */
import { lazy, Suspense, useState } from 'react'
import { EscenaFija } from './EscenaFija'

const Escena3D = lazy(() => import('./Escena3D'))

/** ¿Conviene mostrar la escena 3D? No con movimiento reducido, sin WebGL, en pantallas chicas
 * ni en equipos con muy pocos recursos. */
function puede3D(): boolean {
  if (typeof window === 'undefined') return false
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) return false
  if (innerWidth < 640) return false
  const nav = navigator as Navigator & { deviceMemory?: number }
  if ((nav.hardwareConcurrency ?? 4) <= 2 || (nav.deviceMemory ?? 4) <= 2) return false
  try {
    const lienzo = document.createElement('canvas')
    return !!(lienzo.getContext('webgl2') ?? lienzo.getContext('webgl'))
  } catch {
    return false
  }
}

export function Escena({ variante, className = '' }: { variante: 'login' | 'portada'; className?: string }) {
  const [tres] = useState(puede3D)
  const fija = <EscenaFija variante={variante} className={`${className} size-full`} />
  if (!tres) return fija
  return (
    <Suspense fallback={fija}>
      <Escena3D variante={variante} className={className} />
    </Suspense>
  )
}
