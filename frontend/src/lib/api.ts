/** Cliente HTTP de la API. Envía la cookie de sesión y la cabecera CSRF automáticamente. */
import { idiomaActual } from '../i18n'

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

/** URL de un archivo de un pedido (OC o constancia), servida con la cookie de sesión. */
export function urlArchivo(pedidoId: string, archivoId: string): string {
  return `/api/pedidos/${pedidoId}/archivos/${archivoId}`
}

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

/** Demo pública (GitHub Pages): sin servidor, responde con datos de ejemplo de solo lectura. */
export const MODO_DEMO = import.meta.env.MODE === 'demo'

async function apiDemo<T>(ruta: string, metodo: string, params?: Params): Promise<T> {
  const { responder, ErrorDemo } = await import('../demo/servidor')
  try {
    return (await responder(new URL(construirUrl(ruta, params), location.origin), metodo)) as T
  } catch (e) {
    if (e instanceof ErrorDemo) throw new ErrorApi(e.status, 'demo', e.message)
    throw e
  }
}

export async function api<T>(ruta: string, { metodo = 'GET', cuerpo, params }: Opciones = {}) {
  if (MODO_DEMO) return apiDemo<T>(ruta, metodo, params)
  // Accept-Language: el servidor podrá responder sus mensajes en el idioma del usuario.
  const headers: Record<string, string> = { Accept: 'application/json', 'Accept-Language': idiomaActual() }
  const esFormulario = cuerpo instanceof FormData
  // Con FormData el navegador pone el Content-Type (multipart con su separador).
  if (cuerpo !== undefined && !esFormulario) headers['Content-Type'] = 'application/json'
  if (metodo !== 'GET') {
    const csrf = leerCookie('csrf_token', document.cookie)
    if (csrf) headers['X-CSRF-Token'] = csrf
  }

  let respuesta: Response
  try {
    respuesta = await fetch(construirUrl(ruta, params), {
      method: metodo,
      headers,
      body: cuerpo === undefined ? undefined : esFormulario ? cuerpo : JSON.stringify(cuerpo),
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
