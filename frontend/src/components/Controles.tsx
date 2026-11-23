/** Controles del encabezado: idioma, tema y menú del usuario. */
import { KeyRound, LogOut, Monitor, Moon, Package, Sun, type LucideIcon } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { IDIOMAS, idiomaActual, type Idioma } from '../i18n'
import { siguienteTema, useTema, type Tema } from '../lib/tema'

/** Marca del sistema (cuadro turquesa con un paquete). */
export function Marca({ tamano = 32 }: { tamano?: number }) {
  return (
    <span
      aria-hidden
      className="inline-grid shrink-0 place-items-center rounded-lg bg-acento text-sobre-acento shadow-sm"
      style={{ width: tamano, height: tamano }}
    >
      <Package size={Math.round(tamano * 0.55)} strokeWidth={2} />
    </span>
  )
}

/** Selector de idioma ES / EN (se recuerda en el navegador). */
export function SelectorIdioma({ className = '' }: { className?: string }) {
  const { t, i18n } = useTranslation()
  const actual = idiomaActual()
  return (
    <div role="group" aria-label={t('Idioma')} className={`inline-flex overflow-hidden rounded-lg border border-linea bg-superficie ${className}`}>
      {IDIOMAS.map((idioma: Idioma) => (
        <button
          key={idioma}
          type="button"
          lang={idioma}
          aria-pressed={actual === idioma}
          onClick={() => void i18n.changeLanguage(idioma)}
          className={`min-h-8 px-2.5 text-xs font-semibold uppercase transition-colors ${
            actual === idioma ? 'bg-acento-suave text-acento' : 'text-tinta-3 hover:bg-superficie-2 hover:text-tinta'
          }`}
        >
          {idioma}
        </button>
      ))}
    </div>
  )
}

const TEMAS: Record<Tema, { icono: LucideIcon; texto: string }> = {
  claro: { icono: Sun, texto: 'Tema claro' },
  oscuro: { icono: Moon, texto: 'Tema oscuro' },
  sistema: { icono: Monitor, texto: 'Tema del sistema' },
}

/** Botón de tema: claro → oscuro → sistema. */
export function BotonTema() {
  const { t } = useTranslation()
  const [tema, setTema] = useTema()
  const Icono = TEMAS[tema].icono
  const siguiente = siguienteTema(tema)
  return (
    <button
      type="button"
      onClick={() => setTema(siguiente)}
      aria-label={t('{{actual}}. Cambiar a {{siguiente}}', { actual: t(TEMAS[tema].texto), siguiente: t(TEMAS[siguiente].texto).toLowerCase() })}
      title={t(TEMAS[tema].texto)}
      className="inline-grid size-9 place-items-center rounded-lg text-tinta-2 transition-colors hover:bg-superficie-2 hover:text-tinta"
    >
      <Icono size={18} aria-hidden />
    </button>
  )
}

function iniciales(nombre?: string, apellido?: string): string {
  return `${nombre?.[0] ?? ''}${apellido?.[0] ?? ''}`.toUpperCase() || '?'
}

/** Avatar con menú: nombre, rol, cambiar contraseña y cerrar sesión. */
export function MenuUsuario({
  nombre,
  apellido,
  roles,
  onCambiarClave,
  onSalir,
}: {
  nombre?: string
  apellido?: string
  roles: string
  onCambiarClave: () => void
  onSalir: () => void
}) {
  const { t } = useTranslation()
  const [abierto, setAbierto] = useState(false)
  const caja = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!abierto) return
    const fuera = (e: MouseEvent) => {
      if (!caja.current?.contains(e.target as Node)) setAbierto(false)
    }
    const tecla = (e: KeyboardEvent) => e.key === 'Escape' && setAbierto(false)
    document.addEventListener('mousedown', fuera)
    document.addEventListener('keydown', tecla)
    return () => {
      document.removeEventListener('mousedown', fuera)
      document.removeEventListener('keydown', tecla)
    }
  }, [abierto])

  const opcion =
    'flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-left text-sm text-tinta-2 transition-colors hover:bg-superficie-2 hover:text-tinta'
  return (
    <div ref={caja} className="relative">
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={abierto}
        aria-label={t('Menú de {{nombre}}', { nombre: `${nombre ?? ''} ${apellido ?? ''}`.trim() })}
        onClick={() => setAbierto((v) => !v)}
        className="flex items-center gap-2 rounded-lg p-1 transition-colors hover:bg-superficie-2 sm:pr-2.5"
      >
        <span className="inline-grid size-8 place-items-center rounded-full bg-acento-suave text-[13px] font-semibold text-acento">
          {iniciales(nombre, apellido)}
        </span>
        <span className="hidden text-left leading-tight sm:block">
          <span className="block text-sm font-medium text-tinta">
            {nombre} {apellido}
          </span>
          <span className="block text-xs text-tinta-3">{roles}</span>
        </span>
      </button>
      {abierto && (
        <div
          role="menu"
          className="absolute right-0 z-40 mt-2 w-60 origin-top-right animate-[menu-entra_.18s_var(--ease-entrada)] rounded-xl border border-linea bg-superficie p-1.5 shadow-[var(--sombra-3)]"
        >
          <div className="border-b border-linea px-2.5 pt-1.5 pb-2.5 sm:hidden">
            <div className="text-sm font-medium">
              {nombre} {apellido}
            </div>
            <div className="text-xs text-tinta-3">{roles}</div>
          </div>
          <button role="menuitem" type="button" className={opcion} onClick={() => (setAbierto(false), onCambiarClave())}>
            <KeyRound size={16} aria-hidden /> {t('Cambiar contraseña')}
          </button>
          <button role="menuitem" type="button" className={opcion} onClick={() => (setAbierto(false), onSalir())}>
            <LogOut size={16} aria-hidden /> {t('Cerrar sesión')}
          </button>
        </div>
      )}
    </div>
  )
}
