const fechaHora = new Intl.DateTimeFormat('es-BO', {
  timeZone: 'America/La_Paz',
  dateStyle: 'short',
  timeStyle: 'short',
})

export function formatearFecha(valor: string | null | undefined): string {
  return valor ? fechaHora.format(new Date(valor)) : '—'
}
