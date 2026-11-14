/** Consultas compartidas entre páginas (catálogos pequeños que se reutilizan). */
import { useQuery } from '@tanstack/react-query'
import { api } from './api'
import type { Cadena, Categoria, Marca, Proveedor, Ubicacion } from './tipos'

const CINCO_MINUTOS = 5 * 60 * 1000

export function useUbicaciones(soloActivas = true) {
  return useQuery({
    queryKey: ['ubicaciones'],
    queryFn: () => api<Ubicacion[]>('/ubicaciones'),
    staleTime: CINCO_MINUTOS,
    select: (lista) => (soloActivas ? lista.filter((u) => u.activo) : lista),
  })
}

export function useCategorias() {
  return useQuery({ queryKey: ['categorias'], queryFn: () => api<Categoria[]>('/categorias'), staleTime: CINCO_MINUTOS })
}

export function useMarcas() {
  return useQuery({ queryKey: ['marcas'], queryFn: () => api<Marca[]>('/marcas'), staleTime: CINCO_MINUTOS })
}

export function useProveedores() {
  return useQuery({ queryKey: ['proveedores'], queryFn: () => api<Proveedor[]>('/proveedores'), staleTime: CINCO_MINUTOS })
}

export function useCadenas() {
  return useQuery({ queryKey: ['cadenas'], queryFn: () => api<Cadena[]>('/cadenas'), staleTime: CINCO_MINUTOS })
}
