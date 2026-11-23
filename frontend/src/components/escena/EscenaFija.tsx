/** Imagen fija de la escena (SVG isométrico). Se usa sin WebGL, en equipos lentos, con
 * movimiento reducido y mientras carga la escena 3D. Colores: variables --escena-* del tema. */
import { DISENOS, iso, puntoRuta, type Caja, type Punto } from './datos'

const ESCALA = 46

function poligono(puntos: Punto[]): string {
  return puntos.map((p) => iso(p, ESCALA).join(',')).join(' ')
}

function DibujoCaja({ caja, base }: { caja: Caja; base: Punto }) {
  const [x, , z] = base
  const w = caja.ancho / 2,
    d = caja.fondo / 2,
    h = caja.alto
  const y0 = 0.35 // los paquetes flotan un poco sobre el nodo
  const tapa: Punto[] = [
    [x - w, y0 + h, z - d],
    [x + w, y0 + h, z - d],
    [x + w, y0 + h, z + d],
    [x - w, y0 + h, z + d],
  ]
  const frente: Punto[] = [
    [x - w, y0 + h, z + d],
    [x + w, y0 + h, z + d],
    [x + w, y0, z + d],
    [x - w, y0, z + d],
  ]
  const lado: Punto[] = [
    [x + w, y0 + h, z - d],
    [x + w, y0 + h, z + d],
    [x + w, y0, z + d],
    [x + w, y0, z - d],
  ]
  const cw = w * 0.16
  const cintaTapa: Punto[] = [
    [x - cw, y0 + h, z - d],
    [x + cw, y0 + h, z - d],
    [x + cw, y0 + h, z + d],
    [x - cw, y0 + h, z + d],
  ]
  const cintaFrente: Punto[] = [
    [x - cw, y0 + h, z + d],
    [x + cw, y0 + h, z + d],
    [x + cw, y0, z + d],
    [x - cw, y0, z + d],
  ]
  const [sx, sy] = iso([x, 0, z], ESCALA)
  return (
    <g>
      <ellipse cx={sx} cy={sy} rx={(w + d) * ESCALA * 0.75} ry={(w + d) * ESCALA * 0.32} fill="rgb(0 0 0 / .10)" filter="url(#escena-difuso)" />
      <polygon points={poligono(frente)} fill="var(--escena-caja-2)" />
      <polygon points={poligono(lado)} fill="var(--escena-caja-3)" />
      <polygon points={poligono(tapa)} fill="var(--escena-caja)" />
      <polygon points={poligono(cintaTapa)} fill="var(--escena-cinta)" opacity={0.9} />
      <polygon points={poligono(cintaFrente)} fill="var(--escena-cinta)" opacity={0.6} />
    </g>
  )
}

export function EscenaFija({ variante, className = '' }: { variante: 'login' | 'portada'; className?: string }) {
  const d = DISENOS[variante]
  const proyectados = d.nodos.map((n) => iso(n, ESCALA))
  const xs = proyectados.map((p) => p[0]),
    ys = proyectados.map((p) => p[1])
  const margen = ESCALA * 1.6
  const caja = [Math.min(...xs) - margen, Math.min(...ys) - margen * 1.4, Math.max(...xs) - Math.min(...xs) + margen * 2, Math.max(...ys) - Math.min(...ys) + margen * 2.2]
  // Las cajas se dibujan de atrás hacia adelante para que se tapen bien.
  const cajas = [...d.cajas].sort((a, b) => d.nodos[a.nodo][0] + d.nodos[a.nodo][2] - (d.nodos[b.nodo][0] + d.nodos[b.nodo][2]))
  return (
    <svg viewBox={caja.join(' ')} preserveAspectRatio="xMidYMid meet" className={className} aria-hidden focusable="false">
      <defs>
        <filter id="escena-difuso" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="6" />
        </filter>
      </defs>
      {d.rutas.map(([a, b], i) => {
        const pts = Array.from({ length: 21 }, (_, k) => iso(puntoRuta(d.nodos[a], d.nodos[b], k / 20), ESCALA))
        const pulso = iso(puntoRuta(d.nodos[a], d.nodos[b], 0.3 + (i % 3) * 0.2), ESCALA)
        return (
          <g key={i}>
            <polyline points={pts.map((p) => p.join(',')).join(' ')} fill="none" stroke="var(--escena-ruta)" strokeWidth={1.5} strokeDasharray="2 6" />
            <circle cx={pulso[0]} cy={pulso[1]} r={4} fill="var(--escena-cinta)" />
          </g>
        )
      })}
      {proyectados.map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r={5} fill="var(--t-superficie)" stroke="var(--escena-cinta)" strokeWidth={2} />
      ))}
      {cajas.map((cj) => (
        <DibujoCaja key={cj.nodo} caja={cj} base={d.nodos[cj.nodo]} />
      ))}
    </svg>
  )
}
