import { useQuery } from '@tanstack/react-query'
import { Search, X } from 'lucide-react'
import { useEffect, useId, useState } from 'react'
import { api } from '../lib/api'
import type { Pagina, Producto } from '../lib/tipos'
import { Entrada } from './ui'

/** Buscador de productos activos por nombre, SKU o código de barras. */
export function SelectorProducto({
  valor,
  onCambio,
  autoFocus,
}: {
  valor: Producto | null
  onCambio: (producto: Producto | null) => void
  autoFocus?: boolean
}) {
  const [texto, setTexto] = useState('')
  const [busqueda, setBusqueda] = useState('')
  const [abierto, setAbierto] = useState(false)
  const idLista = useId()

  useEffect(() => {
    const t = setTimeout(() => setBusqueda(texto.trim()), 250)
    return () => clearTimeout(t)
  }, [texto])

  const resultados = useQuery({
    queryKey: ['productos', 'buscar', busqueda],
    queryFn: () =>
      api<Pagina<Producto>>('/productos', { params: { buscar: busqueda, activo: true, tamano: 8 } }),
    enabled: abierto && busqueda.length > 0,
    staleTime: 30_000,
  })

  if (valor) {
    return (
      <div className="flex min-h-10 items-center justify-between gap-2 rounded-md border border-slate-300 bg-slate-50 px-3 text-sm">
        <span className="truncate">
          <span className="font-medium">{valor.nombre}</span>
          <span className="ml-2 text-xs text-slate-500">{valor.sku}</span>
        </span>
        <button type="button" onClick={() => onCambio(null)} aria-label="Cambiar producto" className="text-slate-500 hover:text-slate-800">
          <X size={16} />
        </button>
      </div>
    )
  }

  const elegir = (p: Producto) => {
    onCambio(p)
    setTexto('')
    setAbierto(false)
  }

  return (
    <div className="relative">
      <Search size={16} className="pointer-events-none absolute top-3 left-3 text-slate-400" />
      <Entrada
        value={texto}
        autoFocus={autoFocus}
        placeholder="Buscar producto (nombre, SKU o código)"
        className="pl-9"
        role="combobox"
        aria-expanded={abierto}
        aria-controls={idLista}
        onFocus={() => setAbierto(true)}
        onBlur={() => setTimeout(() => setAbierto(false), 150)}
        onChange={(e) => {
          setTexto(e.target.value)
          setAbierto(true)
        }}
        onKeyDown={(e) => {
          const primero = resultados.data?.items[0]
          if (e.key === 'Enter' && primero) {
            e.preventDefault()
            elegir(primero)
          }
        }}
      />
      {abierto && busqueda && (
        <ul id={idLista} role="listbox" className="absolute z-20 mt-1 max-h-64 w-full overflow-y-auto rounded-md border border-slate-200 bg-white shadow-lg">
          {resultados.isFetching && !resultados.data && <li className="px-3 py-2 text-sm text-slate-500">Buscando…</li>}
          {resultados.data?.items.length === 0 && <li className="px-3 py-2 text-sm text-slate-500">Sin resultados</li>}
          {resultados.data?.items.map((p) => (
            <li key={p.id} role="option" aria-selected={false}>
              <button
                type="button"
                className="block w-full px-3 py-2 text-left text-sm hover:bg-marca-50"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => elegir(p)}
              >
                <span className="font-medium">{p.nombre}</span>
                <span className="ml-2 text-xs text-slate-500">
                  {p.sku} · {p.unidad_base}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
