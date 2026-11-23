import { Fragment, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

/** Vuelve a montar su contenido al cambiar de idioma: textos, fechas y montos cambian de una
 * vez (la URL y los datos en caché se conservan). */
export function ConIdioma({ children }: { children: ReactNode }) {
  const { i18n } = useTranslation()
  return <Fragment key={i18n.resolvedLanguage}>{children}</Fragment>
}
