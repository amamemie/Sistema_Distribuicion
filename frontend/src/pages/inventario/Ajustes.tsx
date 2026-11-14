import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Plus } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { EditorLineas } from '../../components/EditorLineas'
import { nuevaClave, type LineaBase } from '../../lib/lineas'
import { Aviso, Boton, CABECERA_TABLA, Campo, Encabezado, Entrada, Insignia, Modal, Paginador, Selector, Tabla, Tarjeta, Vacio } from '../../components/ui'
import { api, mensajeError } from '../../lib/api'
import { useUbicaciones } from '../../lib/consultas'
import { formatearBs, formatearCantidad, formatearDia, formatearFecha } from '../../lib/formato'
import { usePuede } from '../../lib/sesion'
import { NOMBRE_MOTIVO, type Ajuste, type EstadoAjuste, type MotivoAjuste, type Pagina } from '../../lib/tipos'

const TAMANO = 50
const TONO_ESTADO = { PENDIENTE: 'ambar', APLICADO: 'verde', RECHAZADO: 'rojo' } as const

export function Ajustes() {
  const puede = usePuede()
  const [estado, setEstado] = useState<EstadoAjuste | ''>('')
  const [pagina, setPagina] = useState(1)
  const [detalle, setDetalle] = useState<Ajuste | null>(null)
  const ajustes = useQuery({
    queryKey: ['ajustes', estado, pagina],
    queryFn: () => api<Pagina<Ajuste>>('/ajustes', { params: { estado, pagina, tamano: TAMANO } }),
    placeholderData: keepPreviousData,
  })

  return (
    <>
      <Encabezado
        titulo="Ajustes de inventario"
        descripcion="Mermas, roturas, vencimientos y correcciones. Los ajustes sensibles requieren aprobación."
        acciones={
          puede('inventario.ajustar') && (
            <Link to="/ajustes/nuevo">
              <Boton>
                <Plus size={16} /> Nuevo ajuste
              </Boton>
            </Link>
          )
        }
      />
      <div className="mb-4 flex flex-wrap gap-2">
        {(['', 'PENDIENTE', 'APLICADO', 'RECHAZADO'] as const).map((e) => (
          <Boton
            key={e}
            variante={estado === e ? 'primario' : 'secundario'}
            className="min-h-8"
            onClick={() => {
              setEstado(e)
              setPagina(1)
            }}
          >
            {e === '' ? 'Todos' : e === 'PENDIENTE' ? 'Pendientes' : e === 'APLICADO' ? 'Aplicados' : 'Rechazados'}
          </Boton>
        ))}
      </div>
      {ajustes.isError && <Aviso>{mensajeError(ajustes.error)}</Aviso>}
      {ajustes.data?.items.length === 0 && <Vacio>No hay ajustes para este filtro.</Vacio>}
      {!!ajustes.data?.items.length && (
        <Tabla>
          <thead className={CABECERA_TABLA}>
            <tr>
              <th>N.º</th>
              <th>Fecha</th>
              <th>Ubicación</th>
              <th className="hidden sm:table-cell">Motivo</th>
              {puede('costos.ver') && <th className="hidden text-right md:table-cell">Valor</th>}
              <th>Estado</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {ajustes.data.items.map((a) => (
              <tr key={a.id}>
                <td>
                  <button className="font-medium text-marca-800 hover:underline" onClick={() => setDetalle(a)}>
                    #{a.numero}
                  </button>
                </td>
                <td className="whitespace-nowrap text-slate-600">{formatearFecha(a.fecha)}</td>
                <td>{a.ubicacion.nombre}</td>
                <td className="hidden sm:table-cell">{NOMBRE_MOTIVO[a.motivo]}</td>
                {puede('costos.ver') && <td className="hidden text-right md:table-cell">{formatearBs(a.valor_total)}</td>}
                <td>
                  <Insignia tono={TONO_ESTADO[a.estado]}>{a.estado.charAt(0) + a.estado.slice(1).toLowerCase()}</Insignia>
                </td>
              </tr>
            ))}
          </tbody>
        </Tabla>
      )}
      <Paginador pagina={pagina} total={ajustes.data?.total ?? 0} tamano={TAMANO} onCambio={setPagina} />
      {detalle && <DetalleAjuste ajuste={detalle} onCerrar={() => setDetalle(null)} />}
    </>
  )
}

function DetalleAjuste({ ajuste: a, onCerrar }: { ajuste: Ajuste; onCerrar: () => void }) {
  const puede = usePuede()
  const queryClient = useQueryClient()
  const [nota, setNota] = useState('')
  const resolver = useMutation({
    mutationFn: (accion: 'aprobar' | 'rechazar') => api(`/ajustes/${a.id}/${accion}`, { metodo: 'POST', cuerpo: { nota: nota || null } }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ajustes'] })
      queryClient.invalidateQueries({ queryKey: ['stock'] })
      onCerrar()
    },
  })
  return (
    <Modal abierto titulo={`Ajuste #${a.numero}`} onCerrar={onCerrar}>
      <div className="space-y-4 text-sm">
        <p>
          <strong>{NOMBRE_MOTIVO[a.motivo]}</strong> en {a.ubicacion.nombre}
          <br />
          <span className="text-slate-600">{a.observacion}</span>
          <br />
          <span className="text-slate-500">
            Solicitado por {a.solicitado_por} · {formatearFecha(a.fecha)}
          </span>
        </p>
        <ul className="divide-y divide-slate-100 rounded border border-slate-200">
          {a.lineas.map((l, i) => (
            <li key={i} className="flex justify-between gap-2 px-3 py-2">
              <span>
                {l.producto_nombre}
                {l.lote_codigo && <span className="block text-xs text-slate-500">Lote {l.lote_codigo} · vence {formatearDia(l.lote_vencimiento)}</span>}
              </span>
              <span className={`text-right whitespace-nowrap ${l.sentido === 'AUMENTO' ? 'text-emerald-700' : 'text-red-700'}`}>
                {l.sentido === 'AUMENTO' ? '+' : '−'}
                {formatearCantidad(l.cantidad)} {l.presentacion_nombre}
                {l.valor !== null && <span className="block text-xs text-slate-500">{formatearBs(l.valor)}</span>}
              </span>
            </li>
          ))}
        </ul>
        {a.valor_total !== null && (
          <p className="text-right">
            Valor total: <strong>{formatearBs(a.valor_total)}</strong>
          </p>
        )}
        {a.resuelto_por && (
          <p className="text-slate-500">
            {a.estado === 'RECHAZADO' ? 'Rechazado' : 'Aplicado'} por {a.resuelto_por} · {formatearFecha(a.resuelto_at)}
            {a.resolucion_nota && ` — ${a.resolucion_nota}`}
          </p>
        )}
        {a.estado === 'PENDIENTE' && puede('inventario.aprobar_ajuste') && (
          <div className="space-y-2 border-t border-slate-200 pt-4">
            {resolver.isError && <Aviso>{mensajeError(resolver.error)}</Aviso>}
            <Campo etiqueta="Nota (opcional)">
              <Entrada value={nota} onChange={(e) => setNota(e.target.value)} />
            </Campo>
            <div className="flex justify-end gap-2">
              <Boton variante="secundario" disabled={resolver.isPending} onClick={() => resolver.mutate('rechazar')}>
                Rechazar
              </Boton>
              <Boton disabled={resolver.isPending} onClick={() => resolver.mutate('aprobar')}>
                Aprobar y aplicar
              </Boton>
            </div>
          </div>
        )}
      </div>
    </Modal>
  )
}

interface LineaAjuste extends LineaBase {
  sentido: 'AUMENTO' | 'DISMINUCION'
  costo_unitario: string
  lote_codigo: string
  lote_vencimiento: string
}

const MOTIVOS_DISMINUCION: MotivoAjuste[] = ['MERMA', 'ROTURA', 'VENCIMIENTO']

export function NuevoAjuste() {
  const navegar = useNavigate()
  const queryClient = useQueryClient()
  const ubicaciones = useUbicaciones()
  const [ubicacion, setUbicacion] = useState('')
  const [motivo, setMotivo] = useState<MotivoAjuste>('MERMA')
  const [observacion, setObservacion] = useState('')
  const soloDisminuir = MOTIVOS_DISMINUCION.includes(motivo)
  const lineaVacia = (): LineaAjuste => ({
    clave: nuevaClave(),
    producto: null,
    presentacion_id: '',
    cantidad: '',
    sentido: 'DISMINUCION',
    costo_unitario: '',
    lote_codigo: '',
    lote_vencimiento: '',
  })
  const [lineas, setLineas] = useState<LineaAjuste[]>([lineaVacia()])

  const guardar = useMutation({
    mutationFn: () =>
      api<Ajuste>('/ajustes', {
        metodo: 'POST',
        cuerpo: {
          ubicacion_id: ubicacion,
          motivo,
          observacion,
          lineas: lineas
            .filter((l) => l.producto)
            .map((l) => {
              const sentido = soloDisminuir ? 'DISMINUCION' : l.sentido
              return {
                producto_id: l.producto!.id,
                presentacion_id: l.presentacion_id || null,
                cantidad: l.cantidad,
                sentido,
                costo_unitario: sentido === 'AUMENTO' && l.costo_unitario ? l.costo_unitario : null,
                lote_codigo: sentido === 'AUMENTO' ? l.lote_codigo || null : null,
                lote_vencimiento: sentido === 'AUMENTO' ? l.lote_vencimiento || null : null,
              }
            }),
        },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ajustes'] })
      queryClient.invalidateQueries({ queryKey: ['stock'] })
      navegar('/ajustes', { replace: true })
    },
  })

  return (
    <>
      <Link to="/ajustes" className="mb-2 inline-flex items-center gap-1 text-sm text-slate-600 hover:text-slate-900">
        <ArrowLeft size={16} /> Ajustes
      </Link>
      <Encabezado titulo="Nuevo ajuste" descripcion="Si no tiene permiso para aprobar ajustes, quedará pendiente hasta que el dueño lo apruebe." />
      <form
        className="space-y-6"
        onSubmit={(e) => {
          e.preventDefault()
          guardar.mutate()
        }}
      >
        <Tarjeta className="grid gap-4 p-4 sm:grid-cols-3">
          <Campo etiqueta="Ubicación">
            <Selector required value={ubicacion} onChange={(e) => setUbicacion(e.target.value)}>
              <option value="">Elegir…</option>
              {ubicaciones.data?.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.nombre}
                </option>
              ))}
            </Selector>
          </Campo>
          <Campo etiqueta="Motivo">
            <Selector value={motivo} onChange={(e) => setMotivo(e.target.value as MotivoAjuste)}>
              {(['MERMA', 'ROTURA', 'VENCIMIENTO', 'CORRECCION', 'OTRO'] as const).map((m) => (
                <option key={m} value={m}>
                  {NOMBRE_MOTIVO[m]}
                </option>
              ))}
            </Selector>
          </Campo>
          <Campo etiqueta="Detalle (obligatorio)">
            <Entrada required minLength={3} value={observacion} onChange={(e) => setObservacion(e.target.value)} placeholder="Qué pasó" />
          </Campo>
        </Tarjeta>
        <EditorLineas
          lineas={lineas}
          onCambio={setLineas}
          nueva={lineaVacia}
          extra={(linea, actualizar) =>
            soloDisminuir ? (
              <p className="text-xs text-slate-500">Se descontará del stock (primero los lotes que vencen antes).</p>
            ) : (
              <div className="grid gap-3 sm:grid-cols-4">
                <Campo etiqueta="Tipo">
                  <Selector value={linea.sentido} onChange={(e) => actualizar({ sentido: e.target.value as LineaAjuste['sentido'] })}>
                    <option value="DISMINUCION">Disminuir</option>
                    <option value="AUMENTO">Aumentar</option>
                  </Selector>
                </Campo>
                {linea.sentido === 'AUMENTO' && (
                  <>
                    <Campo etiqueta="Costo unit. (Bs)" ayuda="Vacío = costo promedio actual">
                      <Entrada inputMode="decimal" value={linea.costo_unitario} onChange={(e) => actualizar({ costo_unitario: e.target.value.replace(',', '.') })} />
                    </Campo>
                    {linea.producto?.controla_vencimiento && (
                      <>
                        <Campo etiqueta="Lote">
                          <Entrada value={linea.lote_codigo} onChange={(e) => actualizar({ lote_codigo: e.target.value })} />
                        </Campo>
                        <Campo etiqueta="Vence">
                          <Entrada type="date" required value={linea.lote_vencimiento} onChange={(e) => actualizar({ lote_vencimiento: e.target.value })} />
                        </Campo>
                      </>
                    )}
                  </>
                )}
              </div>
            )
          }
        />
        {guardar.isError && <Aviso>{mensajeError(guardar.error)}</Aviso>}
        <div className="flex justify-end">
          <Boton type="submit" disabled={guardar.isPending || !lineas.some((l) => l.producto)}>
            Registrar ajuste
          </Boton>
        </div>
      </form>
    </>
  )
}
