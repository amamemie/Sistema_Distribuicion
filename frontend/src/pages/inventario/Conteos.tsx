import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Plus } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { SelectorProducto } from '../../components/SelectorProducto'
import { Aviso, Boton, CABECERA_TABLA, Campo, Casilla, Encabezado, Entrada, Insignia, Modal, Paginador, Selector, Tabla, Vacio } from '../../components/ui'
import { api, mensajeError } from '../../lib/api'
import { useCategorias, useUbicaciones } from '../../lib/consultas'
import { formatearBs, formatearCantidad, formatearFecha } from '../../lib/formato'
import { usePuede } from '../../lib/sesion'
import type { Conteo, Pagina } from '../../lib/tipos'

const TAMANO = 50
const TONO = { ABIERTO: 'azul', APROBADO: 'verde', ANULADO: 'rojo' } as const

export function Conteos() {
  const puede = usePuede()
  const [pagina, setPagina] = useState(1)
  const [creando, setCreando] = useState(false)
  const conteos = useQuery({
    queryKey: ['conteos', pagina],
    queryFn: () => api<Pagina<Conteo>>('/conteos', { params: { pagina, tamano: TAMANO } }),
    placeholderData: keepPreviousData,
  })

  return (
    <>
      <Encabezado
        titulo="Conteos físicos"
        descripcion="Se cuenta lo que hay en la ubicación; al aprobar, las diferencias se ajustan automáticamente."
        acciones={
          puede('inventario.ajustar') && (
            <Boton onClick={() => setCreando(true)}>
              <Plus size={16} /> Nuevo conteo
            </Boton>
          )
        }
      />
      {conteos.isError && <Aviso>{mensajeError(conteos.error)}</Aviso>}
      {conteos.data?.items.length === 0 && <Vacio>No hay conteos registrados.</Vacio>}
      {!!conteos.data?.items.length && (
        <Tabla>
          <thead className={CABECERA_TABLA}>
            <tr>
              <th>N.º</th>
              <th>Fecha</th>
              <th>Ubicación</th>
              <th className="hidden sm:table-cell">Responsable</th>
              <th>Estado</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {conteos.data.items.map((c) => (
              <tr key={c.id}>
                <td>
                  <Link to={`/conteos/${c.id}`} className="font-medium text-marca-800 hover:underline">
                    #{c.numero}
                  </Link>
                </td>
                <td className="whitespace-nowrap text-slate-600">{formatearFecha(c.fecha)}</td>
                <td>{c.ubicacion.nombre}</td>
                <td className="hidden sm:table-cell">{c.usuario_nombre}</td>
                <td>
                  <Insignia tono={TONO[c.estado]}>{c.estado.charAt(0) + c.estado.slice(1).toLowerCase()}</Insignia>
                </td>
              </tr>
            ))}
          </tbody>
        </Tabla>
      )}
      <Paginador pagina={pagina} total={conteos.data?.total ?? 0} tamano={TAMANO} onCambio={setPagina} />
      {creando && <CrearConteo onCerrar={() => setCreando(false)} />}
    </>
  )
}

function CrearConteo({ onCerrar }: { onCerrar: () => void }) {
  const navegar = useNavigate()
  const ubicaciones = useUbicaciones()
  const categorias = useCategorias()
  const [datos, setDatos] = useState({ ubicacion_id: '', categoria_id: '', cargar_productos_con_stock: true, observaciones: '' })
  const crear = useMutation({
    mutationFn: () =>
      api<Conteo>('/conteos', {
        metodo: 'POST',
        cuerpo: { ...datos, categoria_id: datos.categoria_id || null, observaciones: datos.observaciones || null },
      }),
    onSuccess: (c) => navegar(`/conteos/${c.id}`),
  })
  return (
    <Modal abierto titulo="Nuevo conteo físico" onCerrar={onCerrar}>
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault()
          crear.mutate()
        }}
      >
        {crear.isError && <Aviso>{mensajeError(crear.error)}</Aviso>}
        <Campo etiqueta="Ubicación">
          <Selector required value={datos.ubicacion_id} onChange={(e) => setDatos((d) => ({ ...d, ubicacion_id: e.target.value }))}>
            <option value="">Elegir…</option>
            {ubicaciones.data?.map((u) => (
              <option key={u.id} value={u.id}>
                {u.nombre}
              </option>
            ))}
          </Selector>
        </Campo>
        <Casilla
          etiqueta="Cargar los productos que tienen stock en la ubicación"
          checked={datos.cargar_productos_con_stock}
          onChange={(e) => setDatos((d) => ({ ...d, cargar_productos_con_stock: e.target.checked }))}
        />
        {datos.cargar_productos_con_stock && (
          <Campo etiqueta="Solo la categoría (opcional)">
            <Selector value={datos.categoria_id} onChange={(e) => setDatos((d) => ({ ...d, categoria_id: e.target.value }))}>
              <option value="">Todas</option>
              {categorias.data?.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.nombre}
                </option>
              ))}
            </Selector>
          </Campo>
        )}
        <Campo etiqueta="Observaciones">
          <Entrada value={datos.observaciones} onChange={(e) => setDatos((d) => ({ ...d, observaciones: e.target.value }))} />
        </Campo>
        <div className="flex justify-end gap-2">
          <Boton variante="secundario" onClick={onCerrar}>
            Cancelar
          </Boton>
          <Boton type="submit" disabled={crear.isPending}>
            Crear conteo
          </Boton>
        </div>
      </form>
    </Modal>
  )
}

export function DetalleConteo() {
  const { conteoId = '' } = useParams()
  const puede = usePuede()
  const queryClient = useQueryClient()
  const clave = ['conteo', conteoId]
  const conteo = useQuery({ queryKey: clave, queryFn: () => api<Conteo>(`/conteos/${conteoId}`) })
  const [editados, setEditados] = useState<Record<string, { cantidad: string; vencimiento: string }>>({})

  const alRecibir = (c: Conteo) => {
    queryClient.setQueryData(clave, c)
    queryClient.invalidateQueries({ queryKey: ['conteos'] })
  }
  const guardar = useMutation({
    mutationFn: (lineas: { producto_id: string; cantidad_contada: string | null; vencimiento: string | null }[]) =>
      api<Conteo>(`/conteos/${conteoId}/lineas`, { metodo: 'PUT', cuerpo: lineas }),
    onSuccess: (c) => {
      alRecibir(c)
      setEditados({})
    },
  })
  const accion = useMutation({
    mutationFn: (que: 'aprobar' | 'anular') => api<Conteo>(`/conteos/${conteoId}/${que}`, { metodo: 'POST' }),
    onSuccess: (c) => {
      alRecibir(c)
      queryClient.invalidateQueries({ queryKey: ['stock'] })
      queryClient.invalidateQueries({ queryKey: ['ajustes'] })
    },
  })

  const c = conteo.data
  const abierto = c?.estado === 'ABIERTO'
  const pendientes = Object.keys(editados).length > 0
  const guardarEditados = () =>
    guardar.mutate(
      Object.entries(editados).map(([producto_id, v]) => ({
        producto_id,
        cantidad_contada: v.cantidad === '' ? null : v.cantidad,
        vencimiento: v.vencimiento || null,
      })),
    )

  return (
    <>
      <Link to="/conteos" className="mb-2 inline-flex items-center gap-1 text-sm text-slate-600 hover:text-slate-900">
        <ArrowLeft size={16} /> Conteos
      </Link>
      {conteo.isError && <Aviso>{mensajeError(conteo.error)}</Aviso>}
      {c && (
        <>
          <Encabezado
            titulo={`Conteo #${c.numero} · ${c.ubicacion.nombre}`}
            descripcion={`${formatearFecha(c.fecha)} · ${c.usuario_nombre}`}
            acciones={<Insignia tono={TONO[c.estado]}>{c.estado.charAt(0) + c.estado.slice(1).toLowerCase()}</Insignia>}
          />
          {(guardar.isError || accion.isError) && <Aviso>{mensajeError(guardar.error ?? accion.error)}</Aviso>}
          {c.ajuste_id && (
            <p className="mb-4 text-sm text-slate-600">
              Las diferencias se registraron como un ajuste aplicado. <Link to="/ajustes" className="text-marca-700 underline">Ver ajustes</Link>
            </p>
          )}
          {abierto && (
            <div className="mb-4 max-w-md">
              <span className="mb-1 block text-sm font-medium text-slate-700">Agregar producto al conteo</span>
              <SelectorProducto
                valor={null}
                onCambio={(p) => p && guardar.mutate([{ producto_id: p.id, cantidad_contada: null, vencimiento: null }])}
              />
            </div>
          )}
          {c.lineas.length === 0 ? (
            <Vacio>Agregue los productos a contar.</Vacio>
          ) : (
            <Tabla>
              <thead className={CABECERA_TABLA}>
                <tr>
                  <th>Producto</th>
                  <th className="text-right">Sistema</th>
                  <th className="w-36">Contado</th>
                  <th className="text-right">Diferencia</th>
                  {puede('costos.ver') && <th className="hidden text-right sm:table-cell">Valor</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {c.lineas.map((l) => {
                  const edit = editados[l.producto_id]
                  const contado = edit?.cantidad ?? l.cantidad_contada ?? ''
                  const diferencia = contado === '' ? null : Number(contado) - Number(l.cantidad_sistema)
                  return (
                    <tr key={l.producto_id}>
                      <td>
                        <div className="font-medium">{l.producto_nombre}</div>
                        <div className="text-xs text-slate-500">
                          {l.producto_sku} · {l.unidad_base}
                        </div>
                      </td>
                      <td className="text-right">{formatearCantidad(l.cantidad_sistema)}</td>
                      <td>
                        {abierto ? (
                          <div className="space-y-1">
                            <Entrada
                              inputMode="decimal"
                              aria-label={`Contado de ${l.producto_nombre}`}
                              value={contado}
                              onChange={(e) =>
                                setEditados((x) => ({
                                  ...x,
                                  [l.producto_id]: { cantidad: e.target.value.replace(',', '.'), vencimiento: x[l.producto_id]?.vencimiento ?? l.vencimiento ?? '' },
                                }))
                              }
                            />
                            {l.controla_vencimiento && diferencia !== null && diferencia > 0 && (
                              <Entrada
                                type="date"
                                aria-label="Vencimiento del sobrante"
                                value={edit?.vencimiento ?? l.vencimiento ?? ''}
                                onChange={(e) =>
                                  setEditados((x) => ({ ...x, [l.producto_id]: { cantidad: contado, vencimiento: e.target.value } }))
                                }
                              />
                            )}
                          </div>
                        ) : (
                          formatearCantidad(l.cantidad_contada)
                        )}
                      </td>
                      <td className={`text-right font-medium ${diferencia === null || diferencia === 0 ? '' : diferencia > 0 ? 'text-emerald-700' : 'text-red-700'}`}>
                        {diferencia === null ? '—' : `${diferencia > 0 ? '+' : ''}${formatearCantidad(diferencia)}`}
                      </td>
                      {puede('costos.ver') && <td className="hidden text-right sm:table-cell">{formatearBs(l.valor_diferencia)}</td>}
                    </tr>
                  )
                })}
              </tbody>
            </Tabla>
          )}
          {abierto && (
            <div className="sticky bottom-0 mt-4 flex flex-wrap justify-end gap-2 border-t border-slate-200 bg-slate-50/95 py-3">
              {puede('inventario.ajustar') && (
                <Boton variante="secundario" disabled={accion.isPending} onClick={() => window.confirm('¿Anular este conteo?') && accion.mutate('anular')}>
                  Anular
                </Boton>
              )}
              <Boton variante="secundario" disabled={!pendientes || guardar.isPending} onClick={guardarEditados}>
                Guardar cantidades
              </Boton>
              {puede('inventario.aprobar_ajuste') && (
                <Boton
                  disabled={pendientes || accion.isPending}
                  title={pendientes ? 'Guarde las cantidades antes de aprobar' : undefined}
                  onClick={() => window.confirm('Se ajustará el stock con las diferencias. ¿Aprobar?') && accion.mutate('aprobar')}
                >
                  Aprobar y ajustar
                </Boton>
              )}
            </div>
          )}
        </>
      )}
    </>
  )
}
