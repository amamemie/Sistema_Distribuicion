import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router'
import { EditorLineas } from '../../components/EditorLineas'
import { cantidadBase, nuevaClave, type LineaBase } from '../../lib/lineas'
import {
  Aviso,
  Boton,
  CABECERA_TABLA,
  Campo,
  Encabezado,
  Entrada,
  Insignia,
  Modal,
  Paginador,
  Selector,
  Tabla,
  Tarjeta,
  Vacio,
} from '../../components/ui'
import { api, mensajeError } from '../../lib/api'
import { useProveedores, useUbicaciones } from '../../lib/consultas'
import { formatearBs, formatearCantidad, formatearCosto, formatearDia, hoyLaPaz } from '../../lib/formato'
import type { CompraDetalle, CompraResumen, Pagina, Producto } from '../../lib/tipos'

const TAMANO = 50

export function Compras() {
  const proveedores = useProveedores()
  const [proveedor, setProveedor] = useState('')
  const [pagina, setPagina] = useState(1)
  const compras = useQuery({
    queryKey: ['compras', proveedor, pagina],
    queryFn: () => api<Pagina<CompraResumen>>('/compras', { params: { proveedor_id: proveedor, pagina, tamano: TAMANO } }),
    placeholderData: keepPreviousData,
  })

  return (
    <>
      <Encabezado
        titulo="Compras"
        descripcion="Ingresos de mercadería comprada a proveedores."
        acciones={
          <Link to="/compras/nueva">
            <Boton>
              <Plus size={16} /> Registrar compra
            </Boton>
          </Link>
        }
      />
      <div className="mb-4 max-w-xs">
        <Campo etiqueta="Proveedor">
          <Selector
            value={proveedor}
            onChange={(e) => {
              setProveedor(e.target.value)
              setPagina(1)
            }}
          >
            <option value="">Todos</option>
            {proveedores.data?.map((p) => (
              <option key={p.id} value={p.id}>
                {p.nombre}
              </option>
            ))}
          </Selector>
        </Campo>
      </div>
      {compras.isError && <Aviso>{mensajeError(compras.error)}</Aviso>}
      {compras.data?.items.length === 0 && <Vacio>No hay compras registradas.</Vacio>}
      {!!compras.data?.items.length && (
        <Tabla>
          <thead className={CABECERA_TABLA}>
            <tr>
              <th>N.º</th>
              <th>Fecha</th>
              <th>Proveedor</th>
              <th className="hidden md:table-cell">Destino</th>
              <th className="text-right">Total</th>
              <th>Estado</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {compras.data.items.map((c) => (
              <tr key={c.id}>
                <td>
                  <Link to={`/compras/${c.id}`} className="font-medium text-marca-800 hover:underline">
                    #{c.numero}
                  </Link>
                  {c.numero_documento && <div className="text-xs text-slate-500">{c.numero_documento}</div>}
                </td>
                <td className="whitespace-nowrap">{formatearDia(c.fecha)}</td>
                <td>{c.proveedor.nombre}</td>
                <td className="hidden md:table-cell">{c.ubicacion.nombre}</td>
                <td className="text-right whitespace-nowrap">{formatearBs(c.total)}</td>
                <td>{c.estado === 'ANULADA' ? <Insignia tono="rojo">Anulada</Insignia> : <Insignia tono="verde">Registrada</Insignia>}</td>
              </tr>
            ))}
          </tbody>
        </Tabla>
      )}
      <Paginador pagina={pagina} total={compras.data?.total ?? 0} tamano={TAMANO} onCambio={setPagina} />
    </>
  )
}

interface LineaCompra extends LineaBase {
  precio: string
  lote_codigo: string
  lote_vencimiento: string
}

const lineaVacia = (): LineaCompra => ({
  clave: nuevaClave(),
  producto: null,
  presentacion_id: '',
  cantidad: '',
  precio: '',
  lote_codigo: '',
  lote_vencimiento: '',
})

/** Datos para precargar la compra (desde una sugerencia de reposición). */
interface PrecargaCompra {
  proveedor_id?: string
  ubicacion_id?: string
  lineas?: { producto: Producto; presentacion_id: string; cantidad: string; precio: string }[]
}

export function NuevaCompra() {
  const precarga = (useLocation().state as PrecargaCompra | null) ?? {}
  const navegar = useNavigate()
  const queryClient = useQueryClient()
  const proveedores = useProveedores()
  const ubicaciones = useUbicaciones()
  const [cabecera, setCabecera] = useState({
    proveedor_id: precarga.proveedor_id ?? '',
    ubicacion_id: precarga.ubicacion_id ?? '',
    fecha: hoyLaPaz(),
    numero_documento: '',
    observaciones: '',
  })
  const [lineas, setLineas] = useState<LineaCompra[]>(() =>
    precarga.lineas?.length ? precarga.lineas.map((l) => ({ ...lineaVacia(), ...l })) : [lineaVacia()],
  )
  const [costos, setCostos] = useState<{ concepto: string; monto: string }[]>([])

  const subtotal = lineas.reduce((s, l) => s + (Number(l.cantidad) || 0) * (Number(l.precio) || 0), 0)
  const adicionales = costos.reduce((s, c) => s + (Number(c.monto) || 0), 0)

  const registrar = useMutation({
    mutationFn: () =>
      api<CompraDetalle>('/compras', {
        metodo: 'POST',
        cuerpo: {
          ...cabecera,
          numero_documento: cabecera.numero_documento || null,
          observaciones: cabecera.observaciones || null,
          lineas: lineas
            .filter((l) => l.producto)
            .map((l) => ({
              producto_id: l.producto!.id,
              presentacion_id: l.presentacion_id || null,
              cantidad: l.cantidad,
              precio_presentacion: l.precio || '0',
              lote_codigo: l.lote_codigo || null,
              lote_vencimiento: l.lote_vencimiento || null,
            })),
          costos: costos.filter((c) => c.concepto && Number(c.monto) > 0),
        },
      }),
    onSuccess: (compra) => {
      queryClient.invalidateQueries({ queryKey: ['compras'] })
      queryClient.invalidateQueries({ queryKey: ['stock'] })
      navegar(`/compras/${compra.id}`, { replace: true })
    },
  })

  return (
    <>
      <Link to="/compras" className="mb-2 inline-flex items-center gap-1 text-sm text-slate-600 hover:text-slate-900">
        <ArrowLeft size={16} /> Compras
      </Link>
      <Encabezado titulo="Registrar compra" descripcion="Al guardar, la mercadería ingresa al inventario de la ubicación de destino." />
      <form
        className="space-y-6"
        onSubmit={(e) => {
          e.preventDefault()
          registrar.mutate()
        }}
      >
        <Tarjeta className="grid gap-4 p-4 sm:grid-cols-2 lg:grid-cols-4">
          <Campo etiqueta="Proveedor">
            <Selector required value={cabecera.proveedor_id} onChange={(e) => setCabecera((c) => ({ ...c, proveedor_id: e.target.value }))}>
              <option value="">Elegir…</option>
              {proveedores.data?.filter((p) => p.activo).map((p) => (
                <option key={p.id} value={p.id}>
                  {p.nombre}
                </option>
              ))}
            </Selector>
          </Campo>
          <Campo etiqueta="Ingresa a">
            <Selector required value={cabecera.ubicacion_id} onChange={(e) => setCabecera((c) => ({ ...c, ubicacion_id: e.target.value }))}>
              <option value="">Elegir…</option>
              {ubicaciones.data?.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.nombre}
                </option>
              ))}
            </Selector>
          </Campo>
          <Campo etiqueta="Fecha">
            <Entrada type="date" required max={hoyLaPaz()} value={cabecera.fecha} onChange={(e) => setCabecera((c) => ({ ...c, fecha: e.target.value }))} />
          </Campo>
          <Campo etiqueta="N.º de factura o nota">
            <Entrada value={cabecera.numero_documento} onChange={(e) => setCabecera((c) => ({ ...c, numero_documento: e.target.value }))} />
          </Campo>
        </Tarjeta>

        <section>
          <h2 className="mb-2 font-semibold">Productos</h2>
          <EditorLineas
            lineas={lineas}
            onCambio={setLineas}
            nueva={lineaVacia}
            extra={(linea, actualizar) => {
              const base = cantidadBase(linea)
              const costoUnit = base > 0 ? ((Number(linea.cantidad) || 0) * (Number(linea.precio) || 0)) / base : 0
              return (
                <div className="grid gap-3 sm:grid-cols-3">
                  <Campo etiqueta={`Precio por ${linea.producto?.presentaciones.find((p) => p.id === linea.presentacion_id)?.nombre ?? linea.producto?.unidad_base ?? 'unidad'} (Bs)`}>
                    <Entrada inputMode="decimal" value={linea.precio} onChange={(e) => actualizar({ precio: e.target.value.replace(',', '.') })} />
                  </Campo>
                  {linea.producto?.controla_vencimiento ? (
                    <>
                      <Campo etiqueta="Lote">
                        <Entrada required value={linea.lote_codigo} onChange={(e) => actualizar({ lote_codigo: e.target.value })} />
                      </Campo>
                      <Campo etiqueta="Vence">
                        <Entrada type="date" required value={linea.lote_vencimiento} onChange={(e) => actualizar({ lote_vencimiento: e.target.value })} />
                      </Campo>
                    </>
                  ) : (
                    <div className="self-end text-sm text-slate-600 sm:col-span-2">
                      {costoUnit > 0 && linea.producto && (
                        <>
                          Costo: <strong>{formatearCosto(costoUnit)}</strong> por {linea.producto.unidad_base} (antes de costos adicionales)
                        </>
                      )}
                    </div>
                  )}
                </div>
              )
            }}
          />
        </section>

        <section>
          <h2 className="mb-1 font-semibold">Costos adicionales</h2>
          <p className="mb-2 text-sm text-slate-500">Flete, carga, descarga… Se reparten entre los productos según su importe.</p>
          <div className="space-y-2">
            {costos.map((c, i) => (
              <div key={i} className="flex gap-2">
                <Entrada placeholder="Concepto" value={c.concepto} onChange={(e) => setCostos((l) => l.map((x, j) => (j === i ? { ...x, concepto: e.target.value } : x)))} />
                <Entrada
                  className="w-32"
                  placeholder="Bs"
                  inputMode="decimal"
                  value={c.monto}
                  onChange={(e) => setCostos((l) => l.map((x, j) => (j === i ? { ...x, monto: e.target.value.replace(',', '.') } : x)))}
                />
                <Boton variante="fantasma" className="px-2 text-red-600" aria-label="Quitar costo" onClick={() => setCostos((l) => l.filter((_, j) => j !== i))}>
                  <Trash2 size={16} />
                </Boton>
              </div>
            ))}
            <Boton variante="secundario" onClick={() => setCostos((l) => [...l, { concepto: 'Flete', monto: '' }])}>
              <Plus size={16} /> Agregar costo
            </Boton>
          </div>
        </section>

        <Campo etiqueta="Observaciones">
          <Entrada value={cabecera.observaciones} onChange={(e) => setCabecera((c) => ({ ...c, observaciones: e.target.value }))} />
        </Campo>

        <Tarjeta className="flex flex-wrap items-center justify-between gap-3 p-4">
          <div className="text-sm">
            Productos {formatearBs(subtotal)} + adicionales {formatearBs(adicionales)} ={' '}
            <strong className="text-base">{formatearBs(subtotal + adicionales)}</strong>
          </div>
          <Boton type="submit" disabled={registrar.isPending || !lineas.some((l) => l.producto)}>
            {registrar.isPending ? 'Registrando…' : 'Registrar compra'}
          </Boton>
        </Tarjeta>
        {registrar.isError && <Aviso>{mensajeError(registrar.error)}</Aviso>}
      </form>
    </>
  )
}

export function DetalleCompra() {
  const { compraId = '' } = useParams()
  const queryClient = useQueryClient()
  const [anulando, setAnulando] = useState(false)
  const [motivo, setMotivo] = useState('')
  const compra = useQuery({ queryKey: ['compra', compraId], queryFn: () => api<CompraDetalle>(`/compras/${compraId}`) })
  const anular = useMutation({
    mutationFn: () => api<CompraDetalle>(`/compras/${compraId}/anular`, { metodo: 'POST', cuerpo: { motivo } }),
    onSuccess: (c) => {
      queryClient.setQueryData(['compra', compraId], c)
      queryClient.invalidateQueries({ queryKey: ['compras'] })
      queryClient.invalidateQueries({ queryKey: ['stock'] })
      setAnulando(false)
    },
  })
  const c = compra.data

  return (
    <>
      <Link to="/compras" className="mb-2 inline-flex items-center gap-1 text-sm text-slate-600 hover:text-slate-900">
        <ArrowLeft size={16} /> Compras
      </Link>
      {compra.isError && <Aviso>{mensajeError(compra.error)}</Aviso>}
      {c && (
        <>
          <Encabezado
            titulo={`Compra #${c.numero}`}
            descripcion={`${c.proveedor.nombre} → ${c.ubicacion.nombre} · ${formatearDia(c.fecha)}${c.numero_documento ? ` · ${c.numero_documento}` : ''}`}
            acciones={
              c.estado === 'REGISTRADA' ? (
                <Boton variante="secundario" onClick={() => setAnulando(true)}>
                  Anular compra
                </Boton>
              ) : (
                <Insignia tono="rojo">Anulada</Insignia>
              )
            }
          />
          {c.estado === 'ANULADA' && <Aviso>Anulada: {c.anulacion_motivo}</Aviso>}
          <Tabla>
            <thead className={CABECERA_TABLA}>
              <tr>
                <th>Producto</th>
                <th className="text-right">Cantidad</th>
                <th className="hidden text-right sm:table-cell">Precio</th>
                <th className="text-right">Subtotal</th>
                <th className="hidden text-right md:table-cell">Ingresan</th>
                <th className="text-right">Costo unit.</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {c.lineas.map((l, i) => (
                <tr key={i}>
                  <td>
                    <div className="font-medium">{l.producto_nombre}</div>
                    <div className="text-xs text-slate-500">
                      {l.producto_sku}
                      {l.lote_codigo && ` · lote ${l.lote_codigo} · vence ${formatearDia(l.lote_vencimiento)}`}
                    </div>
                  </td>
                  <td className="text-right whitespace-nowrap">
                    {formatearCantidad(l.cantidad)} {l.presentacion_nombre}
                  </td>
                  <td className="hidden text-right sm:table-cell">{formatearBs(l.precio_presentacion)}</td>
                  <td className="text-right">
                    {formatearBs(l.subtotal)}
                    {Number(l.prorrateo) > 0 && <div className="text-xs text-slate-500">+ {formatearBs(l.prorrateo)}</div>}
                  </td>
                  <td className="hidden text-right md:table-cell">
                    {formatearCantidad(l.cantidad_base)} {l.unidad_base}
                  </td>
                  <td className="text-right font-medium whitespace-nowrap">
                    {formatearCosto(l.costo_unitario_base)}
                    <div className="text-xs font-normal text-slate-500">por {l.unidad_base}</div>
                  </td>
                </tr>
              ))}
            </tbody>
          </Tabla>
          <Tarjeta className="mt-4 space-y-1 p-4 text-sm sm:ml-auto sm:max-w-sm">
            <div className="flex justify-between">
              <span>Productos</span>
              <span>{formatearBs(c.subtotal)}</span>
            </div>
            {c.costos.map((x, i) => (
              <div key={i} className="flex justify-between text-slate-600">
                <span>{x.concepto}</span>
                <span>{formatearBs(x.monto)}</span>
              </div>
            ))}
            <div className="flex justify-between border-t border-slate-200 pt-1 text-base font-semibold">
              <span>Total</span>
              <span>{formatearBs(c.total)}</span>
            </div>
            <p className="pt-2 text-xs text-slate-500">Registrada por {c.usuario_nombre}</p>
          </Tarjeta>
        </>
      )}
      <Modal abierto={anulando} titulo="Anular compra" onCerrar={() => setAnulando(false)}>
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault()
            anular.mutate()
          }}
        >
          <p className="text-sm text-slate-600">
            Se retirará del inventario todo lo que ingresó con esta compra. Solo es posible si esa mercadería sigue en la ubicación.
          </p>
          {anular.isError && <Aviso>{mensajeError(anular.error)}</Aviso>}
          <Campo etiqueta="Motivo">
            <Entrada required minLength={5} value={motivo} onChange={(e) => setMotivo(e.target.value)} />
          </Campo>
          <div className="flex justify-end gap-2">
            <Boton variante="secundario" onClick={() => setAnulando(false)}>
              Cancelar
            </Boton>
            <Boton type="submit" variante="peligro" disabled={anular.isPending}>
              Anular
            </Boton>
          </div>
        </form>
      </Modal>
    </>
  )
}
