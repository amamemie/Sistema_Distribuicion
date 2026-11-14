import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { AlertTriangle } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { Aviso, CABECERA_TABLA, Campo, Casilla, Encabezado, Entrada, Paginador, Selector, Tabla, Tarjeta, Vacio } from '../../components/ui'
import { api, mensajeError } from '../../lib/api'
import { useCategorias, useUbicaciones } from '../../lib/consultas'
import { formatearBs, formatearCantidad } from '../../lib/formato'
import { usePuede } from '../../lib/sesion'
import type { Pagina, StockEnUbicacion, StockProducto } from '../../lib/tipos'

const TAMANO = 50

/** El desglose solo aporta si expresa la cantidad en presentaciones (no solo en unidades). */
function aportaDesglose(desglose: string, unidad: string): boolean {
  return desglose.includes('+') || !desglose.endsWith(` ${unidad}`)
}

function Celda({ s, unidad }: { s: StockEnUbicacion; unidad: string }) {
  const comprometido = Number(s.comprometido) > 0
  return (
    <div className={s.bajo_minimo ? 'text-red-700' : Number(s.fisico) === 0 ? 'text-slate-400' : ''}>
      <div className="flex items-center gap-1 font-medium">
        {s.bajo_minimo && <AlertTriangle size={14} aria-label="Bajo el mínimo" />}
        {formatearCantidad(s.disponible)} <span className="text-xs font-normal text-slate-500">{unidad}</span>
      </div>
      {Number(s.fisico) > 0 && aportaDesglose(s.desglose, unidad) && <div className="text-xs text-slate-500">{s.desglose}</div>}
      {comprometido && <div className="text-xs text-amber-700">{formatearCantidad(s.comprometido)} reservado</div>}
    </div>
  )
}

export function Stock() {
  const puede = usePuede()
  const verCostos = puede('costos.ver')
  const ubicaciones = useUbicaciones()
  const categorias = useCategorias()
  const [ubicacion, setUbicacion] = useState('')
  const [buscar, setBuscar] = useState('')
  const [categoria, setCategoria] = useState('')
  const [soloConStock, setSoloConStock] = useState(true)
  const [pagina, setPagina] = useState(1)
  const filtrar = <T,>(fn: (v: T) => void) => (v: T) => {
    fn(v)
    setPagina(1)
  }

  const stock = useQuery({
    queryKey: ['stock', ubicacion, buscar, categoria, soloConStock, pagina],
    queryFn: () =>
      api<Pagina<StockProducto>>('/inventario/stock', {
        params: { ubicacion_id: ubicacion, buscar, categoria_id: categoria, solo_con_stock: soloConStock, pagina, tamano: TAMANO },
      }),
    placeholderData: keepPreviousData,
  })
  const columnas = stock.data?.items[0]?.ubicaciones ?? []

  return (
    <>
      <Encabezado titulo="Stock" descripcion="Cantidad disponible por ubicación (físico menos lo reservado para pedidos)." />
      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-[1fr_12rem_12rem_auto] lg:items-end">
        <Campo etiqueta="Buscar">
          <Entrada value={buscar} placeholder="Producto o SKU" onChange={(e) => filtrar(setBuscar)(e.target.value)} />
        </Campo>
        <Campo etiqueta="Ubicación">
          <Selector value={ubicacion} onChange={(e) => filtrar(setUbicacion)(e.target.value)}>
            <option value="">Todas</option>
            {ubicaciones.data?.map((u) => (
              <option key={u.id} value={u.id}>
                {u.nombre}
              </option>
            ))}
          </Selector>
        </Campo>
        <Campo etiqueta="Categoría">
          <Selector value={categoria} onChange={(e) => filtrar(setCategoria)(e.target.value)}>
            <option value="">Todas</option>
            {categorias.data?.map((c) => (
              <option key={c.id} value={c.id}>
                {c.nombre}
              </option>
            ))}
          </Selector>
        </Campo>
        <Casilla etiqueta="Solo con stock" checked={soloConStock} onChange={(e) => filtrar(setSoloConStock)(e.target.checked)} />
      </div>
      {stock.isError && <Aviso>{mensajeError(stock.error)}</Aviso>}
      {stock.data?.items.length === 0 && <Vacio>No hay productos para estos filtros.</Vacio>}

      {/* Escritorio: tabla con una columna por ubicación */}
      {!!stock.data?.items.length && (
        <div className="hidden md:block">
          <Tabla>
            <thead className={CABECERA_TABLA}>
              <tr>
                <th>Producto</th>
                {columnas.map((u) => (
                  <th key={u.ubicacion_id}>
                    {u.ubicacion_nombre}
                    <div className="text-[10px] font-normal normal-case">{u.ubicacion_tipo === 'DEPOSITO' ? 'Depósito' : 'Sucursal'}</div>
                  </th>
                ))}
                {columnas.length > 1 && <th>Total</th>}
                {verCostos && <th className="text-right">Valor</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 align-top">
              {stock.data.items.map((p) => (
                <tr key={p.producto_id}>
                  <td>
                    <Link to={`/inventario/kardex/${p.producto_id}`} className="font-medium text-marca-800 hover:underline">
                      {p.nombre}
                    </Link>
                    <div className="text-xs text-slate-500">
                      {p.sku} · {p.categoria}
                    </div>
                  </td>
                  {p.ubicaciones.map((s) => (
                    <td key={s.ubicacion_id}>
                      <Celda s={s} unidad={p.unidad_base} />
                    </td>
                  ))}
                  {columnas.length > 1 && (
                    <td>
                      <div className="font-semibold">
                        {formatearCantidad(p.total_disponible)} <span className="text-xs font-normal text-slate-500">{p.unidad_base}</span>
                      </div>
                      {aportaDesglose(p.total_desglose, p.unidad_base) && <div className="text-xs text-slate-500">{p.total_desglose}</div>}
                    </td>
                  )}
                  {verCostos && <td className="text-right whitespace-nowrap">{formatearBs(p.valor_total)}</td>}
                </tr>
              ))}
            </tbody>
          </Tabla>
        </div>
      )}

      {/* Móvil: una tarjeta por producto */}
      <div className="space-y-3 md:hidden">
        {stock.data?.items.map((p) => (
          <Tarjeta key={p.producto_id} className="p-4">
            <Link to={`/inventario/kardex/${p.producto_id}`} className="font-medium text-marca-800">
              {p.nombre}
            </Link>
            <div className="mb-2 text-xs text-slate-500">
              {p.sku} · Total {formatearCantidad(p.total_disponible)} {p.unidad_base}
            </div>
            <dl className="divide-y divide-slate-100 text-sm">
              {p.ubicaciones.map((s) => (
                <div key={s.ubicacion_id} className="flex items-start justify-between gap-2 py-2">
                  <dt className="text-slate-600">{s.ubicacion_nombre}</dt>
                  <dd className="text-right">
                    <Celda s={s} unidad={p.unidad_base} />
                  </dd>
                </div>
              ))}
            </dl>
          </Tarjeta>
        ))}
      </div>
      <Paginador pagina={pagina} total={stock.data?.total ?? 0} tamano={TAMANO} onCambio={setPagina} />
    </>
  )
}
