/** Escena de la distribuidora: depósitos y sucursales (nodos) unidos por rutas, con paquetes
 * encima. Las mismas coordenadas alimentan la escena 3D y su imagen fija (SVG isométrico). */

export type Punto = [number, number, number] // x, y (altura), z

export interface Caja {
  nodo: number
  ancho: number
  alto: number
  fondo: number
  fase: number // desfase de la flotación
}

export interface Diseno {
  nodos: Punto[]
  rutas: [number, number][]
  cajas: Caja[]
  camara: Punto
  mira: Punto
}

const c = (nodo: number, ancho: number, alto: number, fondo = ancho, fase = nodo * 0.9): Caja => ({ nodo, ancho, alto, fondo, fase })

export const DISENOS: Record<'login' | 'portada', Diseno> = {
  login: {
    nodos: [
      [-3.2, 0, -0.6],
      [-1.1, 0, -3.0],
      [2.0, 0, -2.4],
      [-2.0, 0, 2.2],
      [1.0, 0, 0.6],
      [3.3, 0, 0.4],
      [0.2, 0, 3.4],
    ],
    rutas: [
      [0, 1],
      [1, 2],
      [0, 3],
      [3, 4],
      [2, 5],
      [4, 5],
      [3, 6],
      [4, 6],
      [1, 4],
    ],
    cajas: [c(1, 0.9, 0.65), c(2, 1.15, 0.8), c(3, 0.8, 0.6), c(4, 1.4, 1.0, 1.2), c(5, 0.7, 0.5), c(0, 0.55, 0.42), c(6, 0.6, 0.45)],
    camara: [9, 8.5, 9],
    mira: [0, 0, 0],
  },
  portada: {
    nodos: [
      [-3.0, 0, 0.5],
      [-0.8, 0, -1.8],
      [1.8, 0, -0.6],
      [0.3, 0, 1.6],
      [3.0, 0, 1.4],
    ],
    rutas: [
      [0, 1],
      [1, 2],
      [1, 3],
      [2, 4],
      [3, 4],
    ],
    cajas: [c(1, 0.8, 0.6), c(2, 1.0, 0.72), c(3, 0.7, 0.5), c(4, 1.2, 0.85)],
    camara: [6.6, 5.6, 6.6],
    mira: [0.5, 0.25, 0.1],
  },
}

/** Punto de la ruta entre dos nodos: un arco que se eleva en el medio. */
export function puntoRuta(a: Punto, b: Punto, t: number, altura = 0.9): Punto {
  return [a[0] + (b[0] - a[0]) * t, Math.sin(Math.PI * t) * altura, a[2] + (b[2] - a[2]) * t]
}

/** Proyección isométrica (para el SVG fijo). */
export function iso([x, y, z]: Punto, escala: number): [number, number] {
  return [(x - z) * 0.866 * escala, (x + z) * 0.5 * escala - y * escala]
}
