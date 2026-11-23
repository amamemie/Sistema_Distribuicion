/** Idiomas de la interfaz (español por defecto, inglés).
 *
 * Las claves son el propio texto en español: `t('Nuevo pedido')`. Así el español no necesita
 * archivo (se muestra la clave) y `en.json` traduce cada frase. Con variables:
 * `t('Hola, {{nombre}}', { nombre })`. Los datos del negocio (productos, clientes, números de
 * documento) no se traducen.
 */
import i18n from 'i18next'
import LanguageDetector from 'i18next-browser-languagedetector'
import { initReactI18next } from 'react-i18next'
import en from './en.json'

export const IDIOMAS = ['es', 'en'] as const
export type Idioma = (typeof IDIOMAS)[number]

void i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: { es: { translation: {} }, en: { translation: en } },
    fallbackLng: 'es',
    supportedLngs: IDIOMAS,
    nonExplicitSupportedLngs: true,
    load: 'languageOnly',
    keySeparator: false,
    nsSeparator: false,
    returnEmptyString: false,
    interpolation: { escapeValue: false },
    detection: { order: ['localStorage', 'navigator'], lookupLocalStorage: 'idioma', caches: ['localStorage'] },
  })

function alCambiar(idioma: string) {
  if (typeof document !== 'undefined') document.documentElement.lang = idioma
}
alCambiar(i18n.resolvedLanguage ?? 'es')
i18n.on('languageChanged', alCambiar)

/** Idioma activo, reducido a los soportados. */
export function idiomaActual(): Idioma {
  return i18n.resolvedLanguage === 'en' ? 'en' : 'es'
}

/** Configuración regional para Intl según el idioma. */
export function locale(): string {
  return idiomaActual() === 'en' ? 'en-US' : 'es-BO'
}

export default i18n
