import { afterEach, describe, expect, it } from 'vitest'
import en from './en.json'
import i18n, { idiomaActual, locale } from './index'
import { formatearBs, formatearDia } from '../lib/formato'

describe('idiomas', () => {
  afterEach(() => i18n.changeLanguage('es'))

  it('el español usa el propio texto como clave y el inglés su traducción', async () => {
    await i18n.changeLanguage('es')
    expect(i18n.t('Nuevo pedido')).toBe('Nuevo pedido')
    expect(idiomaActual()).toBe('es')
    await i18n.changeLanguage('en')
    expect(i18n.t('Nuevo pedido')).toBe('New order')
    expect(i18n.t('{{n}} registros', { n: 3 })).toBe('3 records')
    expect(idiomaActual()).toBe('en')
  })

  it('formatea montos y fechas según el idioma', async () => {
    await i18n.changeLanguage('es')
    expect(locale()).toBe('es-BO')
    expect(formatearBs(1234.5)).toBe('Bs 1.234,50')
    await i18n.changeLanguage('en')
    expect(locale()).toBe('en-US')
    expect(formatearBs(1234.5)).toBe('Bs 1,234.50')
    expect(formatearDia('2026-11-23')).toBe('Nov 23, 2026')
  })

  it('cada traducción conserva sus variables', () => {
    for (const [clave, texto] of Object.entries(en as Record<string, string>)) {
      const vars = (s: string) => (s.match(/{{\w+}}/g) ?? []).sort().join()
      expect(vars(texto), clave).toBe(vars(clave))
    }
  })
})
