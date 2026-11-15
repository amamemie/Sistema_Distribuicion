/** Cálculos de la pantalla de reportes: rangos de fechas, escalas de los gráficos y formato. */
import { formatearBs, formatearCantidad, formatearDia, formatearPorcentaje } from '../../lib/formato'
import type { TipoDato } from '../../lib/tipos'

export type Rango = 'mes' | 'mes_anterior' | '7' | '30' | '90' | 'anio' | 'personalizado'

const iso = (d: Date) => d.toISOString().slice(0, 10)
const dia = (texto: string) => new Date(`${texto}T00:00:00Z`)

/** Fechas (AAAA-MM-DD) de un rango rápido, contando desde `hoy` (fecha de La Paz). */
export function fechasDeRango(rango: Exclude<Rango, 'personalizado'>, hoy: string): { desde: string; hasta: string } {
  const h = dia(hoy)
  const y = h.getUTCFullYear()
  const m = h.getUTCMonth()
  if (rango === 'mes') return { desde: iso(new Date(Date.UTC(y, m, 1))), hasta: hoy }
  if (rango === 'mes_anterior') return { desde: iso(new Date(Date.UTC(y, m - 1, 1))), hasta: iso(new Date(Date.UTC(y, m, 0))) }
  if (rango === 'anio') return { desde: `${y}-01-01`, hasta: hoy }
  const desde = new Date(h)
  desde.setUTCDate(desde.getUTCDate() - (Number(rango) - 1))
  return { desde: iso(desde), hasta: hoy }
}

/** Agrupación razonable para el largo del rango (por día hasta ~2 meses). */
export function agrupacionSugerida(desde: string, hasta: string): 'dia' | 'semana' | 'mes' | 'anio' {
  const dias = (dia(hasta).getTime() - dia(desde).getTime()) / 86_400_000 + 1
  if (dias <= 62) return 'dia'
  if (dias <= 190) return 'semana'
  if (dias <= 1100) return 'mes'
  return 'anio'
}

/** Marcas "redondas" para un eje que cubre [min, max] (siempre incluye el 0). */
export function marcasEje(min: number, max: number, cantidad = 4): number[] {
  const bajo = Math.min(0, min)
  const alto = Math.max(0, max)
  if (alto === bajo) return [0, 1]
  const bruto = (alto - bajo) / cantidad
  const potencia = 10 ** Math.floor(Math.log10(bruto))
  const paso = [1, 2, 2.5, 5, 10].map((f) => f * potencia).find((p) => p >= bruto) ?? 10 * potencia
  const marcas: number[] = []
  for (let v = Math.floor(bajo / paso) * paso; v <= alto + paso * 0.999; v += paso) marcas.push(Math.round(v * 1e6) / 1e6)
  if (marcas[marcas.length - 1] < alto) marcas.push(marcas[marcas.length - 1] + paso)
  return marcas
}

// 'es' (no 'es-BO'): abrevia "2,8 mil" en lugar de "2,8 K".
const compacto = new Intl.NumberFormat('es', { notation: 'compact', maximumFractionDigits: 1 })

/** Etiqueta corta para los ejes: "Bs 12,5 mil", "45 %". */
export function formatoCorto(valor: number, tipo: TipoDato): string {
  if (tipo === 'porcentaje') return `${compacto.format(valor)} %`
  if (tipo === 'dinero') return `Bs ${compacto.format(valor)}`
  return compacto.format(valor)
}

export function formatear(valor: string | number | null | undefined, tipo: TipoDato): string {
  if (valor === null || valor === undefined || valor === '') return '—'
  switch (tipo) {
    case 'dinero':
      return formatearBs(valor)
    case 'porcentaje':
      return formatearPorcentaje(valor)
    case 'entero':
    case 'cantidad':
      return formatearCantidad(valor)
    case 'fecha':
      return formatearDia(String(valor))
    default:
      return String(valor)
  }
}

export const esNumerico = (tipo: TipoDato) => tipo !== 'texto' && tipo !== 'fecha'

/**
 * Colores de las series en orden fijo (paleta validada: separables con daltonismo en pares
 * contiguos). Los de poco contraste siempre van con leyenda, valor visible o la tabla.
 */
export const COLORES_SERIE = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#6250d6', '#e34948']
