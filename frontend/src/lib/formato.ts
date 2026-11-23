/** Formatos de fecha, número y dinero según el idioma activo (es-BO / en-US), en hora de La Paz. */
import { locale } from '../i18n'

const ZONA = 'America/La_Paz'
const cache = new Map<string, Intl.NumberFormat | Intl.DateTimeFormat>()

function formateador<T extends Intl.NumberFormat | Intl.DateTimeFormat>(clave: string, crear: (loc: string) => T): T {
  const loc = locale()
  const k = `${loc}|${clave}`
  let f = cache.get(k) as T | undefined
  if (!f) {
    f = crear(loc)
    cache.set(k, f)
  }
  return f
}

const fechaHora = () => formateador('fechaHora', (l) => new Intl.DateTimeFormat(l, { timeZone: ZONA, dateStyle: 'short', timeStyle: 'short' }))
const soloFecha = () => formateador('dia', (l) => new Intl.DateTimeFormat(l, { timeZone: 'UTC', dateStyle: 'medium' }))
const numero = () => formateador('numero', (l) => new Intl.NumberFormat(l, { maximumFractionDigits: 3 }))
const dinero = () => formateador('dinero', (l) => new Intl.NumberFormat(l, { minimumFractionDigits: 2, maximumFractionDigits: 2 }))
const costo = () => formateador('costo', (l) => new Intl.NumberFormat(l, { minimumFractionDigits: 2, maximumFractionDigits: 4 }))

export function formatearFecha(valor: string | null | undefined): string {
  return valor ? fechaHora().format(new Date(valor)) : '—'
}

/** Fechas sin hora (AAAA-MM-DD): se muestran tal cual, sin desplazamiento de zona horaria. */
export function formatearDia(valor: string | null | undefined): string {
  return valor ? soloFecha().format(new Date(`${valor}T00:00:00Z`)) : '—'
}

/** Fecha larga de hoy: «domingo, 23 de noviembre de 2026» / «Sunday, November 23, 2026». */
export function fechaLargaHoy(): string {
  return formateador('larga', (l) => new Intl.DateTimeFormat(l, { timeZone: ZONA, weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })).format(new Date())
}

export function formatearCantidad(valor: string | number | null | undefined): string {
  if (valor === null || valor === undefined || valor === '') return '—'
  return numero().format(Number(valor))
}

export function formatearBs(valor: string | number | null | undefined): string {
  if (valor === null || valor === undefined || valor === '') return '—'
  return `Bs ${dinero().format(Number(valor))}`
}

export function formatearCosto(valor: string | number | null | undefined): string {
  if (valor === null || valor === undefined || valor === '') return '—'
  return `Bs ${costo().format(Number(valor))}`
}

export function formatearPorcentaje(valor: string | number | null | undefined): string {
  if (valor === null || valor === undefined || valor === '') return '—'
  return `${dinero().format(Number(valor))} %`
}

/** Tamaño de archivo legible: 1,5 MB, 320 KB. */
export function formatearTamano(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${numero().format(Math.round((bytes / 1024 / 1024) * 10) / 10)} MB`
  return `${numero().format(Math.max(1, Math.round(bytes / 1024)))} KB`
}

/** Fecha de hoy en La Paz como AAAA-MM-DD (para inputs de tipo date). */
export function hoyLaPaz(): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: ZONA }).format(new Date())
}
