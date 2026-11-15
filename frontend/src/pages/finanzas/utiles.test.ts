import { describe, expect, it } from 'vitest'
import { agruparPorMes, aTextoBs, cuadra, nombreMes, primerDiaMes, sumarBs, ultimoDiaMes } from './utiles'

describe('utiles de finanzas', () => {
  it('nombra y delimita los meses', () => {
    expect(nombreMes('2026-11-05')).toBe('noviembre 2026')
    expect(primerDiaMes('2026-11')).toBe('2026-11-01')
    expect(ultimoDiaMes('2026-11')).toBe('2026-11-30')
    expect(ultimoDiaMes('2028-02')).toBe('2028-02-29')
    expect(ultimoDiaMes('2026-12')).toBe('2026-12-31')
  })

  it('agrupa por mes conservando el orden', () => {
    const grupos = agruparPorMes(['2026-10-22', '2026-10-30', '2026-11-02'], (f) => f)
    expect(grupos).toEqual([
      ['2026-10-01', ['2026-10-22', '2026-10-30']],
      ['2026-11-01', ['2026-11-02']],
    ])
  })

  it('suma y compara montos sin errores de coma flotante', () => {
    expect(sumarBs(['0.1', '0.2'])).toBe(0.3)
    expect(cuadra(['150.10', '80.20'], '230.3')).toBe(true)
    expect(cuadra(['150', '80'], '229.99')).toBe(false)
    expect(aTextoBs(230.3)).toBe('230.30')
  })
})
