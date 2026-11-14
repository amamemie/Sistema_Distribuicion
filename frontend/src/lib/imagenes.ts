/** Reducción de fotos en el celular antes de subirlas: una foto de 4–8 MB queda en ~0,5 MB
 * sin perder legibilidad, y se sube rápido aun con datos móviles. */

const LADO_MAXIMO = 2200
const CALIDAD = 0.85

/** Medidas finales manteniendo la proporción, sin agrandar. */
export function medidasReducidas(ancho: number, alto: number, maximo = LADO_MAXIMO): { ancho: number; alto: number } {
  const escala = Math.min(1, maximo / Math.max(ancho, alto))
  return { ancho: Math.round(ancho * escala), alto: Math.round(alto * escala) }
}

export function esImagen(archivo: Blob): boolean {
  return archivo.type.startsWith('image/')
}

/** Devuelve un JPEG reducido; si el navegador no puede leer la imagen, el archivo original. */
export async function comprimirImagen(archivo: File): Promise<File> {
  if (!esImagen(archivo)) return archivo
  try {
    const bitmap = await createImageBitmap(archivo, { imageOrientation: 'from-image' })
    const { ancho, alto } = medidasReducidas(bitmap.width, bitmap.height)
    const lienzo = document.createElement('canvas')
    lienzo.width = ancho
    lienzo.height = alto
    const contexto = lienzo.getContext('2d')
    if (!contexto) return archivo
    contexto.drawImage(bitmap, 0, 0, ancho, alto)
    bitmap.close()
    const blob = await new Promise<Blob | null>((ok) => lienzo.toBlob(ok, 'image/jpeg', CALIDAD))
    if (!blob || blob.size >= archivo.size) return archivo
    const nombre = archivo.name.replace(/\.[^.]+$/, '') || 'foto'
    return new File([blob], `${nombre}.jpg`, { type: 'image/jpeg', lastModified: Date.now() })
  } catch {
    return archivo
  }
}
