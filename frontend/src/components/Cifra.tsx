/** Número que cuenta hasta su valor la primera vez que aparece (≤ 600 ms). Con movimiento
 * reducido se muestra directo. El texto final siempre es el valor formateado real. */
import { useEffect, useRef, useState } from 'react'

const reducido = () => typeof window !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches

export function CifraAnimada({ valor, formato }: { valor: number; formato: (n: number) => string }) {
  const [sinMovimiento] = useState(reducido)
  const [mostrado, setMostrado] = useState(0)
  const anterior = useRef(0)
  useEffect(() => {
    if (sinMovimiento) return
    const desde = anterior.current
    const inicio = performance.now()
    let id = requestAnimationFrame(function paso(ahora) {
      const t = Math.min(1, (ahora - inicio) / 600)
      setMostrado(desde + (valor - desde) * (1 - (1 - t) ** 3))
      if (t < 1) id = requestAnimationFrame(paso)
      else anterior.current = valor
    })
    return () => cancelAnimationFrame(id)
  }, [valor, sinMovimiento])
  const final = sinMovimiento || mostrado === valor
  return <span className="tabular-nums">{formato(final ? valor : mostrado)}</span>
}
