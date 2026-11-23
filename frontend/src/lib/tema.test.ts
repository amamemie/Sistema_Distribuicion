import { describe, expect, it } from 'vitest'
import { leerTema, siguienteTema } from './tema'

describe('tema', () => {
  it('el botón recorre claro → oscuro → sistema → claro', () => {
    expect(siguienteTema('claro')).toBe('oscuro')
    expect(siguienteTema('oscuro')).toBe('sistema')
    expect(siguienteTema('sistema')).toBe('claro')
  })

  it('sin almacenamiento disponible sigue el tema del sistema', () => {
    expect(leerTema()).toBe('sistema')
  })
})
