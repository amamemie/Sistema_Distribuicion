/** Componentes básicos de interfaz. Colores y medidas: docs/DESIGN.md. */
import {
  forwardRef,
  useEffect,
  useRef,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
} from 'react'
import { useTranslation } from 'react-i18next'
import { X } from 'lucide-react'

function cx(...clases: (string | false | null | undefined)[]) {
  return clases.filter(Boolean).join(' ')
}

type Variante = 'primario' | 'secundario' | 'peligro' | 'fantasma'

const VARIANTES: Record<Variante, string> = {
  primario: 'bg-acento text-sobre-acento shadow-sm hover:bg-acento-hover disabled:opacity-60',
  secundario: 'border border-linea bg-superficie text-tinta shadow-sm hover:border-linea-fuerte/50 hover:bg-superficie-2 disabled:opacity-60',
  peligro: 'bg-red-600 text-white shadow-sm hover:bg-red-700 disabled:opacity-60',
  fantasma: 'text-tinta-2 hover:bg-superficie-2 hover:text-tinta disabled:opacity-50',
}

export function Boton({
  variante = 'primario',
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variante?: Variante }) {
  return (
    <button
      type="button"
      className={cx(
        'inline-flex min-h-10 items-center justify-center gap-2 rounded-lg px-4 text-sm font-medium select-none',
        'transition-[background-color,border-color,color,transform,box-shadow] duration-150 ease-salida',
        'active:translate-y-px disabled:cursor-not-allowed disabled:active:translate-y-0',
        VARIANTES[variante],
        className,
      )}
      {...props}
    />
  )
}

const CLASE_CAMPO =
  'block w-full min-h-10 rounded-lg border border-linea-fuerte/70 bg-superficie px-3 text-sm text-tinta ' +
  'placeholder:text-tinta-3 transition-[border-color,box-shadow] duration-150 ' +
  'focus-visible:border-acento focus-visible:ring-3 focus-visible:ring-acento/25 focus-visible:outline-none ' +
  'disabled:bg-superficie-2 disabled:text-tinta-3 aria-invalid:border-peligro max-sm:min-h-11 max-sm:text-base'

export const Entrada = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  function Entrada({ className, ...props }, ref) {
    return <input ref={ref} className={cx(CLASE_CAMPO, className)} {...props} />
  },
)

export const Selector = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  function Selector({ className, ...props }, ref) {
    return <select ref={ref} className={cx(CLASE_CAMPO, 'pr-8', className)} {...props} />
  },
)

export function Campo({
  etiqueta,
  error,
  children,
  ayuda,
}: {
  etiqueta: string
  error?: string
  ayuda?: string
  children: ReactNode
}) {
  return (
    <label className="block space-y-1.5">
      <span className="text-[13px] font-medium text-tinta-2">{etiqueta}</span>
      {children}
      {ayuda && !error && <span className="block text-xs text-tinta-3">{ayuda}</span>}
      {error && (
        <span className="block text-xs font-medium text-peligro" role="alert">
          {error}
        </span>
      )}
    </label>
  )
}

export function Aviso({ tipo = 'error', children }: { tipo?: 'error' | 'exito'; children: ReactNode }) {
  return (
    <div
      role={tipo === 'error' ? 'alert' : 'status'}
      aria-live={tipo === 'error' ? 'assertive' : 'polite'}
      className={cx(
        'rounded-lg border px-3 py-2 text-sm',
        tipo === 'error'
          ? 'border-peligro/25 bg-peligro-suave text-peligro'
          : 'border-exito/25 bg-exito-suave text-exito',
      )}
    >
      {children}
    </div>
  )
}

type Tono = 'gris' | 'verde' | 'rojo' | 'azul' | 'ambar' | 'acento'

const TONOS: Record<Tono, string> = {
  gris: 'bg-superficie-2 text-tinta-2',
  verde: 'bg-exito-suave text-exito',
  rojo: 'bg-peligro-suave text-peligro',
  azul: 'bg-info-suave text-info',
  ambar: 'bg-aviso-suave text-aviso',
  acento: 'bg-acento-suave text-acento',
}

/** Insignia de estado: punto de color + texto (el estado nunca depende solo del color). */
export function Insignia({ children, tono = 'gris' }: { children: ReactNode; tono?: Tono }) {
  return (
    <span
      className={cx(
        'inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-xs font-medium whitespace-nowrap',
        'before:size-1.5 before:shrink-0 before:rounded-full before:bg-current',
        TONOS[tono],
      )}
    >
      {children}
    </span>
  )
}

export function Tarjeta({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cx('rounded-xl border border-linea bg-superficie', className)}>{children}</div>
}

export function Encabezado({
  titulo,
  descripcion,
  acciones,
}: {
  titulo: string
  descripcion?: string
  acciones?: ReactNode
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div className="min-w-0">
        <h1 className="text-[22px] leading-tight font-semibold tracking-[-0.4px] text-tinta sm:text-2xl">{titulo}</h1>
        {descripcion && <p className="mt-1 max-w-2xl text-sm text-tinta-3">{descripcion}</p>}
      </div>
      {acciones}
    </div>
  )
}

/** Tabla con desplazamiento horizontal propio para no romper el ancho en móviles. */
export function Tabla({ children }: { children: ReactNode }) {
  return (
    <Tarjeta className="overflow-x-auto">
      <table className="w-full text-left text-sm tabular-nums [&_td]:px-4 [&_td]:py-3 [&_th]:px-4 [&_th]:py-2.5 [&_tbody_tr]:transition-colors [&_tbody_tr:hover]:bg-superficie-2/60">
        {children}
      </table>
    </Tarjeta>
  )
}

export function Modal({
  abierto,
  titulo,
  onCerrar,
  children,
}: {
  abierto: boolean
  titulo: string
  onCerrar: () => void
  children: ReactNode
}) {
  const { t } = useTranslation()
  const ref = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    const dialogo = ref.current
    if (!dialogo) return
    if (abierto && !dialogo.open) dialogo.showModal()
    if (!abierto && dialogo.open) dialogo.close()
  }, [abierto])

  return (
    <dialog
      ref={ref}
      onClose={onCerrar}
      aria-label={titulo}
      className="m-auto w-[calc(100%-2rem)] max-w-lg rounded-2xl border border-linea bg-superficie p-0 text-tinta shadow-[var(--sombra-3)]"
    >
      {abierto && (
        <div>
          <div className="flex items-center justify-between gap-3 border-b border-linea px-5 py-4">
            <h2 className="text-[17px] font-semibold tracking-[-0.2px]">{titulo}</h2>
            <Boton variante="fantasma" className="min-h-9 px-2" onClick={onCerrar} aria-label={t('Cerrar')}>
              <X size={18} aria-hidden />
            </Boton>
          </div>
          <div className="max-h-[75dvh] overflow-y-auto overscroll-contain px-5 py-4">{children}</div>
        </div>
      )}
    </dialog>
  )
}

export function Casilla({
  etiqueta,
  descripcion,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { etiqueta: string; descripcion?: string }) {
  return (
    <label className="flex cursor-pointer items-start gap-2.5 py-1 text-sm">
      <input type="checkbox" className="mt-0.5 size-4 shrink-0 rounded border-linea-fuerte accent-[var(--t-acento)]" {...props} />
      <span>
        <span className="text-tinta">{etiqueta}</span>
        {descripcion && <span className="block text-xs text-tinta-3">{descripcion}</span>}
      </span>
    </label>
  )
}

export function Paginador({
  pagina,
  total,
  tamano,
  onCambio,
}: {
  pagina: number
  total: number
  tamano: number
  onCambio: (pagina: number) => void
}) {
  const { t } = useTranslation()
  const paginas = Math.max(1, Math.ceil(total / tamano))
  return (
    <div className="mt-4 flex flex-wrap items-center justify-between gap-2 text-sm text-tinta-3">
      <span className="tabular-nums">{t('{{n}} registros', { n: total })}</span>
      <div className="flex items-center gap-2">
        <Boton variante="secundario" disabled={pagina <= 1} onClick={() => onCambio(pagina - 1)}>
          {t('Anterior')}
        </Boton>
        <span className="tabular-nums">
          {pagina} / {paginas}
        </span>
        <Boton variante="secundario" disabled={pagina >= paginas} onClick={() => onCambio(pagina + 1)}>
          {t('Siguiente')}
        </Boton>
      </div>
    </div>
  )
}

export function Vacio({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-xl border border-dashed border-linea-fuerte/40 bg-superficie/50 px-6 py-10 text-center text-sm text-tinta-3">
      {children}
    </div>
  )
}

/** Esqueleto de carga para filas o bloques mientras llegan los datos. */
export function Esqueleto({ className }: { className?: string }) {
  return <div aria-hidden className={cx('esqueleto rounded-md', className ?? 'h-4 w-full')} />
}

export const CABECERA_TABLA =
  'border-b border-linea bg-superficie-2 text-[11px] font-semibold tracking-[0.6px] uppercase text-tinta-3'
