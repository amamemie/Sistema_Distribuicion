import { Camera, FileUp, ImagePlus, X } from 'lucide-react'
import { useEffect, useMemo, useRef } from 'react'
import { comprimirImagen, esImagen } from '../../lib/imagenes'
import { formatearTamano } from '../../lib/formato'

const MAX_MB = 15

/** Elegir las páginas de la OC: cámara, galería o PDF. Las fotos se reducen antes de subir. */
export function SelectorArchivos({
  archivos,
  onCambio,
  onError,
  ocupado,
}: {
  archivos: File[]
  onCambio: (archivos: File[]) => void
  onError: (mensaje: string | null) => void
  ocupado?: (preparando: boolean) => void
}) {
  const camara = useRef<HTMLInputElement>(null)
  const galeria = useRef<HTMLInputElement>(null)
  const pdf = useRef<HTMLInputElement>(null)
  const vistas = useMemo(() => archivos.map((a) => (esImagen(a) ? URL.createObjectURL(a) : null)), [archivos])
  useEffect(() => () => vistas.forEach((v) => v && URL.revokeObjectURL(v)), [vistas])

  const agregar = async (lista: FileList | null) => {
    if (!lista?.length) return
    onError(null)
    ocupado?.(true)
    try {
      const nuevos: File[] = []
      for (const archivo of Array.from(lista)) {
        if (!esImagen(archivo) && archivo.type !== 'application/pdf') {
          onError(`«${archivo.name}» no es una foto ni un PDF.`)
          continue
        }
        const listo = await comprimirImagen(archivo)
        if (listo.size > MAX_MB * 1024 * 1024) {
          onError(`«${archivo.name}» supera ${MAX_MB} MB.`)
          continue
        }
        nuevos.push(listo)
      }
      onCambio([...archivos, ...nuevos])
    } finally {
      ocupado?.(false)
    }
  }

  const boton = 'flex flex-col items-center justify-center gap-1 rounded-lg border border-slate-300 bg-white px-2 py-4 text-sm font-medium text-slate-700 hover:bg-slate-50 active:bg-slate-100'
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-3 gap-2">
        <button type="button" className={boton} onClick={() => camara.current?.click()}>
          <Camera size={24} className="text-marca-700" /> Tomar foto
        </button>
        <button type="button" className={boton} onClick={() => galeria.current?.click()}>
          <ImagePlus size={24} className="text-marca-700" /> Galería
        </button>
        <button type="button" className={boton} onClick={() => pdf.current?.click()}>
          <FileUp size={24} className="text-marca-700" /> PDF
        </button>
      </div>
      <input ref={camara} type="file" accept="image/*" capture="environment" hidden onChange={(e) => { void agregar(e.target.files); e.target.value = '' }} />
      <input ref={galeria} type="file" accept="image/*" multiple hidden onChange={(e) => { void agregar(e.target.files); e.target.value = '' }} />
      <input ref={pdf} type="file" accept="application/pdf" multiple hidden onChange={(e) => { void agregar(e.target.files); e.target.value = '' }} />
      {archivos.length > 0 && (
        <ul className="grid grid-cols-3 gap-2 sm:grid-cols-4">
          {archivos.map((a, i) => (
            <li key={`${a.name}-${i}`} className="relative overflow-hidden rounded-md border border-slate-200 bg-slate-50">
              {vistas[i] ? (
                <img src={vistas[i]!} alt={a.name} className="aspect-[3/4] w-full object-cover" />
              ) : (
                <div className="flex aspect-[3/4] items-center justify-center text-xs font-semibold text-slate-500">PDF</div>
              )}
              <span className="absolute top-1 left-1 rounded bg-black/60 px-1.5 text-xs text-white">{i + 1}</span>
              <button
                type="button"
                aria-label={`Quitar ${a.name}`}
                className="absolute top-1 right-1 rounded-full bg-white/90 p-1 text-red-600 shadow"
                onClick={() => onCambio(archivos.filter((_, j) => j !== i))}
              >
                <X size={14} />
              </button>
              <span className="block truncate px-1 py-0.5 text-[11px] text-slate-600">{formatearTamano(a.size)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
