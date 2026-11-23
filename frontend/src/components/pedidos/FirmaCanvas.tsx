import { Eraser } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Boton } from '../ui'
import { useTranslation } from 'react-i18next'

/** Recuadro para firmar con el dedo. Entrega la firma como PNG (o null si está vacío). */
export function FirmaCanvas({ onCambio }: { onCambio: (firma: Blob | null) => void }) {
  const { t } = useTranslation()
  const lienzo = useRef<HTMLCanvasElement>(null)
  const dibujando = useRef(false)
  const [vacio, setVacio] = useState(true)

  useEffect(() => {
    const c = lienzo.current
    if (!c) return
    const escala = window.devicePixelRatio || 1
    c.width = c.clientWidth * escala
    c.height = c.clientHeight * escala
    const ctx = c.getContext('2d')
    if (!ctx) return
    ctx.scale(escala, escala)
    ctx.lineWidth = 2.2
    ctx.lineCap = 'round'
    ctx.lineJoin = 'round'
    ctx.strokeStyle = '#0f172a'
  }, [])

  const punto = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const r = e.currentTarget.getBoundingClientRect()
    return { x: e.clientX - r.left, y: e.clientY - r.top }
  }

  const terminar = () => {
    if (!dibujando.current) return
    dibujando.current = false
    lienzo.current?.toBlob((blob) => onCambio(blob), 'image/png')
  }

  const limpiar = () => {
    const c = lienzo.current
    c?.getContext('2d')?.clearRect(0, 0, c.width, c.height)
    setVacio(true)
    onCambio(null)
  }

  return (
    <div className="space-y-1">
      <canvas
        ref={lienzo}
        aria-label={t("Recuadro de firma")}
        className="h-36 w-full touch-none rounded-md border border-dashed border-slate-400"
        style={{ background: '#ffffff' }} // la firma se dibuja en tinta oscura: fondo blanco también en modo oscuro
        onPointerDown={(e) => {
          e.currentTarget.setPointerCapture(e.pointerId)
          const ctx = e.currentTarget.getContext('2d')
          const p = punto(e)
          ctx?.beginPath()
          ctx?.moveTo(p.x, p.y)
          dibujando.current = true
          setVacio(false)
        }}
        onPointerMove={(e) => {
          if (!dibujando.current) return
          const ctx = e.currentTarget.getContext('2d')
          const p = punto(e)
          ctx?.lineTo(p.x, p.y)
          ctx?.stroke()
        }}
        onPointerUp={terminar}
        onPointerCancel={terminar}
      />
      <div className="flex items-center justify-between text-xs text-slate-500">
        <span>{vacio ? t("Firme dentro del recuadro (opcional).") : t("Firma registrada.")}</span>
        <Boton variante="fantasma" className="min-h-7 px-2" onClick={limpiar} disabled={vacio}>
          <Eraser size={14} /> {t("Borrar")}
        </Boton>
      </div>
    </div>
  )
}
