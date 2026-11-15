import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Camera, PackageCheck, RotateCcw, Truck, X } from 'lucide-react'
import { useRef, useState } from 'react'
import { Link, useParams } from 'react-router'
import { FirmaCanvas } from '../../components/pedidos/FirmaCanvas'
import { VisorDocumentos } from '../../components/pedidos/VisorDocumentos'
import { Aviso, Boton, CABECERA_TABLA, Campo, Entrada, Modal, Tabla, Tarjeta } from '../../components/ui'
import { api, mensajeError, urlArchivo } from '../../lib/api'
import { formatearBs, formatearCantidad, formatearCosto, formatearDia, formatearFecha, formatearPorcentaje } from '../../lib/formato'
import { comprimirImagen } from '../../lib/imagenes'
import { usePuede, useYo } from '../../lib/sesion'
import { NOMBRE_ESTADO_PEDIDO, type EstadoPedido, type LoteEnStock, type PedidoDetalle, type PedidoLinea } from '../../lib/tipos'
import { InsigniaEstado } from './Pedidos'
import { RevisionPedido } from './RevisionPedido'

const NOMBRE_EVENTO: Record<string, string> = {
  CREADO: 'Creó el pedido',
  DOCUMENTO_AGREGADO: 'Adjuntó documentos',
  DOCUMENTO_QUITADO: 'Quitó un documento',
  CONFIRMADO: 'Confirmó (reservó stock)',
  ALISTADO: 'Alistó (descontó stock)',
  ENTREGADO: 'Entregó',
  ANULADO: 'Anuló',
  DEVOLUCION: 'Registró una devolución',
  LEIDO: 'Lectura automática de la OC',
  LECTURA_SOLICITADA: 'Pidió volver a leer la OC',
}

export function DetallePedido() {
  const { pedidoId = '' } = useParams()
  const puede = usePuede()
  const { data: yo } = useYo()
  const [accion, setAccion] = useState<'alistar' | 'entregar' | 'anular' | 'devolver' | null>(null)
  const pedido = useQuery({
    queryKey: ['pedido', pedidoId],
    queryFn: () => api<PedidoDetalle>(`/pedidos/${pedidoId}`),
    // Mientras la OC se lee en segundo plano, se consulta cada 2 segundos.
    refetchInterval: (q) => (['PENDIENTE', 'PROCESANDO'].includes(q.state.data?.lectura?.estado ?? '') ? 2000 : false),
  })

  if (pedido.isError) return <Aviso>{mensajeError(pedido.error)}</Aviso>
  if (!pedido.data) return <p className="text-sm text-slate-500">Cargando…</p>
  const p = pedido.data
  const puedeAnular =
    ['BORRADOR', 'CONFIRMADO', 'ALISTADO'].includes(p.estado) &&
    (puede('pedidos.anular') || (p.estado === 'BORRADOR' && p.responsable_id === yo?.id))
  const cerrar = () => setAccion(null)

  return (
    <>
      <Link to="/pedidos" className="mb-2 inline-flex items-center gap-1 text-sm text-slate-600 hover:text-slate-900">
        <ArrowLeft size={16} /> Pedidos
      </Link>
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="flex flex-wrap items-center gap-2 text-2xl font-semibold tracking-tight">
            Pedido #{p.numero} <InsigniaEstado estado={p.estado} />
          </h1>
          <p className="mt-1 text-sm text-slate-600">
            {p.numero_oc ? `OC ${p.numero_oc}` : 'OC sin número'}
            {p.cadena && ` · ${p.cadena.nombre}`}
            {p.sucursal_cliente && ` · ${p.sucursal_cliente.nombre}`} · despacha {p.ubicacion.nombre}
          </p>
        </div>
        {p.estado !== 'BORRADOR' && (
          <div className="flex flex-wrap gap-2">
            {p.estado === 'CONFIRMADO' && puede('pedidos.alistar') && (
              <Boton onClick={() => setAccion('alistar')}>
                <PackageCheck size={16} /> Alistar
              </Boton>
            )}
            {p.estado === 'ALISTADO' && puede('pedidos.entregar') && (
              <Boton onClick={() => setAccion('entregar')}>
                <Truck size={16} /> Marcar entregado
              </Boton>
            )}
            {p.estado === 'ENTREGADO' && puede('pedidos.anular') && (
              <Boton variante="secundario" onClick={() => setAccion('devolver')}>
                <RotateCcw size={16} /> Registrar devolución
              </Boton>
            )}
            {puedeAnular && (
              <Boton variante="secundario" className="text-red-600" onClick={() => setAccion('anular')}>
                <X size={16} /> Anular
              </Boton>
            )}
          </div>
        )}
      </div>

      {p.estado === 'BORRADOR' ? (
        <RevisionPedido key={`${p.id}-${p.lectura?.id ?? ''}-${p.lectura?.estado ?? ''}`} pedido={p} puedeAnular={puedeAnular} onAnular={() => setAccion('anular')} />
      ) : (
        <ResumenPedido pedido={p} />
      )}

      {accion === 'alistar' && <Alistar pedido={p} onCerrar={cerrar} />}
      {accion === 'entregar' && <Entregar pedido={p} onCerrar={cerrar} />}
      {accion === 'anular' && <Anular pedido={p} onCerrar={cerrar} />}
      {accion === 'devolver' && <Devolver pedido={p} onCerrar={cerrar} />}
    </>
  )
}

function ResumenPedido({ pedido: p }: { pedido: PedidoDetalle }) {
  const conCostos = p.costo !== null
  const alistado = p.detalle_lineas.some((l) => l.cantidad_alistada !== null)
  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
      <div className="space-y-5">
        {p.estado === 'ANULADO' && (
          <Aviso>
            Anulado desde {p.anulado_desde ? NOMBRE_ESTADO_PEDIDO[p.anulado_desde].toLowerCase() : '—'}: {p.anulacion_motivo}
          </Aviso>
        )}
        <Tarjeta className="grid grid-cols-2 gap-4 p-4 text-sm sm:grid-cols-4">
          <Dato titulo="Fecha OC" valor={formatearDia(p.fecha_oc)} />
          <Dato titulo="Entrega" valor={formatearDia(p.fecha_entrega)} />
          <Dato titulo="Total OC" valor={formatearBs(p.total_oc ?? p.total_calculado)} />
          <Dato titulo="Responsable" valor={p.responsable_nombre} />
          {p.ingreso !== null && <Dato titulo="Ingreso" valor={formatearBs(p.ingreso)} />}
          {conCostos && <Dato titulo="Costo" valor={formatearBs(p.costo)} />}
          {p.ganancia !== null && (
            <Dato
              titulo="Ganancia"
              valor={`${formatearBs(p.ganancia)} (${formatearPorcentaje(p.margen)})`}
              tono={Number(p.ganancia) < 0 ? 'text-red-700' : 'text-emerald-700'}
            />
          )}
        </Tarjeta>

        <Tabla>
          <thead className={CABECERA_TABLA}>
            <tr>
              <th>Producto</th>
              <th className="text-right">OC</th>
              <th className="text-right">Confirmado</th>
              {alistado && <th className="text-right">Alistado</th>}
              <th className="text-right">Precio</th>
              {alistado && <th className="text-right">Ingreso</th>}
              {conCostos && alistado && <th className="text-right">Costo unit.</th>}
              {conCostos && alistado && <th className="text-right">Ganancia</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {p.detalle_lineas.map((l) => (
              <tr key={l.id}>
                <td className="min-w-52">
                  <span className="font-medium">{l.producto?.nombre ?? l.descripcion_cliente}</span>
                  <span className="block text-xs text-slate-500">
                    {l.codigo_cliente && `${l.codigo_cliente} · `}
                    {l.descripcion_cliente}
                  </span>
                  {l.lotes.some((t) => t.vencimiento) && (
                    <span className="block text-xs text-slate-500">
                      Lotes: {l.lotes.map((t) => `${t.codigo ?? 's/c'} (${formatearCantidad(t.cantidad)}, vence ${formatearDia(t.vencimiento)})`).join(', ')}
                    </span>
                  )}
                  {Number(l.cantidad_merma) > 0 && <span className="block text-xs text-amber-700">Merma: {formatearCantidad(l.cantidad_merma)}</span>}
                  {Number(l.cantidad_devuelta) > 0 && <span className="block text-xs text-amber-700">Devuelto: {formatearCantidad(l.cantidad_devuelta)}</span>}
                </td>
                <td className="text-right">{formatearCantidad(l.cantidad_oc)}</td>
                <td className="text-right">{formatearCantidad(l.cantidad_confirmada)}</td>
                {alistado && <td className="text-right">{formatearCantidad(l.cantidad_alistada)}</td>}
                <td className="text-right whitespace-nowrap">{formatearCosto(l.precio_oc)}</td>
                {alistado && <td className="text-right whitespace-nowrap">{formatearBs(l.ingreso)}</td>}
                {conCostos && alistado && <td className="text-right whitespace-nowrap">{formatearCosto(l.costo_unitario)}</td>}
                {conCostos && alistado && (
                  <td className={`text-right whitespace-nowrap ${Number(l.ganancia) < 0 ? 'text-red-700' : ''}`}>
                    {formatearBs(l.ganancia)}
                    <span className="block text-xs text-slate-500">{formatearPorcentaje(l.margen)}</span>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </Tabla>

        {p.mermas.length > 0 && (
          <p className="text-sm text-slate-600">
            Merma registrada al alistar:{' '}
            {p.mermas.map((m) => (
              <Link key={m.id} to="/ajustes" className="text-marca-800 underline">
                ajuste #{m.numero} ({m.estado.toLowerCase()})
              </Link>
            ))}
          </p>
        )}
        {p.devoluciones.length > 0 && (
          <Tarjeta className="p-4 text-sm">
            <h2 className="mb-2 font-semibold">Devoluciones</h2>
            <ul className="space-y-2">
              {p.devoluciones.map((d) => (
                <li key={d.id}>
                  #{d.numero} · {formatearFecha(d.fecha)} · {d.usuario_nombre}: {d.motivo}
                  <span className="block text-xs text-slate-500">
                    {d.lineas.map((x) => `${x.descripcion}: ${formatearCantidad(x.cantidad)}`).join(' · ')}
                  </span>
                </li>
              ))}
            </ul>
          </Tarjeta>
        )}
        {p.estado === 'ENTREGADO' && (
          <Tarjeta className="space-y-2 p-4 text-sm">
            <h2 className="font-semibold">Constancia de entrega</h2>
            <p>
              {formatearFecha(p.entregado_at)}
              {p.receptor_nombre && ` · Recibió: ${p.receptor_nombre}`}
            </p>
            {p.entrega_observacion && <p className="text-slate-600">{p.entrega_observacion}</p>}
            <div className="flex flex-wrap gap-3">
              {p.constancia_foto_id && (
                <a href={urlArchivo(p.id, p.constancia_foto_id)} target="_blank" rel="noreferrer">
                  <img src={urlArchivo(p.id, p.constancia_foto_id)} alt="Foto de la entrega" className="h-32 rounded border border-slate-200 object-cover" />
                </a>
              )}
              {p.constancia_firma_id && (
                <img src={urlArchivo(p.id, p.constancia_firma_id)} alt="Firma de recepción" className="h-32 rounded border border-slate-200 bg-white" />
              )}
            </div>
          </Tarjeta>
        )}
      </div>

      <div className="space-y-5">
        <VisorDocumentos pedidoId={p.id} documentos={p.detalle_documentos} />
        <Tarjeta className="p-4 text-sm">
          <h2 className="mb-2 font-semibold">Historia</h2>
          <ol className="space-y-2">
            {p.eventos.map((e, i) => (
              <li key={i} className="border-l-2 border-slate-200 pl-3">
                <span className="font-medium">{NOMBRE_EVENTO[e.tipo] ?? e.tipo}</span>
                <span className="block text-xs text-slate-500">
                  {e.usuario_nombre} · {formatearFecha(e.fecha)}
                </span>
              </li>
            ))}
          </ol>
        </Tarjeta>
      </div>
    </div>
  )
}

function Dato({ titulo, valor, tono }: { titulo: string; valor: string; tono?: string }) {
  return (
    <div>
      <p className="text-xs text-slate-500">{titulo}</p>
      <p className={`font-medium ${tono ?? ''}`}>{valor}</p>
    </div>
  )
}

function useActualizarPedido(pedidoId: string, onCerrar: () => void) {
  const queryClient = useQueryClient()
  return (nuevo: PedidoDetalle) => {
    queryClient.setQueryData(['pedido', pedidoId], nuevo)
    void queryClient.invalidateQueries({ queryKey: ['pedidos'] })
    void queryClient.invalidateQueries({ queryKey: ['stock'] })
    void queryClient.invalidateQueries({ queryKey: ['ajustes'] })
    onCerrar()
  }
}

// ---------------------------------------------------------------- alistar

interface FilaAlistado {
  alistada: string
  merma: string
  elegirLotes: boolean
  lotes: Record<string, string>
}

/** Reparto FEFO sugerido: primero el lote que vence antes. */
function repartoFefo(lotes: LoteEnStock[], cantidad: number): Record<string, string> {
  const resultado: Record<string, string> = {}
  let pendiente = cantidad
  for (const l of lotes.filter((x) => !x.vencido)) {
    const tomar = Math.min(pendiente, Number(l.cantidad))
    resultado[l.lote_id] = tomar > 0 ? String(tomar) : ''
    pendiente -= tomar
  }
  return resultado
}

function Alistar({ pedido: p, onCerrar }: { pedido: PedidoDetalle; onCerrar: () => void }) {
  const lineas = p.detalle_lineas.filter((l) => Number(l.cantidad_confirmada) > 0)
  const [filas, setFilas] = useState<Record<string, FilaAlistado>>(() =>
    Object.fromEntries(lineas.map((l) => [l.id, { alistada: String(Number(l.cantidad_confirmada)), merma: '', elegirLotes: false, lotes: {} }])),
  )
  const [observacion, setObservacion] = useState('')
  const actualizar = useActualizarPedido(p.id, onCerrar)
  const alistar = useMutation({
    mutationFn: () =>
      api<PedidoDetalle>(`/pedidos/${p.id}/alistar`, {
        metodo: 'POST',
        cuerpo: {
          observacion_merma: observacion.trim() || null,
          lineas: lineas.map((l) => {
            const f = filas[l.id]
            return {
              linea_id: l.id,
              cantidad_alistada: f.alistada || '0',
              cantidad_merma: f.merma || '0',
              lotes: f.elegirLotes
                ? Object.entries(f.lotes)
                    .filter(([, c]) => Number(c) > 0)
                    .map(([lote_id, cantidad]) => ({ lote_id, cantidad }))
                : [],
            }
          }),
        },
      }),
    onSuccess: actualizar,
  })
  const cambiar = (id: string, cambios: Partial<FilaAlistado>) => setFilas((f) => ({ ...f, [id]: { ...f[id], ...cambios } }))
  const hayMerma = Object.values(filas).some((f) => Number(f.merma) > 0)

  return (
    <Modal abierto titulo={`Alistar pedido #${p.numero}`} onCerrar={onCerrar}>
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault()
          alistar.mutate()
        }}
      >
        <p className="text-sm text-slate-600">
          Al alistar se descuenta el stock de {p.ubicacion.nombre}. Puede salir menos de lo confirmado; lo que esté en mal estado regístrelo como merma.
        </p>
        {lineas.map((l) => (
          <FilaAlistar key={l.id} linea={l} ubicacionId={p.ubicacion.id} fila={filas[l.id]} onCambio={(c) => cambiar(l.id, c)} />
        ))}
        {hayMerma && (
          <Campo etiqueta="Detalle de la merma (opcional)">
            <Entrada value={observacion} onChange={(e) => setObservacion(e.target.value)} placeholder="Ej.: cajas aplastadas" />
          </Campo>
        )}
        {alistar.isError && <Aviso>{mensajeError(alistar.error)}</Aviso>}
        <div className="flex justify-end gap-2">
          <Boton variante="secundario" onClick={onCerrar}>
            Cancelar
          </Boton>
          <Boton type="submit" disabled={alistar.isPending}>
            {alistar.isPending ? 'Alistando…' : 'Confirmar alistado'}
          </Boton>
        </div>
      </form>
    </Modal>
  )
}

function FilaAlistar({
  linea: l,
  ubicacionId,
  fila,
  onCambio,
}: {
  linea: PedidoLinea
  ubicacionId: string
  fila: FilaAlistado
  onCambio: (c: Partial<FilaAlistado>) => void
}) {
  const vence = !!l.producto?.controla_vencimiento
  const lotes = useQuery({
    queryKey: ['lotes', l.producto?.id, ubicacionId],
    queryFn: () => api<LoteEnStock[]>('/inventario/lotes', { params: { producto_id: l.producto?.id, ubicacion_id: ubicacionId } }),
    enabled: vence && !!l.producto,
  })
  const sumaLotes = Object.values(fila.lotes).reduce((s, c) => s + (Number(c) || 0), 0)
  return (
    <div className="rounded-lg border border-slate-200 p-3">
      <p className="text-sm font-medium">{l.producto?.nombre ?? l.descripcion_cliente}</p>
      <p className="text-xs text-slate-500">
        Confirmado: {formatearCantidad(l.cantidad_confirmada)} {l.producto?.unidad_base}
      </p>
      <div className="mt-2 grid grid-cols-2 gap-3">
        <Campo etiqueta="Alistado">
          <Entrada inputMode="decimal" required value={fila.alistada} onChange={(e) => onCambio({ alistada: e.target.value.replace(',', '.') })} />
        </Campo>
        <Campo etiqueta="En mal estado (merma)">
          <Entrada inputMode="decimal" placeholder="0" value={fila.merma} onChange={(e) => onCambio({ merma: e.target.value.replace(',', '.') })} />
        </Campo>
      </div>
      {vence && (
        <div className="mt-2 text-sm">
          <label className="inline-flex items-center gap-2 text-xs text-slate-700">
            <input
              type="checkbox"
              className="accent-marca-700"
              checked={fila.elegirLotes}
              onChange={(e) => onCambio({ elegirLotes: e.target.checked, lotes: repartoFefo(lotes.data ?? [], Number(fila.alistada) || 0) })}
            />
            Elegir lotes (si no, sale primero el que vence antes)
          </label>
          {fila.elegirLotes && (
            <ul className="mt-2 space-y-1">
              {(lotes.data ?? []).map((lote) => (
                <li key={lote.lote_id} className="flex items-center gap-2">
                  <span className={`flex-1 text-xs ${lote.vencido ? 'text-red-600 line-through' : 'text-slate-600'}`}>
                    {lote.codigo ?? 's/c'} · vence {formatearDia(lote.vencimiento)} · hay {formatearCantidad(lote.cantidad)}
                  </span>
                  <Entrada
                    className="w-24"
                    inputMode="decimal"
                    disabled={lote.vencido}
                    value={fila.lotes[lote.lote_id] ?? ''}
                    onChange={(e) => onCambio({ lotes: { ...fila.lotes, [lote.lote_id]: e.target.value.replace(',', '.') } })}
                  />
                </li>
              ))}
              {sumaLotes !== (Number(fila.alistada) || 0) && (
                <li className="text-xs text-red-700">
                  Los lotes suman {formatearCantidad(sumaLotes)}; deben sumar {formatearCantidad(fila.alistada)}.
                </li>
              )}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------- entregar

function Entregar({ pedido: p, onCerrar }: { pedido: PedidoDetalle; onCerrar: () => void }) {
  const [receptor, setReceptor] = useState('')
  const [observacion, setObservacion] = useState('')
  const [foto, setFoto] = useState<File | null>(null)
  const [firma, setFirma] = useState<Blob | null>(null)
  const camara = useRef<HTMLInputElement>(null)
  const actualizar = useActualizarPedido(p.id, onCerrar)
  const entregar = useMutation({
    mutationFn: () => {
      const datos = new FormData()
      if (receptor.trim()) datos.append('receptor_nombre', receptor.trim())
      if (observacion.trim()) datos.append('observacion', observacion.trim())
      if (foto) datos.append('foto', foto, foto.name)
      if (firma) datos.append('firma', firma, 'firma.png')
      return api<PedidoDetalle>(`/pedidos/${p.id}/entregar`, { metodo: 'POST', cuerpo: datos })
    },
    onSuccess: actualizar,
  })
  return (
    <Modal abierto titulo={`Entregar pedido #${p.numero}`} onCerrar={onCerrar}>
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault()
          entregar.mutate()
        }}
      >
        <p className="text-sm text-slate-600">La constancia es opcional: nombre de quien recibe, una foto y/o su firma.</p>
        <Campo etiqueta="Recibido por">
          <Entrada value={receptor} onChange={(e) => setReceptor(e.target.value)} placeholder="Nombre de quien recibe" />
        </Campo>
        <div className="space-y-1">
          <span className="text-sm font-medium text-slate-700">Foto de la entrega</span>
          <input
            ref={camara}
            type="file"
            accept="image/*"
            capture="environment"
            hidden
            onChange={async (e) => {
              const archivo = e.target.files?.[0]
              if (archivo) setFoto(await comprimirImagen(archivo))
              e.target.value = ''
            }}
          />
          <div className="flex items-center gap-2">
            <Boton variante="secundario" onClick={() => camara.current?.click()}>
              <Camera size={16} /> {foto ? 'Cambiar foto' : 'Tomar foto'}
            </Boton>
            {foto && <span className="truncate text-xs text-slate-600">{foto.name}</span>}
          </div>
        </div>
        <div className="space-y-1">
          <span className="text-sm font-medium text-slate-700">Firma de recepción</span>
          <FirmaCanvas onCambio={setFirma} />
        </div>
        <Campo etiqueta="Observación">
          <Entrada value={observacion} onChange={(e) => setObservacion(e.target.value)} />
        </Campo>
        {entregar.isError && <Aviso>{mensajeError(entregar.error)}</Aviso>}
        <div className="flex justify-end gap-2">
          <Boton variante="secundario" onClick={onCerrar}>
            Cancelar
          </Boton>
          <Boton type="submit" disabled={entregar.isPending}>
            {entregar.isPending ? 'Guardando…' : 'Confirmar entrega'}
          </Boton>
        </div>
      </form>
    </Modal>
  )
}

// ---------------------------------------------------------------- anular y devolver

const EFECTO_ANULAR: Partial<Record<EstadoPedido, string>> = {
  BORRADOR: 'El pedido se descarta; no afecta el stock.',
  CONFIRMADO: 'Se libera el stock reservado.',
  ALISTADO: 'Lo alistado vuelve al stock de la sucursal (mismos lotes y costo).',
}

function Anular({ pedido: p, onCerrar }: { pedido: PedidoDetalle; onCerrar: () => void }) {
  const [motivo, setMotivo] = useState('')
  const actualizar = useActualizarPedido(p.id, onCerrar)
  const anular = useMutation({
    mutationFn: () => api<PedidoDetalle>(`/pedidos/${p.id}/anular`, { metodo: 'POST', cuerpo: { motivo } }),
    onSuccess: actualizar,
  })
  return (
    <Modal abierto titulo={`Anular pedido #${p.numero}`} onCerrar={onCerrar}>
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault()
          anular.mutate()
        }}
      >
        <p className="text-sm text-slate-600">{EFECTO_ANULAR[p.estado]}</p>
        <Campo etiqueta="Motivo">
          <Entrada required minLength={5} value={motivo} onChange={(e) => setMotivo(e.target.value)} autoFocus />
        </Campo>
        {anular.isError && <Aviso>{mensajeError(anular.error)}</Aviso>}
        <div className="flex justify-end gap-2">
          <Boton variante="secundario" onClick={onCerrar}>
            Volver
          </Boton>
          <Boton type="submit" variante="peligro" disabled={anular.isPending}>
            Anular pedido
          </Boton>
        </div>
      </form>
    </Modal>
  )
}

function Devolver({ pedido: p, onCerrar }: { pedido: PedidoDetalle; onCerrar: () => void }) {
  const lineas = p.detalle_lineas.filter((l) => Number(l.cantidad_alistada ?? 0) - Number(l.cantidad_devuelta) > 0)
  const [cantidades, setCantidades] = useState<Record<string, string>>({})
  const [motivo, setMotivo] = useState('')
  const actualizar = useActualizarPedido(p.id, onCerrar)
  const devolver = useMutation({
    mutationFn: () =>
      api<PedidoDetalle>(`/pedidos/${p.id}/devoluciones`, {
        metodo: 'POST',
        cuerpo: {
          motivo,
          lineas: Object.entries(cantidades)
            .filter(([, c]) => Number(c) > 0)
            .map(([linea_id, cantidad]) => ({ linea_id, cantidad })),
        },
      }),
    onSuccess: actualizar,
  })
  return (
    <Modal abierto titulo={`Devolución del pedido #${p.numero}`} onCerrar={onCerrar}>
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault()
          devolver.mutate()
        }}
      >
        <p className="text-sm text-slate-600">
          Lo devuelto vuelve al stock de {p.ubicacion.nombre} y se descuenta del ingreso del pedido. Si llegó dañado, regístrelo luego como merma.
        </p>
        {lineas.map((l) => (
          <div key={l.id} className="flex items-center gap-3">
            <span className="flex-1 text-sm">
              {l.producto?.nombre ?? l.descripcion_cliente}
              <span className="block text-xs text-slate-500">
                Entregado: {formatearCantidad(Number(l.cantidad_alistada) - Number(l.cantidad_devuelta))}
              </span>
            </span>
            <Entrada
              className="w-24"
              inputMode="decimal"
              placeholder="0"
              value={cantidades[l.id] ?? ''}
              onChange={(e) => setCantidades((c) => ({ ...c, [l.id]: e.target.value.replace(',', '.') }))}
            />
          </div>
        ))}
        <Campo etiqueta="Motivo">
          <Entrada required minLength={5} value={motivo} onChange={(e) => setMotivo(e.target.value)} />
        </Campo>
        {devolver.isError && <Aviso>{mensajeError(devolver.error)}</Aviso>}
        <div className="flex justify-end gap-2">
          <Boton variante="secundario" onClick={onCerrar}>
            Cancelar
          </Boton>
          <Boton type="submit" disabled={devolver.isPending || !Object.values(cantidades).some((c) => Number(c) > 0)}>
            Registrar devolución
          </Boton>
        </div>
      </form>
    </Modal>
  )
}
