/** Servidor simulado de la demo pública (GitHub Pages): responde con datos de ejemplo grabados
 * de una instancia de prueba. Solo lectura: los cambios devuelven un aviso. Nunca se incluye en
 * el build normal (se importa de forma diferida solo en `vite build --mode demo`). */
import i18n from '../i18n'
import datos from './datos.json'

const RESPUESTAS = datos as Record<string, unknown>
const RUTAS = Object.keys(RESPUESTAS).map((clave) => {
  const [ruta, query = ''] = clave.split('?')
  return { clave, ruta, params: new URLSearchParams(query) }
})

// Fechas y paginación cambian con el día o la pantalla: no deben impedir encontrar la respuesta.
const VARIABLES = new Set(['desde', 'hasta', 'pagina', 'tamano', 'buscar'])

/** Respuesta grabada más parecida: misma ruta y la mayor cantidad de filtros iguales. */
function buscar(url: URL): unknown {
  const exacta = RESPUESTAS[url.pathname + url.search]
  if (exacta !== undefined) return exacta
  let mejor: { clave: string; puntos: number } | null = null
  for (const r of RUTAS) {
    if (r.ruta !== url.pathname) continue
    let puntos = 0
    let descarta = false
    for (const [k, v] of url.searchParams) {
      if (VARIABLES.has(k)) continue
      if (r.params.get(k) === v) puntos += 2
      else if (r.params.has(k)) descarta = true
    }
    for (const k of r.params.keys()) if (!VARIABLES.has(k) && !url.searchParams.has(k)) puntos -= 1
    if (!descarta && (!mejor || puntos > mejor.puntos)) mejor = { clave: r.clave, puntos }
  }
  return mejor ? RESPUESTAS[mejor.clave] : undefined
}

export class ErrorDemo extends Error {
  status: number
  constructor(status: number, mensaje: string) {
    super(mensaje)
    this.status = status
  }
}

export async function responder(url: URL, metodo: string): Promise<unknown> {
  await new Promise((r) => setTimeout(r, 120)) // como una red real, para ver los estados de carga
  if (url.pathname === '/api/auth/login') return RESPUESTAS['/api/auth/yo']
  if (url.pathname === '/api/auth/logout') return undefined
  if (metodo !== 'GET') {
    throw new ErrorDemo(403, i18n.t('Esta es una demo con datos de ejemplo: los cambios no se guardan.'))
  }
  const respuesta = buscar(url)
  if (respuesta === undefined) throw new ErrorDemo(404, i18n.t('Esta pantalla no tiene datos en la demo.'))
  return structuredClone(respuesta)
}
