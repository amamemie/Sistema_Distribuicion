/** Componentes básicos de interfaz (Tailwind). */
import {
  forwardRef,
  useEffect,
  useRef,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
} from 'react'
import { X } from 'lucide-react'

function cx(...clases: (string | false | null | undefined)[]) {
  return clases.filter(Boolean).join(' ')
}

type Variante = 'primario' | 'secundario' | 'peligro' | 'fantasma'

const VARIANTES: Record<Variante, string> = {
  primario: 'bg-marca-700 text-white hover:bg-marca-800 disabled:bg-marca-700/60',
  secundario: 'border border-slate-300 bg-white text-slate-800 hover:bg-slate-50',
  peligro: 'bg-red-600 text-white hover:bg-red-700',
  fantasma: 'text-slate-600 hover:bg-slate-100',
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
        'inline-flex min-h-10 items-center justify-center gap-2 rounded-lg px-4 text-sm font-medium',
        'transition-colors focus-visible:outline-2 focus-visible:outline-offset-2',
        'focus-visible:outline-marca-600 disabled:cursor-not-allowed',
        VARIANTES[variante],
        className,
      )}
      {...props}
    />
  )
}

const CLASE_CAMPO =
  'block w-full min-h-10 rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-900 ' +
  'focus:border-marca-600 focus:ring-2 focus:ring-marca-100 focus:outline-none ' +
  'disabled:bg-slate-100 aria-invalid:border-red-500'

export const Entrada = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  function Entrada({ className, ...props }, ref) {
    return <input ref={ref} className={cx(CLASE_CAMPO, className)} {...props} />
  },
)

export const Selector = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  function Selector({ className, ...props }, ref) {
    return <select ref={ref} className={cx(CLASE_CAMPO, className)} {...props} />
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
    <label className="block space-y-1">
      <span className="text-sm font-medium text-slate-700">{etiqueta}</span>
      {children}
      {ayuda && !error && <span className="block text-xs text-slate-500">{ayuda}</span>}
      {error && <span className="block text-xs text-red-600">{error}</span>}
    </label>
  )
}

export function Aviso({ tipo = 'error', children }: { tipo?: 'error' | 'exito'; children: ReactNode }) {
  return (
    <div
      role={tipo === 'error' ? 'alert' : 'status'}
      className={cx(
        'rounded-md border px-3 py-2 text-sm',
        tipo === 'error'
          ? 'border-red-200 bg-red-50 text-red-800'
          : 'border-emerald-200 bg-emerald-50 text-emerald-800',
      )}
    >
      {children}
    </div>
  )
}

export function Insignia({
  children,
  tono = 'gris',
}: {
  children: ReactNode
  tono?: 'gris' | 'verde' | 'rojo' | 'azul' | 'ambar'
}) {
  const tonos = {
    gris: 'bg-slate-100 text-slate-700',
    verde: 'bg-emerald-100 text-emerald-800',
    rojo: 'bg-red-100 text-red-800',
    azul: 'bg-marca-100 text-marca-800',
    ambar: 'bg-amber-100 text-amber-800',
  }
  return (
    <span className={cx('inline-flex rounded-full px-2 py-0.5 text-xs font-medium', tonos[tono])}>
      {children}
    </span>
  )
}

export function Tarjeta({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cx('rounded-xl border border-slate-200 bg-white shadow-sm shadow-slate-900/5', className)}>
      {children}
    </div>
  )
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
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{titulo}</h1>
        {descripcion && <p className="mt-1 text-sm text-slate-600">{descripcion}</p>}
      </div>
      {acciones}
    </div>
  )
}

/** Tabla con desplazamiento horizontal propio para no romper el ancho en móviles. */
export function Tabla({ children }: { children: ReactNode }) {
  return (
    <Tarjeta className="overflow-x-auto">
      <table className="w-full text-left text-sm [&_td]:px-4 [&_td]:py-3 [&_th]:px-4 [&_th]:py-3">
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
      className="m-auto w-[calc(100%-2rem)] max-w-lg rounded-xl bg-white p-0 text-slate-900 shadow-xl"
    >
      {abierto && (
        <div>
          <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
            <h2 className="text-lg font-semibold">{titulo}</h2>
            <Boton variante="fantasma" className="px-2" onClick={onCerrar} aria-label="Cerrar">
              <X size={18} />
            </Boton>
          </div>
          <div className="max-h-[75dvh] overflow-y-auto px-5 py-4">{children}</div>
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
    <label className="flex items-start gap-2 py-1 text-sm">
      <input
        type="checkbox"
        className="mt-0.5 size-4 rounded border-slate-300 accent-marca-700"
        {...props}
      />
      <span>
        <span className="text-slate-800">{etiqueta}</span>
        {descripcion && <span className="block text-xs text-slate-500">{descripcion}</span>}
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
  const paginas = Math.max(1, Math.ceil(total / tamano))
  return (
    <div className="mt-4 flex items-center justify-between text-sm text-slate-600">
      <span>{total} registros</span>
      <div className="flex items-center gap-2">
        <Boton variante="secundario" disabled={pagina <= 1} onClick={() => onCambio(pagina - 1)}>
          Anterior
        </Boton>
        <span>
          {pagina} / {paginas}
        </span>
        <Boton variante="secundario" disabled={pagina >= paginas} onClick={() => onCambio(pagina + 1)}>
          Siguiente
        </Boton>
      </div>
    </div>
  )
}

export function Vacio({ children }: { children: ReactNode }) {
  return <div className="rounded-xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500">{children}</div>
}

export const CABECERA_TABLA = 'border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-500'
