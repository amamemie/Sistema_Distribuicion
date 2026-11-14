/** Cola de subida de OC guardada en el dispositivo (IndexedDB).
 *
 * Si no hay señal al fotografiar la OC, las fotos no se pierden: quedan en el celular y se
 * suben solas cuando vuelve la conexión. Cada envío crea el pedido una sola vez (se guarda su
 * id) y sube los archivos uno por uno, quitándolos de la cola a medida que llegan.
 */
import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
import type { PedidoDetalle } from './tipos'

export interface EnvioPendiente {
  id: string
  ubicacion_id: string
  ubicacion_nombre: string
  archivos: { nombre: string; blob: Blob }[]
  creado: number
  pedido_id: string | null
  error: string | null
}

const BASE = 'inventario'
const ALMACEN = 'envios'

function abrir(): Promise<IDBDatabase> {
  return new Promise((ok, falla) => {
    const pedido = indexedDB.open(BASE, 1)
    pedido.onupgradeneeded = () => pedido.result.createObjectStore(ALMACEN, { keyPath: 'id' })
    pedido.onsuccess = () => ok(pedido.result)
    pedido.onerror = () => falla(pedido.error)
  })
}

async function operar<T>(modo: IDBTransactionMode, accion: (almacen: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  const db = await abrir()
  try {
    return await new Promise<T>((ok, falla) => {
      const solicitud = accion(db.transaction(ALMACEN, modo).objectStore(ALMACEN))
      solicitud.onsuccess = () => ok(solicitud.result)
      solicitud.onerror = () => falla(solicitud.error)
    })
  } finally {
    db.close()
  }
}

export const guardarEnvio = (envio: EnvioPendiente) => operar('readwrite', (a) => a.put(envio))
export const quitarEnvio = (id: string) => operar('readwrite', (a) => a.delete(id))
export const listarEnvios = async () =>
  ((await operar('readonly', (a) => a.getAll())) as EnvioPendiente[]).sort((x, y) => x.creado - y.creado)

/** Arma un envío nuevo con las páginas de la OC. */
export function nuevoEnvio(ubicacion: { id: string; nombre: string }, archivos: File[]): EnvioPendiente {
  return {
    id: crypto.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`,
    ubicacion_id: ubicacion.id,
    ubicacion_nombre: ubicacion.nombre,
    archivos: archivos.map((a) => ({ nombre: a.name, blob: a })),
    creado: Date.now(),
    pedido_id: null,
    error: null,
  }
}

const enCurso = new Set<string>()

/** Sube un envío pendiente. Devuelve el pedido creado cuando terminó de subir todo. */
export async function procesarEnvio(envio: EnvioPendiente, alAvanzar?: (texto: string) => void): Promise<PedidoDetalle | null> {
  if (enCurso.has(envio.id)) return null
  enCurso.add(envio.id)
  try {
    const actual = { ...envio, archivos: [...envio.archivos] }
    if (!actual.pedido_id) {
      alAvanzar?.('Creando el pedido…')
      const pedido = await api<PedidoDetalle>('/pedidos', { metodo: 'POST', cuerpo: { ubicacion_id: actual.ubicacion_id } })
      actual.pedido_id = pedido.id
      await guardarEnvio(actual)
    }
    let ultimo: PedidoDetalle | null = null
    const total = actual.archivos.length
    while (actual.archivos.length) {
      const [archivo] = actual.archivos
      alAvanzar?.(`Subiendo archivo ${total - actual.archivos.length + 1} de ${total}…`)
      const formulario = new FormData()
      formulario.append('archivos', archivo.blob, archivo.nombre)
      ultimo = await api<PedidoDetalle>(`/pedidos/${actual.pedido_id}/documentos`, { metodo: 'POST', cuerpo: formulario })
      actual.archivos.shift()
      await guardarEnvio(actual)
    }
    await quitarEnvio(actual.id)
    return ultimo ?? (await api<PedidoDetalle>(`/pedidos/${actual.pedido_id}`))
  } catch (error) {
    const mensaje = error instanceof Error ? error.message : 'Error al subir.'
    const guardado = (await listarEnvios()).find((e) => e.id === envio.id)
    if (guardado) await guardarEnvio({ ...guardado, error: mensaje })
    throw error
  } finally {
    enCurso.delete(envio.id)
  }
}

/** Envíos pendientes de este dispositivo; reintenta solo al recuperar la conexión. */
export function useColaSubida(alSubir?: () => void) {
  const [pendientes, setPendientes] = useState<EnvioPendiente[]>([])
  const [subiendo, setSubiendo] = useState(false)

  const recargar = useCallback(async () => {
    try {
      setPendientes(await listarEnvios())
    } catch {
      setPendientes([])
    }
  }, [])

  const reintentar = useCallback(async () => {
    const lista = await listarEnvios().catch(() => [])
    if (!lista.length) return
    setSubiendo(true)
    for (const envio of lista) {
      try {
        await procesarEnvio(envio)
        alSubir?.()
      } catch {
        // queda en la cola con su error; se reintenta luego
      }
    }
    setSubiendo(false)
    await recargar()
  }, [alSubir, recargar])

  useEffect(() => {
    listarEnvios()
      .then(setPendientes)
      .catch(() => setPendientes([]))
    const alConectar = () => void reintentar()
    window.addEventListener('online', alConectar)
    return () => window.removeEventListener('online', alConectar)
  }, [reintentar])

  const descartar = useCallback(
    async (id: string) => {
      await quitarEnvio(id)
      await recargar()
    },
    [recargar],
  )

  return { pendientes, subiendo, reintentar, descartar, recargar }
}
