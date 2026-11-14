import { describe, expect, it } from 'vitest'
import { construirUrl, leerCookie } from './api'
import { formatearFecha } from './formato'

describe('construirUrl', () => {
  it('antepone /api y omite parámetros vacíos', () => {
    expect(construirUrl('/auditoria', { entidad: 'usuario', accion: '', pagina: 2, x: null })).toBe(
      '/api/auditoria?entidad=usuario&pagina=2',
    )
  })

  it('funciona sin parámetros', () => {
    expect(construirUrl('/auth/yo')).toBe('/api/auth/yo')
  })
})

describe('leerCookie', () => {
  it('encuentra la cookie pedida', () => {
    expect(leerCookie('csrf_token', 'tema=claro; csrf_token=abc%3D123; otra=1')).toBe('abc=123')
  })

  it('devuelve null si no existe', () => {
    expect(leerCookie('csrf_token', 'tema=claro')).toBeNull()
  })
})

describe('formatearFecha', () => {
  it('usa la hora de La Paz', () => {
    expect(formatearFecha('2026-11-14T16:30:00Z')).toContain('12:30')
  })
})

describe('formatos numéricos', () => {
  it('formatea cantidades y bolivianos al estilo boliviano', async () => {
    const { formatearCantidad, formatearBs, formatearDia } = await import('./formato')
    expect(formatearCantidad('1200.000')).toBe('1.200')
    expect(formatearCantidad('2.500')).toBe('2,5')
    expect(formatearBs('1234.5')).toBe('Bs 1.234,50')
    expect(formatearCantidad(null)).toBe('—')
    expect(formatearDia('2026-11-01')).toContain('2026')
  })
})
