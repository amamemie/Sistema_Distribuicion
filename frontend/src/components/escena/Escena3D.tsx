/** Escena 3D (three.js + React Three Fiber). Se carga en un chunk aparte, solo en el login y en
 * la portada del inicio. Tope de 30 cuadros por segundo y pausa cuando no se ve. */
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { useEffect, useMemo, useRef, useState } from 'react'
import * as THREE from 'three'
import { DISENOS, puntoRuta, type Caja, type Diseno } from './datos'

interface Colores {
  caja: string
  caja2: string
  cinta: string
  ruta: string
  nodo: string
}

function leerColores(): Colores {
  const css = getComputedStyle(document.documentElement)
  const v = (n: string) => css.getPropertyValue(n).trim() || '#888888'
  return { caja: v('--escena-caja'), caja2: v('--escena-caja-3'), cinta: v('--escena-cinta'), ruta: v('--escena-ruta'), nodo: v('--t-superficie') }
}

/** Colores del tema actual; se vuelven a leer cuando cambia la clase `dark`. */
function useColores(): Colores {
  const [colores, setColores] = useState(leerColores)
  useEffect(() => {
    const observador = new MutationObserver(() => setColores(leerColores()))
    observador.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] })
    return () => observador.disconnect()
  }, [])
  return colores
}

/** Pide cuadros a ~30 fps solo mientras la escena está visible y la pestaña activa. */
function Ritmo({ visible }: { visible: boolean }) {
  const invalidate = useThree((s) => s.invalidate)
  useEffect(() => {
    if (!visible) return
    let id = 0
    const tick = () => {
      if (!document.hidden) invalidate()
    }
    id = window.setInterval(tick, 1000 / 30)
    return () => window.clearInterval(id)
  }, [visible, invalidate])
  return null
}

function Paquete({ caja, diseno, colores }: { caja: Caja; diseno: Diseno; colores: Colores }) {
  const grupo = useRef<THREE.Group>(null)
  const [x, , z] = diseno.nodos[caja.nodo]
  useFrame(({ clock }) => {
    if (!grupo.current) return
    const t = clock.elapsedTime * 0.6 + caja.fase
    grupo.current.position.y = 0.45 + caja.alto / 2 + Math.sin(t) * 0.12
    grupo.current.rotation.y = Math.sin(t * 0.5) * 0.08
  })
  return (
    <group ref={grupo} position={[x, 0.45 + caja.alto / 2, z]}>
      <mesh castShadow>
        <boxGeometry args={[caja.ancho, caja.alto, caja.fondo]} />
        <meshStandardMaterial color={colores.caja} roughness={0.85} />
      </mesh>
      {/* Cinta: tira sobre la tapa y bajando por el frente */}
      <mesh position={[0, caja.alto / 2 + 0.006, 0]}>
        <boxGeometry args={[caja.ancho * 0.16, 0.012, caja.fondo + 0.012]} />
        <meshStandardMaterial color={colores.cinta} roughness={0.6} />
      </mesh>
      <mesh position={[0, 0, caja.fondo / 2 + 0.006]}>
        <boxGeometry args={[caja.ancho * 0.16, caja.alto + 0.012, 0.012]} />
        <meshStandardMaterial color={colores.cinta} roughness={0.6} />
      </mesh>
    </group>
  )
}

function Rutas({ diseno, colores }: { diseno: Diseno; colores: Colores }) {
  const lineas = useMemo(
    () =>
      diseno.rutas.map(([a, b]) => {
        const puntos = Array.from({ length: 33 }, (_, k) => new THREE.Vector3(...puntoRuta(diseno.nodos[a], diseno.nodos[b], k / 32)))
        const linea = new THREE.Line(new THREE.BufferGeometry().setFromPoints(puntos), new THREE.LineDashedMaterial({ dashSize: 0.08, gapSize: 0.18 }))
        linea.computeLineDistances()
        return linea
      }),
    [diseno],
  )
  useEffect(() => {
    for (const l of lineas) (l.material as THREE.LineDashedMaterial).color.set(colores.ruta)
  }, [lineas, colores.ruta])
  useEffect(
    () => () => {
      for (const l of lineas) {
        l.geometry.dispose()
        ;(l.material as THREE.Material).dispose()
      }
    },
    [lineas],
  )
  return (
    <>
      {lineas.map((l, i) => (
        <primitive key={i} object={l} />
      ))}
    </>
  )
}

/** Pulsos de luz que recorren las rutas: el inventario en movimiento. */
function Pulsos({ diseno, colores }: { diseno: Diseno; colores: Colores }) {
  const refs = useRef<(THREE.Mesh | null)[]>([])
  useFrame(({ clock }) => {
    diseno.rutas.forEach(([a, b], i) => {
      const m = refs.current[i]
      if (!m) return
      const t = (clock.elapsedTime * 0.18 + i * 0.37) % 1
      const ida = i % 2 === 0
      m.position.set(...puntoRuta(diseno.nodos[a], diseno.nodos[b], ida ? t : 1 - t))
      const s = 0.6 + Math.sin(t * Math.PI) * 0.6
      m.scale.setScalar(s)
    })
  })
  return (
    <>
      {diseno.rutas.map((_, i) => (
        <mesh key={i} ref={(m) => void (refs.current[i] = m)}>
          <sphereGeometry args={[0.07, 12, 12]} />
          <meshBasicMaterial color={colores.cinta} toneMapped={false} />
        </mesh>
      ))}
    </>
  )
}

function Nodos({ diseno, colores }: { diseno: Diseno; colores: Colores }) {
  return (
    <>
      {diseno.nodos.map(([x, , z], i) => (
        <group key={i} position={[x, 0.02, z]}>
          <mesh rotation={[-Math.PI / 2, 0, 0]}>
            <ringGeometry args={[0.1, 0.16, 32]} />
            <meshBasicMaterial color={colores.cinta} />
          </mesh>
          <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.001, 0]}>
            <circleGeometry args={[0.1, 32]} />
            <meshBasicMaterial color={colores.nodo} />
          </mesh>
        </group>
      ))}
    </>
  )
}

/** Mueve un poco la cámara siguiendo al puntero (solo con mouse): da profundidad sin distraer. */
function Camara({ diseno }: { diseno: Diseno }) {
  const objetivo = useRef({ x: 0, y: 0 })
  useEffect(() => {
    if (!matchMedia('(pointer: fine)').matches) return
    const mover = (e: PointerEvent) => {
      objetivo.current = { x: e.clientX / innerWidth - 0.5, y: e.clientY / innerHeight - 0.5 }
    }
    addEventListener('pointermove', mover)
    return () => removeEventListener('pointermove', mover)
  }, [])
  useFrame(({ camera }) => {
    const [cx, cy, cz] = diseno.camara
    camera.position.x += (cx + objetivo.current.x * 1.2 - camera.position.x) * 0.05
    camera.position.y += (cy - objetivo.current.y * 0.8 - camera.position.y) * 0.05
    camera.position.z += (cz - objetivo.current.x * 1.2 - camera.position.z) * 0.05
    camera.lookAt(...diseno.mira)
  })
  return null
}

export default function Escena3D({ variante, className = '' }: { variante: 'login' | 'portada'; className?: string }) {
  const diseno = DISENOS[variante]
  const colores = useColores()
  const caja = useRef<HTMLDivElement>(null)
  const [visible, setVisible] = useState(true)
  useEffect(() => {
    const el = caja.current
    if (!el) return
    const io = new IntersectionObserver(([e]) => setVisible(e.isIntersecting))
    io.observe(el)
    return () => io.disconnect()
  }, [])
  return (
    <div ref={caja} className={className} aria-hidden>
      <Canvas
        frameloop="demand"
        dpr={[1, 1.5]}
        gl={{ antialias: true, alpha: true, powerPreference: 'low-power' }}
        camera={{ position: diseno.camara, fov: 32, near: 0.1, far: 100 }}
        onCreated={({ camera }) => camera.lookAt(...diseno.mira)}
      >
        <Ritmo visible={visible} />
        <Camara diseno={diseno} />
        <ambientLight intensity={1.6} />
        <directionalLight position={[5, 9, 4]} intensity={2.2} />
        <directionalLight position={[-6, 4, -3]} intensity={0.5} />
        <Rutas diseno={diseno} colores={colores} />
        <Nodos diseno={diseno} colores={colores} />
        <Pulsos diseno={diseno} colores={colores} />
        {diseno.cajas.map((c) => (
          <Paquete key={c.nodo} caja={c} diseno={diseno} colores={colores} />
        ))}
      </Canvas>
    </div>
  )
}
