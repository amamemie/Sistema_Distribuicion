/** Cálculos de la revisión de la OC en el navegador (el servidor repite las mismas reglas). */
import { formatearBs, formatearCantidad } from '../../lib/formato'

const TOLERANCIA = 0.01

/** Texto numérico del formulario → valor para la API ('' → null). Acepta coma decimal. */
export function numeroONulo(valor: string): string | null {
  const limpio = valor.trim().replace(',', '.')
  if (limpio === '' || Number.isNaN(Number(limpio))) return null
  return limpio
}

const redondear2 = (n: number) => Math.round((n + Number.EPSILON) * 100) / 100

interface LineaCalculo {
  cantidad_oc: string
  precio_oc: string
  total_linea_oc: string
}

export function totalCalculado(l: LineaCalculo): number {
  return redondear2((Number(l.cantidad_oc) || 0) * (Number(l.precio_oc) || 0))
}

/** Mensaje si `cantidad × precio` no coincide con el total impreso de la línea. */
export function diferenciaLinea(l: LineaCalculo): string | null {
  const impreso = numeroONulo(l.total_linea_oc)
  if (impreso === null || !l.cantidad_oc || !l.precio_oc) return null
  const calculado = totalCalculado(l)
  if (Math.abs(calculado - Number(impreso)) <= TOLERANCIA) return null
  return `${formatearCantidad(l.cantidad_oc)} × ${l.precio_oc} = ${formatearBs(calculado)}, pero la OC dice ${formatearBs(impreso)}.`
}

/** Suma de las líneas: el total impreso si existe, si no el calculado. */
export function sumaLineas(lineas: LineaCalculo[]): number {
  return redondear2(
    lineas.reduce((s, l) => {
      const impreso = numeroONulo(l.total_linea_oc)
      return s + (impreso !== null ? Number(impreso) : totalCalculado(l))
    }, 0),
  )
}
