/** Tema claro / oscuro. Se guarda en el navegador; «sistema» sigue la preferencia del equipo.
 * index.html aplica el tema antes de dibujar la página (sin destello blanco). */
import { useEffect, useState } from 'react'

export type Tema = 'claro' | 'oscuro' | 'sistema'

const CLAVE = 'tema'
const consulta = () => window.matchMedia('(prefers-color-scheme: dark)')

export function leerTema(): Tema {
  try {
    const valor = localStorage.getItem(CLAVE)
    return valor === 'claro' || valor === 'oscuro' ? valor : 'sistema'
  } catch {
    return 'sistema'
  }
}

export function esOscuro(tema: Tema): boolean {
  return tema === 'oscuro' || (tema === 'sistema' && consulta().matches)
}

export function aplicarTema(tema: Tema): void {
  const oscuro = esOscuro(tema)
  document.documentElement.classList.toggle('dark', oscuro)
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', oscuro ? '#0b1220' : '#1d4ed8')
}

/** Siguiente tema al tocar el botón: claro → oscuro → sistema → claro. */
export function siguienteTema(tema: Tema): Tema {
  return tema === 'claro' ? 'oscuro' : tema === 'oscuro' ? 'sistema' : 'claro'
}

export function useTema(): [Tema, (tema: Tema) => void] {
  const [tema, setTema] = useState<Tema>(leerTema)
  useEffect(() => {
    aplicarTema(tema)
    try {
      if (tema === 'sistema') localStorage.removeItem(CLAVE)
      else localStorage.setItem(CLAVE, tema)
    } catch {
      // Sin almacenamiento (modo privado): el tema dura hasta recargar.
    }
    if (tema !== 'sistema') return
    const media = consulta()
    const alCambiar = () => aplicarTema('sistema')
    media.addEventListener('change', alCambiar)
    return () => media.removeEventListener('change', alCambiar)
  }, [tema])
  return [tema, setTema]
}
