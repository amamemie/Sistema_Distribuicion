/** Cliente HTTP de la API. Envía la cookie de sesión y la cabecera CSRF automáticamente. */

export interface ErrorCampo {
  campo: string
  mensaje: string
}

export class ErrorApi extends Error {
  readonly status: number
  readonly codigo: string
  readonly errores: ErrorCampo[]

  constructor(status: number, codigo: string, mensaje: string, errores: ErrorCampo[] = []) {
    super(mensaje)
    this.status = status
    this.codigo = codigo
    this.errores = errores
  }
}

type Params = Record<string, string | number | boolean | null | undefined>

export function construirUrl(ruta: string, params?: Params): string {
  const query = new URLSearchParams()
  for (const [clave, valor] of Object.entries(params ?? {})) {
    if (valor !== undefined && valor !== null && valor !== '') query.set(clave, String(valor))
  }
  const texto = query.toString()
  return `/api${ruta}${texto ? `?${texto}` : ''}`
}

export function leerCookie(nombre: string, cookies: string): string | null {
  for (const parte of cookies.split(';')) {
    const [clave, ...resto] = parte.trim().split('=')
    if (clave === nombre) return decodeURIComponent(resto.join('='))
  }
  return null
}

interface Opciones {
  metodo?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'
  cuerpo?: unknown
  params?: Params
}

export async function api<T>(ruta: string, { metodo = 'GET', cuerpo, params }: Opciones = {}) {
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (cuerpo !== undefined) headers['Content-Type'] = 'application/json'
  if (metodo !== 'GET') {
    const csrf = leerCookie('csrf_token', document.cookie)
    if (csrf) headers['X-CSRF-Token'] = csrf
  }

  let respuesta: Response
  try {
    respuesta = await fetch(construirUrl(ruta, params), {
      method: metodo,
      headers,
      body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
      credentials: 'same-origin',
    })
  } catch {
    throw new ErrorApi(0, 'sin_conexion', 'No hay conexión con el servidor. Revise su red.')
  }

  if (respuesta.status === 204) return undefined as T
  const datos = await respuesta.json().catch(() => null)
  if (!respuesta.ok) {
    throw new ErrorApi(
      respuesta.status,
      datos?.codigo ?? 'error',
      datos?.detalle ?? 'Ocurrió un error inesperado.',
      datos?.errores ?? [],
    )
  }
  return datos as T
}

export function mensajeError(error: unknown): string {
  if (error instanceof ErrorApi) return error.message
  return 'Ocurrió un error inesperado.'
}
