import type { Producto } from './tipos'

export interface LineaBase {
  clave: string
  producto: Producto | null
  presentacion_id: string // '' = unidad base
  cantidad: string
}

export function nuevaClave(): string {
  return Math.random().toString(36).slice(2)
}

export function factorDe(linea: LineaBase): number {
  if (!linea.producto || !linea.presentacion_id) return 1
  const p = linea.producto.presentaciones.find((x) => x.id === linea.presentacion_id)
  return p ? Number(p.factor) : 1
}

export function cantidadBase(linea: LineaBase): number {
  return (Number(linea.cantidad) || 0) * factorDe(linea)
}
