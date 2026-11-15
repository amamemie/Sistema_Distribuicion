import { describe, expect, it } from 'vitest'
import { agrupacionSugerida, fechasDeRango, marcasEje } from './utiles'

describe('reportes', () => {
  it('rangos rápidos de fechas', () => {
    expect(fechasDeRango('mes', '2026-11-15')).toEqual({ desde: '2026-11-01', hasta: '2026-11-15' })
    expect(fechasDeRango('mes_anterior', '2026-11-15')).toEqual({ desde: '2026-10-01', hasta: '2026-10-31' })
    expect(fechasDeRango('mes_anterior', '2026-01-10')).toEqual({ desde: '2025-12-01', hasta: '2025-12-31' })
    expect(fechasDeRango('7', '2026-11-15')).toEqual({ desde: '2026-11-09', hasta: '2026-11-15' })
    expect(fechasDeRango('anio', '2026-11-15')).toEqual({ desde: '2026-01-01', hasta: '2026-11-15' })
  })

  it('agrupación según el largo del rango', () => {
    expect(agrupacionSugerida('2026-11-01', '2026-11-30')).toBe('dia')
    expect(agrupacionSugerida('2026-08-01', '2026-11-30')).toBe('semana')
    expect(agrupacionSugerida('2026-01-01', '2026-11-30')).toBe('mes')
  })

  it('marcas del eje redondas, con el cero', () => {
    expect(marcasEje(0, 230)).toEqual([0, 100, 200, 300])
    expect(marcasEje(-3, 0)).toEqual([-3, -2, -1, 0])
    expect(marcasEje(-40, 90)).toEqual([-50, 0, 50, 100])
    expect(marcasEje(0, 0)).toEqual([0, 1])
  })
})
