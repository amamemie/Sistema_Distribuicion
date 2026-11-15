/** Utilidades de la pantalla de finanzas (lógica pura, con pruebas). */

/** Comprobante de un cobro o gasto, servido con la cookie de sesión. */
export const urlComprobante = (archivoId: string) => `/api/finanzas/comprobantes/${archivoId}`

const MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']

/** "2026-11-05" → "noviembre 2026". */
export function nombreMes(fecha: string): string {
  const [anio, mes] = fecha.split('-')
  return `${MESES[Number(mes) - 1]} ${anio}`
}

/** "2026-11" → "2026-11-01". */
export function primerDiaMes(mes: string): string {
  return `${mes.slice(0, 7)}-01`
}

/** "2026-02" → "2026-02-28" (considera años bisiestos). */
export function ultimoDiaMes(mes: string): string {
  const [anio, m] = mes.split('-').map(Number)
  const dia = new Date(Date.UTC(anio, m, 0)).getUTCDate()
  return `${mes.slice(0, 7)}-${String(dia).padStart(2, '0')}`
}

/** Agrupa por mes ("2026-11-01") conservando el orden de aparición. */
export function agruparPorMes<T>(items: T[], fecha: (item: T) => string): [string, T[]][] {
  const grupos = new Map<string, T[]>()
  for (const item of items) {
    const mes = primerDiaMes(fecha(item))
    grupos.set(mes, [...(grupos.get(mes) ?? []), item])
  }
  return [...grupos.entries()]
}

const centavos = (valor: string | number) => Math.round(Number(valor || 0) * 100)

/** Suma exacta en centavos (evita errores de coma flotante al comparar montos en Bs). */
export function sumarBs(valores: (string | number)[]): number {
  return valores.reduce<number>((s, v) => s + centavos(v), 0) / 100
}

/** Monto en Bs como texto con dos decimales para enviar a la API ("150.5" → "150.50"). */
export function aTextoBs(valor: number): string {
  return (Math.round(valor * 100) / 100).toFixed(2)
}

/** ¿Lo aplicado a los pedidos cuadra con el monto de la transferencia? */
export function cuadra(aplicado: (string | number)[], monto: string | number): boolean {
  return aplicado.reduce<number>((s, v) => s + centavos(v), 0) === centavos(monto)
}
