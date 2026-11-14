const fechaHora = new Intl.DateTimeFormat('es-BO', {
  timeZone: 'America/La_Paz',
  dateStyle: 'short',
  timeStyle: 'short',
})

const soloFecha = new Intl.DateTimeFormat('es-BO', { timeZone: 'UTC', dateStyle: 'medium' })

const numero = new Intl.NumberFormat('es-BO', { maximumFractionDigits: 3 })

const dinero = new Intl.NumberFormat('es-BO', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

const costo = new Intl.NumberFormat('es-BO', { minimumFractionDigits: 2, maximumFractionDigits: 4 })

export function formatearFecha(valor: string | null | undefined): string {
  return valor ? fechaHora.format(new Date(valor)) : '—'
}

/** Fechas sin hora (AAAA-MM-DD): se muestran tal cual, sin desplazamiento de zona horaria. */
export function formatearDia(valor: string | null | undefined): string {
  return valor ? soloFecha.format(new Date(`${valor}T00:00:00Z`)) : '—'
}

export function formatearCantidad(valor: string | number | null | undefined): string {
  if (valor === null || valor === undefined || valor === '') return '—'
  return numero.format(Number(valor))
}

export function formatearBs(valor: string | number | null | undefined): string {
  if (valor === null || valor === undefined || valor === '') return '—'
  return `Bs ${dinero.format(Number(valor))}`
}

export function formatearCosto(valor: string | number | null | undefined): string {
  if (valor === null || valor === undefined || valor === '') return '—'
  return `Bs ${costo.format(Number(valor))}`
}

/** Fecha de hoy en La Paz como AAAA-MM-DD (para inputs de tipo date). */
export function hoyLaPaz(): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'America/La_Paz' }).format(new Date())
}
