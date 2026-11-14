import { describe, expect, it } from 'vitest'
import { diferenciaLinea, numeroONulo, sumaLineas } from './calculos'
import { medidasReducidas } from '../../lib/imagenes'

describe('revisión de la OC', () => {
  it('convierte los números del formulario', () => {
    expect(numeroONulo(' 12,5 ')).toBe('12.5')
    expect(numeroONulo('')).toBeNull()
    expect(numeroONulo('abc')).toBeNull()
  })

  it('detecta cantidad × precio distinto del total impreso', () => {
    expect(diferenciaLinea({ cantidad_oc: '10', precio_oc: '2.5', total_linea_oc: '25' })).toBeNull()
    expect(diferenciaLinea({ cantidad_oc: '10', precio_oc: '2.5', total_linea_oc: '250' })).toContain('pero la OC dice')
    expect(diferenciaLinea({ cantidad_oc: '3', precio_oc: '1.3333', total_linea_oc: '4' })).toBeNull()
  })

  it('suma con el total impreso o el calculado', () => {
    expect(
      sumaLineas([
        { cantidad_oc: '10', precio_oc: '2.5', total_linea_oc: '' },
        { cantidad_oc: '1', precio_oc: '1', total_linea_oc: '0.10' },
      ]),
    ).toBe(25.1)
  })
})

describe('fotos', () => {
  it('reduce sin deformar ni agrandar', () => {
    expect(medidasReducidas(4000, 3000)).toEqual({ ancho: 2200, alto: 1650 })
    expect(medidasReducidas(800, 600)).toEqual({ ancho: 800, alto: 600 })
  })
})
