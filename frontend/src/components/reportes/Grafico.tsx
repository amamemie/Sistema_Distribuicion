import { useEffect, useRef, useState } from 'react'
import type { SerieReporte } from '../../lib/tipos'
import { COLORES_SERIE, formatear, formatoCorto, marcasEje } from '../../pages/reportes/utiles'

const ALTO = 240
const MARGEN = { arriba: 12, derecha: 12, abajo: 28, izquierda: 64 }

function useAncho<T extends HTMLElement>() {
  const ref = useRef<T>(null)
  const [ancho, setAncho] = useState(0)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const observador = new ResizeObserver(([e]) => setAncho(Math.floor(e.contentRect.width)))
    observador.observe(el)
    return () => observador.disconnect()
  }, [])
  return [ref, ancho] as const
}

const num = (v: unknown) => (v === null || v === undefined || v === '' ? null : Number(v))

/** Gráfico de una serie del reporte: por tiempo (barras o líneas) o ranking (barras horizontales). */
export function Grafico({ serie }: { serie: SerieReporte }) {
  const vacia = serie.puntos.every((p) => serie.claves.every((c) => !num(p[c.clave])))
  return (
    <figure className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <figcaption className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <span className="text-sm font-semibold text-slate-800">{serie.titulo}</span>
        {serie.claves.length > 1 && <Leyenda serie={serie} />}
      </figcaption>
      {vacia ? (
        <p className="py-10 text-center text-sm text-slate-500">Sin datos en el período.</p>
      ) : serie.eje === 'categoria' ? (
        <Ranking serie={serie} />
      ) : (
        <PorTiempo serie={serie} />
      )}
    </figure>
  )
}

function Leyenda({ serie }: { serie: SerieReporte }) {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600">
      {serie.claves.map((c, i) => (
        <li key={c.clave} className="inline-flex items-center gap-1.5">
          <span
            aria-hidden
            className={serie.forma === 'linea' && serie.eje === 'tiempo' ? 'h-0.5 w-4 rounded' : 'size-2.5 rounded-sm'}
            style={{ background: COLORES_SERIE[i % COLORES_SERIE.length] }}
          />
          {c.titulo}
        </li>
      ))}
    </ul>
  )
}

/** Barra con el extremo de datos redondeado (4px) y la base recta sobre el eje. */
function barra(x: number, y0: number, y1: number, ancho: number): string {
  const alto = Math.abs(y1 - y0)
  const r = Math.min(4, ancho / 2, alto)
  if (y1 <= y0) {
    return `M${x},${y0}V${y1 + r}Q${x},${y1} ${x + r},${y1}H${x + ancho - r}Q${x + ancho},${y1} ${x + ancho},${y1 + r}V${y0}Z`
  }
  return `M${x},${y0}V${y1 - r}Q${x},${y1} ${x + r},${y1}H${x + ancho - r}Q${x + ancho},${y1} ${x + ancho},${y1 - r}V${y0}Z`
}

function PorTiempo({ serie }: { serie: SerieReporte }) {
  const [ref, ancho] = useAncho<HTMLDivElement>()
  const [activo, setActivo] = useState<number | null>(null)
  const n = serie.puntos.length
  const valores = serie.puntos.flatMap((p) => serie.claves.map((c) => num(p[c.clave]) ?? 0))
  const marcas = marcasEje(Math.min(...valores), Math.max(...valores))
  const [minimo, maximo] = [marcas[0], marcas[marcas.length - 1]]
  const plotW = Math.max(ancho - MARGEN.izquierda - MARGEN.derecha, 10)
  const plotH = ALTO - MARGEN.arriba - MARGEN.abajo
  const y = (v: number) => MARGEN.arriba + plotH - ((v - minimo) / (maximo - minimo || 1)) * plotH
  const banda = plotW / Math.max(n, 1)
  const cx = (i: number) => MARGEN.izquierda + banda * (i + 0.5)
  const cada = Math.max(1, Math.ceil((n * 72) / plotW)) // etiquetas del eje x sin encimarse
  const lineas = serie.forma === 'linea'
  const m = serie.claves.length
  const anchoBarra = Math.max(2, Math.min(28, (banda * 0.72 - (m - 1) * 2) / m))

  const mover = (clientX: number, rect: DOMRect) => {
    const i = Math.floor((clientX - rect.left - MARGEN.izquierda) / banda)
    setActivo(i >= 0 && i < n ? i : null)
  }

  return (
    <div ref={ref} className="relative">
      {ancho > 0 && (
        <svg
          width={ancho}
          height={ALTO}
          role="img"
          aria-label={`${serie.titulo}. Los valores están en la tabla del reporte.`}
          onPointerMove={(e) => mover(e.clientX, e.currentTarget.getBoundingClientRect())}
          onPointerLeave={() => setActivo(null)}
          className="touch-pan-y select-none"
        >
          {marcas.map((v) => (
            <g key={v}>
              <line x1={MARGEN.izquierda} x2={ancho - MARGEN.derecha} y1={y(v)} y2={y(v)} stroke={v === 0 ? 'var(--color-slate-400)' : 'var(--color-slate-200)'} strokeWidth={1} />
              <text x={MARGEN.izquierda - 8} y={y(v)} dy="0.32em" textAnchor="end" className="fill-slate-500 text-[11px] tabular-nums">
                {formatoCorto(v, serie.tipo)}
              </text>
            </g>
          ))}
          {serie.puntos.map((p, i) =>
            i % cada === 0 ? (
              <text key={i} x={cx(i)} y={ALTO - 8} textAnchor="middle" className="fill-slate-500 text-[11px]">
                {String(p.etiqueta)}
              </text>
            ) : null,
          )}
          {activo !== null && <rect x={MARGEN.izquierda + banda * activo} y={MARGEN.arriba} width={banda} height={plotH} fill="var(--color-slate-100)" />}
          {lineas
            ? serie.claves.map((c, k) => {
                const color = COLORES_SERIE[k % COLORES_SERIE.length]
                const d = serie.puntos
                  .map((p, i) => {
                    const v = num(p[c.clave])
                    return v === null ? null : `${cx(i)},${y(v)}`
                  })
                  .filter(Boolean)
                  .join('L')
                return (
                  <g key={c.clave}>
                    <path d={`M${d}`} fill="none" stroke={color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
                    {activo !== null && num(serie.puntos[activo][c.clave]) !== null && (
                      <circle cx={cx(activo)} cy={y(num(serie.puntos[activo][c.clave]) ?? 0)} r={4.5} fill={color} stroke="var(--superficie)" strokeWidth={2} />
                    )}
                  </g>
                )
              })
            : serie.puntos.map((p, i) => {
                const inicio = cx(i) - (m * anchoBarra + (m - 1) * 2) / 2
                return serie.claves.map((c, k) => {
                  const v = num(p[c.clave]) ?? 0
                  if (v === 0) return null
                  return (
                    <path
                      key={`${i}-${c.clave}`}
                      d={barra(inicio + k * (anchoBarra + 2), y(0), y(v), anchoBarra)}
                      fill={COLORES_SERIE[k % COLORES_SERIE.length]}
                    />
                  )
                })
              })}
        </svg>
      )}
      {activo !== null && (
        <div
          role="status"
          className="pointer-events-none absolute top-1 z-10 min-w-40 rounded-md border border-slate-200 bg-white px-3 py-2 text-xs shadow-lg"
          style={cx(activo) > ancho / 2 ? { right: ancho - cx(activo) + 12 } : { left: cx(activo) + 12 }}
        >
          <p className="mb-1 font-semibold text-slate-800">{String(serie.puntos[activo].etiqueta)}</p>
          {serie.claves.map((c, k) => (
            <p key={c.clave} className="flex items-center justify-between gap-3 text-slate-600">
              <span className="inline-flex items-center gap-1.5">
                <span aria-hidden className="size-2 rounded-sm" style={{ background: COLORES_SERIE[k % COLORES_SERIE.length] }} />
                {c.titulo}
              </span>
              <span className="font-medium text-slate-900 tabular-nums">{formatear(serie.puntos[activo][c.clave], c.tipo)}</span>
            </p>
          ))}
        </div>
      )}
    </div>
  )
}

/** Ranking: una fila por categoría, con el nombre, la barra y el valor visible. */
function Ranking({ serie }: { serie: SerieReporte }) {
  const maximo = Math.max(...serie.puntos.flatMap((p) => serie.claves.map((c) => Math.abs(num(p[c.clave]) ?? 0))), 1)
  return (
    <ol className="space-y-2.5">
      {serie.puntos.map((p, i) => (
        <li key={i} className="grid grid-cols-[minmax(0,1fr)] gap-1 sm:grid-cols-[minmax(0,14rem)_minmax(0,1fr)] sm:items-center sm:gap-3">
          <span className="truncate text-xs text-slate-700" title={String(p.etiqueta)}>
            {String(p.etiqueta)}
          </span>
          <span className="space-y-1">
            {serie.claves.map((c, k) => {
              const v = num(p[c.clave]) ?? 0
              return (
                <span key={c.clave} className="flex items-center gap-2" title={`${c.titulo}: ${formatear(p[c.clave], c.tipo)}`}>
                  <span
                    className="h-2.5 rounded-r"
                    style={{ width: `${Math.max(0.5, (Math.abs(v) / maximo) * 80)}%`, background: COLORES_SERIE[k % COLORES_SERIE.length] }}
                  />
                  <span className="shrink-0 text-xs text-slate-600 tabular-nums">{formatear(p[c.clave], c.tipo)}</span>
                </span>
              )
            })}
          </span>
        </li>
      ))}
    </ol>
  )
}
