import { describe, expect, it } from 'vitest'
import { descuentoInicial, diferenciaLinea, numeroONulo, totalCalculado, totales } from './calculos'
import { medidasReducidas } from '../../lib/imagenes'

describe('revisión del pedido', () => {
  it('convierte los números del formulario', () => {
    expect(numeroONulo(' 12,5 ')).toBe('12.5')
    expect(numeroONulo('')).toBeNull()
    expect(numeroONulo('abc')).toBeNull()
  })

  it('calcula el total de la línea', () => {
    expect(totalCalculado({ cantidad_oc: '40', precio_oc: '19' })).toBe(760)
    expect(totalCalculado({ cantidad_oc: '48', precio_oc: '13.8' })).toBe(662.4)
    expect(totalCalculado({ cantidad_oc: '', precio_oc: '5' })).toBe(0)
  })

  it('avisa si el documento leído dice otro total de línea', () => {
    expect(diferenciaLinea({ cantidad_oc: '10', precio_oc: '2.5', impreso: '25' })).toBeNull()
    expect(diferenciaLinea({ cantidad_oc: '10', precio_oc: '2.5', impreso: '250' })).toContain('pero el documento dice')
    expect(diferenciaLinea({ cantidad_oc: '10', precio_oc: '2.5', impreso: '' })).toBeNull()
  })

  it('subtotal, descuento y total', () => {
    const lineas = [
      { cantidad_oc: '40', precio_oc: '19' },
      { cantidad_oc: '24', precio_oc: '8' },
    ]
    expect(totales(lineas, '')).toEqual({ subtotal: 952, descuento: 0, total: 952 })
    expect(totales(lineas, '52,5')).toEqual({ subtotal: 952, descuento: 52.5, total: 899.5 })
  })

  it('recupera el descuento de un pedido guardado', () => {
    expect(descuentoInicial(['760.00', '192.00'], '900.00')).toBe('52')
    expect(descuentoInicial(['760.00'], '760.00')).toBe('')
    expect(descuentoInicial(['760.00'], null)).toBe('')
  })
})

describe('fotos', () => {
  it('reduce sin deformar ni agrandar', () => {
    expect(medidasReducidas(4000, 3000)).toEqual({ ancho: 2200, alto: 1650 })
    expect(medidasReducidas(800, 600)).toEqual({ ancho: 800, alto: 600 })
  })
})
