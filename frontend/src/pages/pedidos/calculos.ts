/** Cálculos de la revisión del pedido en el navegador (el servidor repite las mismas reglas). */
import { formatearBs, formatearCantidad } from '../../lib/formato'

const TOLERANCIA = 0.01

/** Texto numérico del formulario → valor para la API ('' → null). Acepta coma decimal. */
export function numeroONulo(valor: string): string | null {
  const limpio = valor.trim().replace(',', '.')
  if (limpio === '' || Number.isNaN(Number(limpio))) return null
  return limpio
}

export const redondear2 = (n: number) => Math.round((n + Number.EPSILON) * 100) / 100

interface LineaCalculo {
  cantidad_oc: string
  precio_oc: string
}

/** Total de la línea: cantidad × precio (se calcula solo, D-21). */
export function totalCalculado(l: LineaCalculo): number {
  return redondear2((Number(l.cantidad_oc) || 0) * (Number(l.precio_oc) || 0))
}

/** Mensaje si `cantidad × precio` no coincide con el total impreso en el documento leído. */
export function diferenciaLinea(l: LineaCalculo & { impreso: string }): string | null {
  const impreso = numeroONulo(l.impreso)
  if (impreso === null || !l.cantidad_oc || !l.precio_oc) return null
  const calculado = totalCalculado(l)
  if (Math.abs(calculado - Number(impreso)) <= TOLERANCIA) return null
  return `${formatearCantidad(l.cantidad_oc)} × ${l.precio_oc} = ${formatearBs(calculado)}, pero el documento dice ${formatearBs(impreso)}.`
}

/** Subtotal (suma de cantidad × precio), descuento y total del pedido. */
export function totales(lineas: LineaCalculo[], descuento: string): { subtotal: number; descuento: number; total: number } {
  const subtotal = redondear2(lineas.reduce((s, l) => s + totalCalculado(l), 0))
  const d = redondear2(Number(numeroONulo(descuento) ?? 0))
  return { subtotal, descuento: d, total: redondear2(subtotal - d) }
}

/** Descuento guardado implícitamente: suma de los totales de línea menos el total del pedido. */
export function descuentoInicial(totalesLinea: (string | null)[], total: string | null): string {
  if (total === null) return ''
  const suma = totalesLinea.reduce((s, t) => s + (Number(t) || 0), 0)
  const d = redondear2(suma - Number(total))
  return d > 0 ? String(d) : ''
}
