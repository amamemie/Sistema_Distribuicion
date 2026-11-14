import { useQuery } from '@tanstack/react-query'
import { api, ErrorApi } from './api'
import type { UsuarioYo } from './tipos'

export const CLAVE_YO = ['yo'] as const

export function useYo() {
  return useQuery({
    queryKey: CLAVE_YO,
    queryFn: async () => {
      try {
        return await api<UsuarioYo>('/auth/yo')
      } catch (error) {
        if (error instanceof ErrorApi && error.status === 401) return null
        throw error
      }
    },
    staleTime: 5 * 60 * 1000,
    retry: false,
  })
}

export function usePuede(): (permiso: string) => boolean {
  const { data } = useYo()
  return (permiso) => data?.permisos.includes(permiso) ?? false
}
