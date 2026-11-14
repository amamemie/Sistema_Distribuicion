import { Plus, Trash2 } from 'lucide-react'
import type { ReactNode } from 'react'
import { formatearCantidad } from '../lib/formato'
import { cantidadBase, factorDe, type LineaBase } from '../lib/lineas'
import { SelectorProducto } from './SelectorProducto'
import { Boton, Entrada, Selector } from './ui'

/** Editor de líneas producto + presentación + cantidad, con campos extra por línea. */
export function EditorLineas<T extends LineaBase>({
  lineas,
  onCambio,
  nueva,
  extra,
  etiquetaCantidad = 'Cantidad',
}: {
  lineas: T[]
  onCambio: (lineas: T[]) => void
  nueva: () => T
  extra?: (linea: T, actualizar: (cambios: Partial<T>) => void) => ReactNode
  etiquetaCantidad?: string
}) {
  const actualizar = (clave: string, cambios: Partial<T>) =>
    onCambio(lineas.map((l) => (l.clave === clave ? { ...l, ...cambios } : l)))

  return (
    <div className="space-y-3">
      {lineas.map((linea, i) => {
        const activas = linea.producto?.presentaciones.filter((p) => p.activo) ?? []
        const base = cantidadBase(linea)
        return (
          <div key={linea.clave} className="rounded-lg border border-slate-200 bg-slate-50/60 p-3">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-500 uppercase">Línea {i + 1}</span>
              <Boton
                variante="fantasma"
                className="min-h-8 px-2 text-red-600"
                onClick={() => onCambio(lineas.filter((l) => l.clave !== linea.clave))}
                aria-label={`Quitar línea ${i + 1}`}
              >
                <Trash2 size={16} />
              </Boton>
            </div>
            <div className="grid gap-3 md:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_8rem]">
              <SelectorProducto
                valor={linea.producto}
                onCambio={(producto) => actualizar(linea.clave, { producto, presentacion_id: producto?.presentaciones.find((p) => p.activo)?.id ?? '' } as Partial<T>)}
              />
              <Selector
                aria-label="Presentación"
                value={linea.presentacion_id}
                disabled={!linea.producto}
                onChange={(e) => actualizar(linea.clave, { presentacion_id: e.target.value } as Partial<T>)}
              >
                {activas.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.nombre} ({formatearCantidad(p.factor)} {linea.producto?.unidad_base})
                  </option>
                ))}
                <option value="">{linea.producto ? `${linea.producto.unidad_base} (unidad base)` : 'Presentación'}</option>
              </Selector>
              <Entrada
                aria-label={etiquetaCantidad}
                placeholder={etiquetaCantidad}
                inputMode="decimal"
                value={linea.cantidad}
                onChange={(e) => actualizar(linea.clave, { cantidad: e.target.value.replace(',', '.') } as Partial<T>)}
              />
            </div>
            {linea.producto && base > 0 && factorDe(linea) !== 1 && (
              <p className="mt-1 text-xs text-slate-500">
                = {formatearCantidad(base)} {linea.producto.unidad_base}
              </p>
            )}
            {extra && <div className="mt-3">{extra(linea, (cambios) => actualizar(linea.clave, cambios))}</div>}
          </div>
        )
      })}
      <Boton variante="secundario" onClick={() => onCambio([...lineas, nueva()])}>
        <Plus size={16} /> Agregar producto
      </Boton>
    </div>
  )
}
