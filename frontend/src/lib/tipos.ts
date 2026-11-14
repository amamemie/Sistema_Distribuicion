/** Tipos de las respuestas de la API (reflejan los esquemas de Pydantic del backend). */

export type TipoUbicacion = 'DEPOSITO' | 'SUCURSAL'

export interface UbicacionResumen {
  id: string
  nombre: string
  tipo: TipoUbicacion
}

export interface Ubicacion extends UbicacionResumen {
  direccion: string | null
  telefono: string | null
  activo: boolean
}

export interface RolResumen {
  id: string
  nombre: string
}

export interface Rol extends RolResumen {
  descripcion: string | null
  es_sistema: boolean
  permisos: string[]
}

export interface Permiso {
  codigo: string
  modulo: string
  descripcion: string
}

export interface Usuario {
  id: string
  nombre: string
  apellido: string
  correo: string
  telefono: string | null
  activo: boolean
  ultimo_acceso: string | null
  ubicacion_predeterminada_id: string | null
  roles: RolResumen[]
  ubicaciones: UbicacionResumen[]
}

export interface UsuarioYo extends Usuario {
  permisos: string[]
}

export interface RegistroAuditoria {
  id: number
  fecha: string
  usuario_id: string | null
  usuario_nombre: string | null
  accion: string
  entidad: string
  entidad_id: string | null
  antes: Record<string, unknown> | null
  despues: Record<string, unknown> | null
  ip: string | null
}

export interface Pagina<T> {
  items: T[]
  total: number
  pagina: number
  tamano: number
}

export const NOMBRE_TIPO_UBICACION: Record<TipoUbicacion, string> = {
  DEPOSITO: 'Depósito',
  SUCURSAL: 'Sucursal',
}
