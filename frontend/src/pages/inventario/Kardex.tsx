import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { ArrowLeft } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { Aviso, CABECERA_TABLA, Campo, Encabezado, Entrada, Insignia, Paginador, Selector, Tabla, Vacio } from '../../components/ui'
import { api, mensajeError } from '../../lib/api'
import { useUbicaciones } from '../../lib/consultas'
import { formatearCantidad, formatearCosto, formatearDia, formatearFecha } from '../../lib/formato'
import { usePuede } from '../../lib/sesion'
import { NOMBRE_MOVIMIENTO, type LoteEnStock, type MovimientoKardex, type Pagina, type ProductoDetalle } from '../../lib/tipos'

const TAMANO = 100

export function Kardex() {
  const { productoId = '' } = useParams()
  const verCostos = usePuede()('costos.ver')
  const ubicaciones = useUbicaciones(false)
  const [ubicacion, setUbicacion] = useState('')
  const [desde, setDesde] = useState('')
  const [hasta, setHasta] = useState('')
  const [pagina, setPagina] = useState(1)

  const producto = useQuery({ queryKey: ['producto', productoId], queryFn: () => api<ProductoDetalle>(`/productos/${productoId}`) })
  const lotes = useQuery({
    queryKey: ['lotes', productoId, ubicacion],
    queryFn: () => api<LoteEnStock[]>('/inventario/lotes', { params: { producto_id: productoId, ubicacion_id: ubicacion } }),
  })
  const kardex = useQuery({
    queryKey: ['kardex', productoId, ubicacion, desde, hasta, pagina],
    queryFn: () =>
      api<Pagina<MovimientoKardex>>('/inventario/kardex', {
        params: { producto_id: productoId, ubicacion_id: ubicacion, desde, hasta, pagina, tamano: TAMANO },
      }),
    placeholderData: keepPreviousData,
  })
  const unidad = producto.data?.unidad_base ?? ''
  const mostrarLotes = producto.data?.controla_vencimiento || (lotes.data?.length ?? 0) > 1

  return (
    <>
      <Link to="/inventario" className="mb-2 inline-flex items-center gap-1 text-sm text-slate-600 hover:text-slate-900">
        <ArrowLeft size={16} /> Stock
      </Link>
      <Encabezado
        titulo={producto.data ? `Kardex · ${producto.data.nombre}` : 'Kardex'}
        descripcion={producto.data ? `${producto.data.sku} · cantidades en ${unidad}` : undefined}
      />
      {(producto.isError || kardex.isError) && <Aviso>{mensajeError(producto.error ?? kardex.error)}</Aviso>}
      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        <Campo etiqueta="Ubicación">
          <Selector
            value={ubicacion}
            onChange={(e) => {
              setUbicacion(e.target.value)
              setPagina(1)
            }}
          >
            <option value="">Todas</option>
            {ubicaciones.data?.map((u) => (
              <option key={u.id} value={u.id}>
                {u.nombre}
              </option>
            ))}
          </Selector>
        </Campo>
        <Campo etiqueta="Desde">
          <Entrada type="date" value={desde} onChange={(e) => setDesde(e.target.value)} />
        </Campo>
        <Campo etiqueta="Hasta">
          <Entrada type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} />
        </Campo>
      </div>

      {mostrarLotes && !!lotes.data?.length && (
        <section className="mb-6">
          <h2 className="mb-2 font-semibold">Lotes en stock</h2>
          <Tabla>
            <thead className={CABECERA_TABLA}>
              <tr>
                <th>Lote</th>
                <th>Ubicación</th>
                <th>Vence</th>
                <th className="text-right">Cantidad</th>
                {verCostos && <th className="text-right">Costo unit.</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {lotes.data.map((l) => (
                <tr key={`${l.lote_id}-${l.ubicacion_id}`}>
                  <td>{l.codigo ?? <span className="text-slate-400">sin código</span>}</td>
                  <td>{l.ubicacion_nombre}</td>
                  <td>
                    {formatearDia(l.vencimiento)}{' '}
                    {l.vencido ? (
                      <Insignia tono="rojo">Vencido</Insignia>
                    ) : l.dias_para_vencer !== null && l.dias_para_vencer <= 7 ? (
                      <Insignia tono="ambar">{l.dias_para_vencer} días</Insignia>
                    ) : null}
                  </td>
                  <td className="text-right">{formatearCantidad(l.cantidad)}</td>
                  {verCostos && <td className="text-right">{formatearCosto(l.costo_unitario)}</td>}
                </tr>
              ))}
            </tbody>
          </Tabla>
        </section>
      )}

      <h2 className="mb-2 font-semibold">Movimientos</h2>
      {kardex.data?.items.length === 0 && <Vacio>Sin movimientos para estos filtros.</Vacio>}
      {!!kardex.data?.items.length && (
        <Tabla>
          <thead className={CABECERA_TABLA}>
            <tr>
              <th>Fecha</th>
              <th>Movimiento</th>
              <th className="hidden md:table-cell">Ubicación</th>
              <th className="text-right">Entrada</th>
              <th className="text-right">Salida</th>
              <th className="text-right">Saldo</th>
              {verCostos && <th className="hidden text-right lg:table-cell">Costo unit.</th>}
              {verCostos && <th className="hidden text-right lg:table-cell">CPP</th>}
              <th className="hidden lg:table-cell">Usuario</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {kardex.data.items.map((m) => (
              <tr key={m.id}>
                <td className="whitespace-nowrap text-slate-600">{formatearFecha(m.fecha)}</td>
                <td>
                  <div>{NOMBRE_MOVIMIENTO[m.tipo]}</div>
                  <div className="text-xs text-slate-500">
                    {m.documento}
                    {m.lote_codigo && ` · lote ${m.lote_codigo}`}
                  </div>
                  {m.motivo && <div className="text-xs text-slate-500 italic">{m.motivo}</div>}
                </td>
                <td className="hidden md:table-cell">{m.ubicacion.nombre}</td>
                <td className="text-right text-emerald-700">{m.entrada ? formatearCantidad(m.entrada) : ''}</td>
                <td className="text-right text-red-700">{m.salida ? formatearCantidad(m.salida) : ''}</td>
                <td className="text-right font-medium">{formatearCantidad(m.saldo)}</td>
                {verCostos && <td className="hidden text-right whitespace-nowrap lg:table-cell">{formatearCosto(m.costo_unitario)}</td>}
                {verCostos && <td className="hidden text-right whitespace-nowrap lg:table-cell">{formatearCosto(m.cpp_despues)}</td>}
                <td className="hidden text-slate-600 lg:table-cell">{m.usuario_nombre}</td>
              </tr>
            ))}
          </tbody>
        </Tabla>
      )}
      <p className="mt-2 text-xs text-slate-500">El saldo de cada fila es el de su ubicación después del movimiento.</p>
      <Paginador pagina={pagina} total={kardex.data?.total ?? 0} tamano={TAMANO} onCambio={setPagina} />
    </>
  )
}
