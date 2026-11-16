import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Banknote, FileText, Paperclip, Plus, Settings2 } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { Link, useSearchParams } from 'react-router'
import {
  Aviso,
  Boton,
  CABECERA_TABLA,
  Campo,
  Casilla,
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
import { useCadenas, useUbicaciones } from '../../lib/consultas'
import { formatearBs, formatearDia, hoyLaPaz } from '../../lib/formato'
import { usePuede } from '../../lib/sesion'
import type {
  CategoriaGasto,
  CobroDetalle,
  CobroResumen,
  CompraPorPagar,
  CuentaPorCobrar,
  EstadoCuenta,
  Gasto,
  ImpuestoMes,
  Pagina,
  PaginaGastos,
  ParametrosFinanzas,
  PorCobrar,
  ResumenCadena,
} from '../../lib/tipos'
import { nombreMes, primerDiaMes, ultimoDiaMes, urlComprobante } from './utiles'

const PESTANAS = [
  { clave: 'por-cobrar', titulo: 'Por cobrar' },
  { clave: 'cobros', titulo: 'Cobros' },
  { clave: 'gastos', titulo: 'Gastos' },
  { clave: 'por-pagar', titulo: 'Por pagar' },
  { clave: 'impuestos', titulo: 'Impuestos' },
] as const

type Pestana = (typeof PESTANAS)[number]['clave']

/** Finanzas: lo que deben los supermercados, cobros, gastos, pagos e impuestos (Fase 5). */
export function Finanzas() {
  const [params, setParams] = useSearchParams()
  const actual: Pestana = PESTANAS.find((p) => p.clave === params.get('pestana'))?.clave ?? 'por-cobrar'
  const puede = usePuede()

  return (
    <>
      <Encabezado
        titulo="Finanzas"
        descripcion="Lo que deben los supermercados, las transferencias recibidas, los gastos y los impuestos."
        acciones={
          puede('finanzas.cobros') && (
            <Link to="/finanzas/cobros/nuevo">
              <Boton>
                <Banknote size={16} /> Registrar cobro
              </Boton>
            </Link>
          )
        }
      />
      <nav aria-label="Secciones de finanzas" className="-mx-4 mb-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
        <ul className="flex min-w-max gap-1 border-b border-slate-200">
          {PESTANAS.map((p) => (
            <li key={p.clave}>
              <button
                type="button"
                onClick={() => setParams({ pestana: p.clave }, { replace: true })}
                aria-current={p.clave === actual ? 'page' : undefined}
                className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium whitespace-nowrap ${
                  p.clave === actual ? 'border-marca-600 text-marca-700' : 'border-transparent text-slate-600 hover:text-slate-900'
                }`}
              >
                {p.titulo}
              </button>
            </li>
          ))}
        </ul>
      </nav>
      {actual === 'por-cobrar' && <SeccionPorCobrar />}
      {actual === 'cobros' && <SeccionCobros />}
      {actual === 'gastos' && <SeccionGastos />}
      {actual === 'por-pagar' && <SeccionPorPagar />}
      {actual === 'impuestos' && <SeccionImpuestos />}
    </>
  )
}

function Cifra({ titulo, valor, tono, children }: { titulo: string; valor: string; tono?: 'rojo'; children?: ReactNode }) {
  return (
    <Tarjeta className="p-3">
      <p className="text-xs text-slate-500">{titulo}</p>
      <p className={`mt-1 text-lg font-semibold tabular-nums ${tono === 'rojo' ? 'text-red-700' : 'text-slate-900'}`}>{valor}</p>
      {children}
    </Tarjeta>
  )
}

const ESTADO_CUENTA: Record<EstadoCuenta, { texto: string; tono: 'gris' | 'verde' | 'rojo' | 'azul' | 'ambar' }> = {
  PENDIENTE: { texto: 'Por cobrar', tono: 'ambar' },
  PARCIAL: { texto: 'Pago parcial', tono: 'azul' },
  SALDADA: { texto: 'Cobrado', tono: 'verde' },
  A_FAVOR: { texto: 'Saldo a favor', tono: 'gris' },
}

export function InsigniaCuenta({ cuenta }: { cuenta: CuentaPorCobrar }) {
  if (cuenta.dias_vencida > 0) return <Insignia tono="rojo">Vencido hace {cuenta.dias_vencida} d</Insignia>
  const e = ESTADO_CUENTA[cuenta.estado]
  return <Insignia tono={e.tono}>{e.texto}</Insignia>
}

// ================================================================ por cobrar

/** Lo que debe cada empresa (cadena), en total (T-31). El detalle por pedido es secundario. */
function SeccionPorCobrar() {
  const puede = usePuede()
  const [abierta, setAbierta] = useState<string | null>(null)
  const [rebajando, setRebajando] = useState<ResumenCadena | null>(null)
  const datos = useQuery({
    queryKey: ['por-cobrar', '', false],
    queryFn: () => api<PorCobrar>('/finanzas/por-cobrar'),
    placeholderData: keepPreviousData,
  })
  const d = datos.data
  const cadenas = d?.cadenas.filter((c) => Number(c.pendiente) > 0 || Number(c.a_favor) > 0) ?? []

  return (
    <div className="space-y-5">
      {datos.isError && <Aviso>{mensajeError(datos.error)}</Aviso>}
      {d && (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
          <Cifra titulo="Total por cobrar" valor={formatearBs(d.total_pendiente)} />
          <Cifra titulo="Vencido" valor={formatearBs(d.total_vencido)} tono={Number(d.total_vencido) > 0 ? 'rojo' : undefined} />
          <Cifra titulo="Cobrado este mes" valor={formatearBs(d.cobrado_mes)} />
        </div>
      )}
      {d && cadenas.length === 0 && <Vacio>Ninguna empresa le debe. Todo cobrado.</Vacio>}
      <div className="grid gap-3 lg:grid-cols-2">
        {cadenas.map((c) => {
          const detalle = d?.cuentas.filter((x) => x.cadena.id === c.cadena.id) ?? []
          const verDetalle = abierta === c.cadena.id
          return (
            <Tarjeta key={c.cadena.id} className="space-y-3 p-5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h2 className="text-lg font-semibold">{c.cadena.nombre}</h2>
                  <p className="text-sm text-slate-500">Le debe</p>
                  <p className="text-3xl font-semibold tracking-tight tabular-nums">{formatearBs(c.pendiente)}</p>
                </div>
                {puede('finanzas.cobros') && Number(c.pendiente) > 0 && (
                  <Link to={`/finanzas/cobros/nuevo?cadena=${c.cadena.id}`}>
                    <Boton>
                      <Banknote size={16} /> Registrar cobro
                    </Boton>
                  </Link>
                )}
              </div>
              <div className="space-y-1 text-sm">
                {Number(c.vencido) > 0 ? (
                  <p className="flex items-center gap-1 font-medium text-red-700">
                    <AlertTriangle size={14} aria-hidden /> Vencido: {formatearBs(c.vencido)}
                  </p>
                ) : (
                  Number(c.pendiente) > 0 && <p className="text-emerald-700">Nada vencido</p>
                )}
                {c.mas_antiguo && (
                  <p className="text-slate-500">
                    {c.pedidos_pendientes} entrega(s) sin cobrar desde el {formatearDia(c.mas_antiguo)}
                  </p>
                )}
                {Number(c.a_favor) > 0 && <p className="text-slate-600">Saldo a favor de {c.cadena.nombre}: {formatearBs(c.a_favor)}</p>}
              </div>
              <div className="flex flex-wrap gap-2 border-t border-slate-100 pt-3">
                <Boton variante="fantasma" className="min-h-8 text-xs" onClick={() => setAbierta(verDetalle ? null : c.cadena.id)} aria-expanded={verDetalle}>
                  {verDetalle ? 'Ocultar pedidos' : 'Ver de qué pedidos es'}
                </Boton>
                {puede('finanzas.cobros') && Number(c.pendiente) > 0 && (
                  <Boton variante="fantasma" className="min-h-8 text-xs" onClick={() => setRebajando(c)}>
                    Rebajar saldo
                  </Boton>
                )}
              </div>
              {verDetalle && (
                <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200 text-sm">
                  {detalle.map((x) => (
                    <li key={x.pedido_id} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2">
                      <div className="min-w-0 flex-1">
                        <Link to={`/pedidos/${x.pedido_id}`} className="font-medium text-marca-800 hover:underline">
                          #{x.numero}
                        </Link>
                        <span className="text-slate-500">
                          {' '}
                          · {x.sucursal ?? x.cadena.nombre}
                          {x.numero_oc && ` · O/C ${x.numero_oc}`}
                        </span>
                        <div className="text-xs text-slate-500">
                          Entregado {formatearDia(x.fecha)} · vence {formatearDia(x.vencimiento)}
                        </div>
                      </div>
                      <span className="tabular-nums">{formatearBs(x.saldo)}</span>
                      <InsigniaCuenta cuenta={x} />
                    </li>
                  ))}
                </ul>
              )}
            </Tarjeta>
          )
        })}
      </div>
      {rebajando && <RebajarSaldo cadena={rebajando} onCerrar={() => setRebajando(null)} />}
    </div>
  )
}

function RebajarSaldo({ cadena, onCerrar }: { cadena: ResumenCadena; onCerrar: () => void }) {
  const queryClient = useQueryClient()
  const [monto, setMonto] = useState('')
  const [motivo, setMotivo] = useState('')
  const rebajar = useMutation({
    mutationFn: () => api(`/finanzas/por-cobrar/cadenas/${cadena.cadena.id}/ajustar`, { metodo: 'POST', cuerpo: { monto, motivo } }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['por-cobrar'] })
      void queryClient.invalidateQueries({ queryKey: ['cobros'] })
      onCerrar()
    },
  })
  return (
    <Modal abierto titulo={`Rebajar lo que debe ${cadena.cadena.nombre}`} onCerrar={onCerrar}>
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault()
          rebajar.mutate()
        }}
      >
        <p className="text-sm text-slate-600">
          Para lo que la empresa no va a pagar (por ejemplo, un error reconocido en la factura). Hoy debe {formatearBs(cadena.pendiente)}. Queda registrado y se puede
          deshacer anulándolo en «Cobros».
        </p>
        {rebajar.isError && <Aviso>{mensajeError(rebajar.error)}</Aviso>}
        <Campo etiqueta="Monto a rebajar (Bs)">
          <Entrada required inputMode="decimal" value={monto} onChange={(e) => setMonto(e.target.value.replace(',', '.'))} />
        </Campo>
        <Campo etiqueta="Motivo">
          <Entrada required minLength={3} maxLength={300} value={motivo} onChange={(e) => setMotivo(e.target.value)} />
        </Campo>
        <div className="flex justify-end gap-2">
          <Boton variante="secundario" onClick={onCerrar}>
            Cancelar
          </Boton>
          <Boton type="submit" disabled={rebajar.isPending}>
            Rebajar saldo
          </Boton>
        </div>
      </form>
    </Modal>
  )
}

// ================================================================ cobros

const TAMANO = 30

function SeccionCobros() {
  const [cadena, setCadena] = useState('')
  const [pagina, setPagina] = useState(1)
  const [abierto, setAbierto] = useState<string | null>(null)
  const cadenas = useCadenas()
  const cobros = useQuery({
    queryKey: ['cobros', cadena, pagina],
    queryFn: () => api<Pagina<CobroResumen>>('/finanzas/cobros', { params: { cadena_id: cadena, pagina, tamano: TAMANO } }),
    placeholderData: keepPreviousData,
  })
  return (
    <div className="space-y-4">
      <div className="w-full sm:w-64">
        <Campo etiqueta="Cadena">
          <Selector value={cadena} onChange={(e) => (setCadena(e.target.value), setPagina(1))}>
            <option value="">Todas</option>
            {cadenas.data?.map((c) => (
              <option key={c.id} value={c.id}>
                {c.nombre}
              </option>
            ))}
          </Selector>
        </Campo>
      </div>
      {cobros.isError && <Aviso>{mensajeError(cobros.error)}</Aviso>}
      {cobros.data?.items.length === 0 && <Vacio>Todavía no se registró ningún cobro.</Vacio>}
      {!!cobros.data?.items.length && (
        <Tabla>
          <thead className={CABECERA_TABLA}>
            <tr>
              <th>Fecha</th>
              <th>Cadena</th>
              <th className="hidden sm:table-cell">N.º de operación</th>
              <th className="text-right">Monto</th>
              <th className="hidden md:table-cell">Pedidos</th>
              <th>Estado</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {cobros.data.items.map((c) => (
              <tr key={c.id} className="cursor-pointer hover:bg-slate-50" onClick={() => setAbierto(c.id)}>
                <td className="whitespace-nowrap">
                  <button type="button" className="font-medium text-marca-800 hover:underline">
                    {formatearDia(c.fecha)}
                  </button>
                  <div className="text-xs text-slate-500">#{c.numero}</div>
                </td>
                <td>{c.cadena.nombre}</td>
                <td className="hidden sm:table-cell">{c.es_cierre ? <span className="text-slate-500">Cierre de saldo</span> : (c.referencia ?? '—')}</td>
                <td className="text-right whitespace-nowrap tabular-nums">
                  {formatearBs(c.monto)}
                  {Number(c.diferencias) > 0 && <div className="text-xs text-slate-500">dif. {formatearBs(c.diferencias)}</div>}
                </td>
                <td className="hidden md:table-cell">{c.pedidos}</td>
                <td>{c.estado === 'ANULADO' ? <Insignia tono="rojo">Anulado</Insignia> : <Insignia tono="verde">Registrado</Insignia>}</td>
              </tr>
            ))}
          </tbody>
        </Tabla>
      )}
      {cobros.data && <Paginador pagina={pagina} total={cobros.data.total} tamano={TAMANO} onCambio={setPagina} />}
      {abierto && <DetalleCobro id={abierto} onCerrar={() => setAbierto(null)} />}
    </div>
  )
}

function DetalleCobro({ id, onCerrar }: { id: string; onCerrar: () => void }) {
  const puede = usePuede()
  const queryClient = useQueryClient()
  const [anulando, setAnulando] = useState(false)
  const [motivo, setMotivo] = useState('')
  const cobro = useQuery({ queryKey: ['cobro', id], queryFn: () => api<CobroDetalle>(`/finanzas/cobros/${id}`) })
  const alCambiar = (c: CobroDetalle) => {
    queryClient.setQueryData(['cobro', id], c)
    void queryClient.invalidateQueries({ queryKey: ['cobros'] })
    void queryClient.invalidateQueries({ queryKey: ['por-cobrar'] })
  }
  const anular = useMutation({
    mutationFn: () => api<CobroDetalle>(`/finanzas/cobros/${id}/anular`, { metodo: 'POST', cuerpo: { motivo } }),
    onSuccess: (c) => (alCambiar(c), setAnulando(false)),
  })
  const adjuntar = useMutation({
    mutationFn: (archivo: File) => {
      const datos = new FormData()
      datos.append('archivo', archivo)
      return api<CobroDetalle>(`/finanzas/cobros/${id}/comprobante`, { metodo: 'POST', cuerpo: datos })
    },
    onSuccess: alCambiar,
  })
  const c = cobro.data
  return (
    <Modal abierto titulo={c ? `${c.es_cierre ? 'Cierre de saldo' : 'Cobro'} #${c.numero}` : 'Cobro'} onCerrar={onCerrar}>
      {cobro.isError && <Aviso>{mensajeError(cobro.error)}</Aviso>}
      {c && (
        <div className="space-y-4 text-sm">
          {c.estado === 'ANULADO' && <Aviso>Anulado: {c.anulacion_motivo}</Aviso>}
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2">
            <dt className="text-slate-500">Cadena</dt>
            <dd>{c.cadena.nombre}</dd>
            <dt className="text-slate-500">Fecha</dt>
            <dd>{formatearDia(c.fecha)}</dd>
            <dt className="text-slate-500">Monto</dt>
            <dd className="font-semibold">{formatearBs(c.monto)}</dd>
            {c.banco && (
              <>
                <dt className="text-slate-500">Banco</dt>
                <dd>{c.banco}</dd>
              </>
            )}
            {c.referencia && (
              <>
                <dt className="text-slate-500">N.º de operación</dt>
                <dd>{c.referencia}</dd>
              </>
            )}
            <dt className="text-slate-500">Registrado por</dt>
            <dd>{c.usuario_nombre}</dd>
          </dl>
          {c.observaciones && <p className="text-slate-600">{c.observaciones}</p>}
          <div className="overflow-x-auto rounded-md border border-slate-200">
            <table className="w-full text-left [&_td]:px-3 [&_td]:py-2 [&_th]:px-3 [&_th]:py-2">
              <thead className={CABECERA_TABLA}>
                <tr>
                  <th>Pedido</th>
                  <th className="text-right">Aplicado</th>
                  <th className="text-right">Diferencia</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {c.detalles.map((d) => (
                  <tr key={d.pedido_id}>
                    <td>
                      <Link to={`/pedidos/${d.pedido_id}`} className="font-medium text-marca-800 hover:underline">
                        #{d.pedido_numero}
                      </Link>
                      <div className="text-xs text-slate-500">{[d.numero_oc && `O/C ${d.numero_oc}`, d.sucursal].filter(Boolean).join(' · ')}</div>
                      {d.motivo_diferencia && <div className="text-xs text-amber-800">{d.motivo_diferencia}</div>}
                    </td>
                    <td className="text-right tabular-nums">{formatearBs(d.monto)}</td>
                    <td className="text-right tabular-nums">{Number(d.diferencia) > 0 ? formatearBs(d.diferencia) : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {c.comprobante_id ? (
              <a href={urlComprobante(c.comprobante_id)} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-marca-700 hover:underline">
                <FileText size={16} /> {c.comprobante_nombre ?? 'Comprobante'}
              </a>
            ) : (
              <span className="text-slate-500">Sin comprobante adjunto.</span>
            )}
            {c.estado === 'REGISTRADO' && !c.es_cierre && puede('finanzas.cobros') && (
              <label className="inline-flex cursor-pointer items-center gap-1 rounded-md border border-slate-300 px-3 py-1.5 hover:bg-slate-50">
                <Paperclip size={14} /> {adjuntar.isPending ? 'Subiendo…' : c.comprobante_id ? 'Reemplazar' : 'Adjuntar comprobante'}
                <input
                  type="file"
                  accept="image/*,application/pdf"
                  className="sr-only"
                  onChange={(e) => {
                    const archivo = e.target.files?.[0]
                    if (archivo) adjuntar.mutate(archivo)
                    e.target.value = ''
                  }}
                />
              </label>
            )}
          </div>
          {adjuntar.isError && <Aviso>{mensajeError(adjuntar.error)}</Aviso>}
          {c.estado === 'REGISTRADO' && puede('finanzas.cobros') && !anulando && (
            <Boton variante="secundario" onClick={() => setAnulando(true)}>
              Anular {c.es_cierre ? 'cierre' : 'cobro'}
            </Boton>
          )}
          {anulando && (
            <form
              className="space-y-3 rounded-md border border-red-200 bg-red-50/50 p-3"
              onSubmit={(e) => {
                e.preventDefault()
                anular.mutate()
              }}
            >
              <p className="text-slate-700">Los pedidos vuelven a quedar con saldo por cobrar.</p>
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
          )}
        </div>
      )}
    </Modal>
  )
}

// ================================================================ gastos

function useCategoriasGasto() {
  return useQuery({ queryKey: ['categorias-gasto'], queryFn: () => api<CategoriaGasto[]>('/finanzas/categorias-gasto') })
}

function SeccionGastos() {
  const puede = usePuede()
  const queryClient = useQueryClient()
  const hoy = hoyLaPaz()
  const [mes, setMes] = useState(hoy.slice(0, 7))
  const [categoria, setCategoria] = useState('')
  const [ubicacion, setUbicacion] = useState('')
  const [buscar, setBuscar] = useState('')
  const [pagina, setPagina] = useState(1)
  const [nuevo, setNuevo] = useState(false)
  const [gestionando, setGestionando] = useState(false)
  const [anulando, setAnulando] = useState<Gasto | null>(null)
  const [motivo, setMotivo] = useState('')
  const categorias = useCategoriasGasto()
  const ubicaciones = useUbicaciones()
  const gastos = useQuery({
    queryKey: ['gastos', mes, categoria, ubicacion, buscar, pagina],
    queryFn: () =>
      api<PaginaGastos>('/finanzas/gastos', {
        params: {
          desde: mes ? primerDiaMes(mes) : null,
          hasta: mes ? ultimoDiaMes(mes) : null,
          categoria_id: categoria,
          ubicacion_id: ubicacion,
          buscar,
          pagina,
          tamano: TAMANO,
        },
      }),
    placeholderData: keepPreviousData,
  })
  const anular = useMutation({
    mutationFn: () => api(`/finanzas/gastos/${anulando!.id}/anular`, { metodo: 'POST', cuerpo: { motivo } }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['gastos'] })
      setAnulando(null)
      setMotivo('')
    },
  })
  const filtrar = (cambio: () => void) => (cambio(), setPagina(1))
  const g = gastos.data

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap justify-end gap-2">
        {puede('finanzas.gastos') && (
          <>
            <Boton variante="secundario" onClick={() => setGestionando(true)}>
              <Settings2 size={16} /> Categorías
            </Boton>
            <Boton onClick={() => setNuevo(true)}>
              <Plus size={16} /> Registrar gasto
            </Boton>
          </>
        )}
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Campo etiqueta="Mes">
          <Entrada type="month" value={mes} max={hoy.slice(0, 7)} onChange={(e) => filtrar(() => setMes(e.target.value))} />
        </Campo>
        <Campo etiqueta="Categoría">
          <Selector value={categoria} onChange={(e) => filtrar(() => setCategoria(e.target.value))}>
            <option value="">Todas</option>
            {categorias.data?.map((c) => (
              <option key={c.id} value={c.id}>
                {c.nombre}
              </option>
            ))}
          </Selector>
        </Campo>
        <Campo etiqueta="Ubicación">
          <Selector value={ubicacion} onChange={(e) => filtrar(() => setUbicacion(e.target.value))}>
            <option value="">Todas</option>
            {ubicaciones.data?.map((u) => (
              <option key={u.id} value={u.id}>
                {u.nombre}
              </option>
            ))}
          </Selector>
        </Campo>
        <Campo etiqueta="Buscar (a quién, detalle)">
          <Entrada type="search" value={buscar} onChange={(e) => filtrar(() => setBuscar(e.target.value))} />
        </Campo>
      </div>
      {gastos.isError && <Aviso>{mensajeError(gastos.error)}</Aviso>}
      {g && (
        <Tarjeta className="p-4">
          <p className="text-sm text-slate-600">
            Total {mes ? `de ${nombreMes(primerDiaMes(mes))}` : ''}: <strong className="text-lg text-slate-900 tabular-nums">{formatearBs(g.suma)}</strong>
          </p>
          {g.por_categoria.length > 0 && (
            <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm">
              {g.por_categoria.map((c) => (
                <li key={c.categoria.id}>
                  {c.categoria.nombre}: <span className="tabular-nums">{formatearBs(c.total)}</span>
                </li>
              ))}
            </ul>
          )}
        </Tarjeta>
      )}
      {g?.items.length === 0 && <Vacio>No hay gastos registrados con estos filtros.</Vacio>}
      {!!g?.items.length && (
        <Tabla>
          <thead className={CABECERA_TABLA}>
            <tr>
              <th>Fecha</th>
              <th>Gasto</th>
              <th className="hidden md:table-cell">Ubicación</th>
              <th className="text-right">Monto</th>
              <th />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {g.items.map((x) => (
              <tr key={x.id} className={x.estado === 'ANULADO' ? 'text-slate-400' : ''}>
                <td className="whitespace-nowrap">{formatearDia(x.fecha)}</td>
                <td>
                  <div className="font-medium">
                    {x.categoria.nombre}
                    {x.beneficiario && <span className="font-normal"> · {x.beneficiario}</span>}
                  </div>
                  <div className="text-xs text-slate-500">
                    {[x.descripcion, x.con_factura && `Factura ${x.numero_factura ?? ''}`.trim()].filter(Boolean).join(' · ')}
                    {x.estado === 'ANULADO' && <span className="text-red-700"> Anulado: {x.anulacion_motivo}</span>}
                  </div>
                  {x.comprobante_id && (
                    <a href={urlComprobante(x.comprobante_id)} target="_blank" rel="noreferrer" className="text-xs text-marca-700 hover:underline">
                      Ver comprobante
                    </a>
                  )}
                </td>
                <td className="hidden md:table-cell">{x.ubicacion?.nombre ?? 'General'}</td>
                <td className={`text-right whitespace-nowrap tabular-nums ${x.estado === 'ANULADO' ? 'line-through' : ''}`}>{formatearBs(x.monto)}</td>
                <td className="text-right">
                  {x.estado === 'REGISTRADO' && puede('finanzas.gastos') && (
                    <button type="button" className="text-xs text-slate-500 hover:text-red-700" onClick={() => setAnulando(x)}>
                      Anular
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </Tabla>
      )}
      {g && <Paginador pagina={pagina} total={g.total} tamano={TAMANO} onCambio={setPagina} />}

      {nuevo && <NuevoGasto categorias={categorias.data ?? []} onCerrar={() => setNuevo(false)} />}
      {gestionando && <GestionCategorias categorias={categorias.data ?? []} onCerrar={() => setGestionando(false)} />}
      <Modal abierto={!!anulando} titulo="Anular gasto" onCerrar={() => setAnulando(null)}>
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault()
            anular.mutate()
          }}
        >
          <p className="text-sm text-slate-600">
            {anulando?.categoria.nombre} de {formatearBs(anulando?.monto)} del {formatearDia(anulando?.fecha)}. Queda en el historial, pero deja de sumar.
          </p>
          {anular.isError && <Aviso>{mensajeError(anular.error)}</Aviso>}
          <Campo etiqueta="Motivo">
            <Entrada required minLength={5} value={motivo} onChange={(e) => setMotivo(e.target.value)} />
          </Campo>
          <div className="flex justify-end gap-2">
            <Boton variante="secundario" onClick={() => setAnulando(null)}>
              Cancelar
            </Boton>
            <Boton type="submit" variante="peligro" disabled={anular.isPending}>
              Anular
            </Boton>
          </div>
        </form>
      </Modal>
    </div>
  )
}

function NuevoGasto({ categorias, onCerrar }: { categorias: CategoriaGasto[]; onCerrar: () => void }) {
  const queryClient = useQueryClient()
  const ubicaciones = useUbicaciones()
  const activas = categorias.filter((c) => c.activo)
  const [f, setF] = useState({
    fecha: hoyLaPaz(),
    categoria_id: '',
    ubicacion_id: '',
    beneficiario: '',
    descripcion: '',
    monto: '',
    con_factura: false,
    numero_factura: '',
  })
  const [archivo, setArchivo] = useState<File | null>(null)
  const categoria = activas.find((c) => c.id === f.categoria_id)
  const registrar = useMutation({
    mutationFn: async () => {
      const gasto = await api<Gasto>('/finanzas/gastos', {
        metodo: 'POST',
        cuerpo: {
          ...f,
          ubicacion_id: f.ubicacion_id || null,
          beneficiario: f.beneficiario || null,
          descripcion: f.descripcion || null,
          numero_factura: f.con_factura ? f.numero_factura || null : null,
        },
      })
      if (archivo) {
        const datos = new FormData()
        datos.append('archivo', archivo)
        await api(`/finanzas/gastos/${gasto.id}/comprobante`, { metodo: 'POST', cuerpo: datos })
      }
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['gastos'] })
      onCerrar()
    },
  })
  return (
    <Modal abierto titulo="Registrar gasto" onCerrar={onCerrar}>
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault()
          registrar.mutate()
        }}
      >
        <div className="grid gap-3 sm:grid-cols-2">
          <Campo etiqueta="Categoría">
            <Selector
              required
              value={f.categoria_id}
              onChange={(e) => {
                const elegida = activas.find((c) => c.id === e.target.value)
                setF((x) => ({ ...x, categoria_id: e.target.value, con_factura: elegida?.factura_habitual ?? x.con_factura }))
              }}
            >
              <option value="">Elegir…</option>
              {activas.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.nombre}
                </option>
              ))}
            </Selector>
          </Campo>
          <Campo etiqueta="Monto (Bs)">
            <Entrada required inputMode="decimal" value={f.monto} onChange={(e) => setF((x) => ({ ...x, monto: e.target.value.replace(',', '.') }))} />
          </Campo>
          <Campo etiqueta="Fecha">
            <Entrada type="date" required max={hoyLaPaz()} value={f.fecha} onChange={(e) => setF((x) => ({ ...x, fecha: e.target.value }))} />
          </Campo>
          <Campo etiqueta="Ubicación">
            <Selector value={f.ubicacion_id} onChange={(e) => setF((x) => ({ ...x, ubicacion_id: e.target.value }))}>
              <option value="">General (de toda la empresa)</option>
              {ubicaciones.data?.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.nombre}
                </option>
              ))}
            </Selector>
          </Campo>
        </div>
        <Campo etiqueta={categoria?.nombre === 'Sueldos' ? 'A quién se pagó' : 'A quién se pagó (opcional)'}>
          <Entrada
            required={categoria?.nombre === 'Sueldos'}
            maxLength={120}
            placeholder={categoria?.nombre === 'Sueldos' ? 'Nombre del empleado' : 'Persona o empresa'}
            value={f.beneficiario}
            onChange={(e) => setF((x) => ({ ...x, beneficiario: e.target.value }))}
          />
        </Campo>
        <Campo etiqueta="Detalle (opcional)">
          <Entrada maxLength={300} value={f.descripcion} onChange={(e) => setF((x) => ({ ...x, descripcion: e.target.value }))} />
        </Campo>
        <Casilla
          etiqueta="Tiene factura"
          descripcion="Las facturas a nombre de la empresa dan crédito fiscal (descuentan IVA)."
          checked={f.con_factura}
          onChange={(e) => setF((x) => ({ ...x, con_factura: e.target.checked }))}
        />
        {f.con_factura && (
          <Campo etiqueta="N.º de factura (opcional)">
            <Entrada maxLength={40} value={f.numero_factura} onChange={(e) => setF((x) => ({ ...x, numero_factura: e.target.value }))} />
          </Campo>
        )}
        <Campo etiqueta="Comprobante (foto o PDF, opcional)">
          <input type="file" accept="image/*,application/pdf" className="block w-full text-sm" onChange={(e) => setArchivo(e.target.files?.[0] ?? null)} />
        </Campo>
        {registrar.isError && <Aviso>{mensajeError(registrar.error)}</Aviso>}
        <div className="flex justify-end gap-2">
          <Boton variante="secundario" onClick={onCerrar}>
            Cancelar
          </Boton>
          <Boton type="submit" disabled={registrar.isPending}>
            {registrar.isPending ? 'Guardando…' : 'Registrar gasto'}
          </Boton>
        </div>
      </form>
    </Modal>
  )
}

function GestionCategorias({ categorias, onCerrar }: { categorias: CategoriaGasto[]; onCerrar: () => void }) {
  const queryClient = useQueryClient()
  const [nombre, setNombre] = useState('')
  const [factura, setFactura] = useState(false)
  const refrescar = () => void queryClient.invalidateQueries({ queryKey: ['categorias-gasto'] })
  const crear = useMutation({
    mutationFn: () => api('/finanzas/categorias-gasto', { metodo: 'POST', cuerpo: { nombre, factura_habitual: factura, activo: true } }),
    onSuccess: () => (refrescar(), setNombre(''), setFactura(false)),
  })
  const editar = useMutation({
    mutationFn: (c: CategoriaGasto) => api(`/finanzas/categorias-gasto/${c.id}`, { metodo: 'PUT', cuerpo: c }),
    onSuccess: refrescar,
  })
  return (
    <Modal abierto titulo="Categorías de gasto" onCerrar={onCerrar}>
      <div className="space-y-4 text-sm">
        <ul className="divide-y divide-slate-100 rounded-md border border-slate-200">
          {categorias.map((c) => (
            <li key={c.id} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2">
              <span className={c.activo ? '' : 'text-slate-400 line-through'}>
                {c.nombre}
                {c.factura_habitual && <span className="ml-2 text-xs text-slate-500">(suele tener factura)</span>}
              </span>
              <Boton variante="fantasma" className="min-h-8 text-xs" disabled={editar.isPending} onClick={() => editar.mutate({ ...c, activo: !c.activo })}>
                {c.activo ? 'Desactivar' : 'Activar'}
              </Boton>
            </li>
          ))}
        </ul>
        <form
          className="space-y-2"
          onSubmit={(e) => {
            e.preventDefault()
            crear.mutate()
          }}
        >
          <Campo etiqueta="Nueva categoría">
            <Entrada required minLength={2} maxLength={60} value={nombre} onChange={(e) => setNombre(e.target.value)} />
          </Campo>
          <Casilla etiqueta="Suele tener factura" checked={factura} onChange={(e) => setFactura(e.target.checked)} />
          {(crear.isError || editar.isError) && <Aviso>{mensajeError(crear.error ?? editar.error)}</Aviso>}
          <Boton type="submit" disabled={crear.isPending}>
            <Plus size={16} /> Agregar
          </Boton>
        </form>
      </div>
    </Modal>
  )
}

// ================================================================ por pagar

function SeccionPorPagar() {
  const puede = usePuede()
  const queryClient = useQueryClient()
  const [pagando, setPagando] = useState<CompraPorPagar | null>(null)
  const [fecha, setFecha] = useState(hoyLaPaz())
  const deudas = useQuery({ queryKey: ['por-pagar'], queryFn: () => api<CompraPorPagar[]>('/finanzas/por-pagar') })
  const pagar = useMutation({
    mutationFn: () => api(`/finanzas/compras/${pagando!.id}/pagar`, { metodo: 'POST', cuerpo: { fecha } }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['por-pagar'] })
      void queryClient.invalidateQueries({ queryKey: ['compras'] })
      setPagando(null)
    },
  })
  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-600">
        Compras hechas a crédito que todavía no se pagaron. Las compras al contado se consideran pagadas el mismo día.
      </p>
      {deudas.isError && <Aviso>{mensajeError(deudas.error)}</Aviso>}
      {deudas.data?.length === 0 && <Vacio>No hay compras a crédito pendientes de pago.</Vacio>}
      {!!deudas.data?.length && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Object.values(
            deudas.data.reduce<Record<string, { nombre: string; total: number; compras: number }>>((acc, d) => {
              const x = (acc[d.proveedor.id] ??= { nombre: d.proveedor.nombre, total: 0, compras: 0 })
              x.total += Number(d.total)
              x.compras += 1
              return acc
            }, {}),
          ).map((x) => (
            <Cifra key={x.nombre} titulo={`Se le debe a ${x.nombre}`} valor={formatearBs(x.total)}>
              <p className="mt-1 text-xs text-slate-500">{x.compras} compra(s) a crédito</p>
            </Cifra>
          ))}
        </div>
      )}
      {!!deudas.data?.length && (
        <Tabla>
          <thead className={CABECERA_TABLA}>
            <tr>
              <th>Compra</th>
              <th>Proveedor</th>
              <th>Vence</th>
              <th className="text-right">Total</th>
              <th />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {deudas.data.map((d) => (
              <tr key={d.id}>
                <td>
                  <Link to={`/compras/${d.id}`} className="font-medium text-marca-800 hover:underline">
                    #{d.numero}
                  </Link>
                  <div className="text-xs text-slate-500">{formatearDia(d.fecha)}</div>
                </td>
                <td>{d.proveedor.nombre}</td>
                <td className="whitespace-nowrap">
                  {formatearDia(d.fecha_vencimiento)}
                  {d.dias_para_vencer !== null && (
                    <div className={`text-xs ${d.dias_para_vencer < 0 ? 'text-red-700' : d.dias_para_vencer <= 3 ? 'text-amber-700' : 'text-slate-500'}`}>
                      {d.dias_para_vencer < 0 ? `vencida hace ${-d.dias_para_vencer} d` : d.dias_para_vencer === 0 ? 'vence hoy' : `en ${d.dias_para_vencer} d`}
                    </div>
                  )}
                </td>
                <td className="text-right whitespace-nowrap tabular-nums">{formatearBs(d.total)}</td>
                <td className="text-right">
                  {puede('finanzas.gastos') && (
                    <Boton variante="secundario" className="min-h-9" onClick={() => (setPagando(d), setFecha(hoyLaPaz()))}>
                      Registrar pago
                    </Boton>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </Tabla>
      )}
      <Modal abierto={!!pagando} titulo={`Pago de la compra #${pagando?.numero ?? ''}`} onCerrar={() => setPagando(null)}>
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault()
            pagar.mutate()
          }}
        >
          <p className="text-sm text-slate-600">
            {pagando?.proveedor.nombre}: {formatearBs(pagando?.total)}
          </p>
          {pagar.isError && <Aviso>{mensajeError(pagar.error)}</Aviso>}
          <Campo etiqueta="Fecha del pago">
            <Entrada type="date" required max={hoyLaPaz()} min={pagando?.fecha} value={fecha} onChange={(e) => setFecha(e.target.value)} />
          </Campo>
          <div className="flex justify-end gap-2">
            <Boton variante="secundario" onClick={() => setPagando(null)}>
              Cancelar
            </Boton>
            <Boton type="submit" disabled={pagar.isPending}>
              Registrar pago
            </Boton>
          </div>
        </form>
      </Modal>
    </div>
  )
}

// ================================================================ impuestos

function SeccionImpuestos() {
  const puede = usePuede()
  const anioActual = Number(hoyLaPaz().slice(0, 4))
  const [anio, setAnio] = useState(anioActual)
  const meses = useQuery({
    queryKey: ['impuestos', anio],
    queryFn: () => api<ImpuestoMes[]>('/finanzas/impuestos', { params: { desde: `${anio}-01-01`, hasta: anio === anioActual ? hoyLaPaz() : `${anio}-12-31` } }),
    placeholderData: keepPreviousData,
    // Los meses vacíos antes del primer movimiento no aportan nada.
    select: (lista) => lista.slice(Math.max(0, lista.findIndex((m) => [m.ventas, m.iva_credito, m.saldo_anterior].some((v) => Number(v) !== 0)))),
  })
  const parametros = useQuery({ queryKey: ['parametros-finanzas'], queryFn: () => api<ParametrosFinanzas>('/finanzas/parametros') })
  const p = parametros.data
  const total = (clave: keyof ImpuestoMes) => (meses.data ?? []).reduce((s, m) => s + Number(m[clave]), 0)

  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-600">
        IVA {p ? `${Number(p.iva_pct)} %` : ''} sobre lo facturado (pedidos entregados en el mes), menos el crédito fiscal de las compras y gastos con factura. Si
        el crédito es mayor, el sobrante pasa al mes siguiente. IT {p ? `${Number(p.it_pct)} %` : ''} sobre lo facturado. Es una referencia para el contador.
      </p>
      <div className="w-32">
        <Campo etiqueta="Año">
          <Selector value={anio} onChange={(e) => setAnio(Number(e.target.value))}>
            {[0, 1, 2].map((i) => (
              <option key={i} value={anioActual - i}>
                {anioActual - i}
              </option>
            ))}
          </Selector>
        </Campo>
      </div>
      {meses.isError && <Aviso>{mensajeError(meses.error)}</Aviso>}
      {meses.data && (
        <Tabla>
          <thead className={CABECERA_TABLA}>
            <tr>
              <th>Mes</th>
              <th className="text-right">Facturado</th>
              <th className="hidden text-right md:table-cell">IVA débito</th>
              <th className="hidden text-right md:table-cell">IVA crédito</th>
              <th className="hidden text-right lg:table-cell">Saldo a favor anterior</th>
              <th className="text-right">IVA a pagar</th>
              <th className="text-right">IT</th>
              <th className="text-right">Total</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 tabular-nums">
            {meses.data.map((m) => (
              <tr key={m.mes}>
                <td className="whitespace-nowrap">{nombreMes(m.mes)}</td>
                <td className="text-right whitespace-nowrap">{formatearBs(m.ventas)}</td>
                <td className="hidden text-right whitespace-nowrap md:table-cell">{formatearBs(m.iva_debito)}</td>
                <td className="hidden text-right whitespace-nowrap md:table-cell">{formatearBs(m.iva_credito)}</td>
                <td className="hidden text-right whitespace-nowrap lg:table-cell">{formatearBs(m.saldo_anterior)}</td>
                <td className="text-right whitespace-nowrap">{formatearBs(m.iva_pagar)}</td>
                <td className="text-right whitespace-nowrap">{formatearBs(m.it)}</td>
                <td className="text-right font-semibold whitespace-nowrap">{formatearBs(m.total_pagar)}</td>
              </tr>
            ))}
            <tr className="bg-slate-50 font-semibold">
              <td>Total {anio}</td>
              <td className="text-right whitespace-nowrap">{formatearBs(total('ventas'))}</td>
              <td className="hidden text-right whitespace-nowrap md:table-cell">{formatearBs(total('iva_debito'))}</td>
              <td className="hidden text-right whitespace-nowrap md:table-cell">{formatearBs(total('iva_credito'))}</td>
              <td className="hidden lg:table-cell" />
              <td className="text-right whitespace-nowrap">{formatearBs(total('iva_pagar'))}</td>
              <td className="text-right whitespace-nowrap">{formatearBs(total('it'))}</td>
              <td className="text-right whitespace-nowrap">{formatearBs(total('total_pagar'))}</td>
            </tr>
          </tbody>
        </Tabla>
      )}
      <p className="text-xs text-slate-500">
        Más detalle (compras y gastos con factura, crédito que pasa al mes siguiente) y exportación a Excel en{' '}
        <Link to="/reportes?r=impuestos" className="text-marca-700 underline">
          Reportes → Impuestos
        </Link>
        .
      </p>
      {p && puede('configuracion.gestionar') && <FormParametros parametros={p} />}
    </div>
  )
}

function FormParametros({ parametros }: { parametros: ParametrosFinanzas }) {
  const queryClient = useQueryClient()
  const [f, setF] = useState({ dias_credito: String(parametros.dias_credito), iva_pct: parametros.iva_pct, it_pct: parametros.it_pct })
  const guardar = useMutation({
    mutationFn: () =>
      api<ParametrosFinanzas>('/finanzas/parametros', {
        metodo: 'PUT',
        cuerpo: { dias_credito: Number(f.dias_credito), iva_pct: f.iva_pct, it_pct: f.it_pct },
      }),
    onSuccess: (p) => {
      queryClient.setQueryData(['parametros-finanzas'], p)
      void queryClient.invalidateQueries({ queryKey: ['impuestos'] })
      void queryClient.invalidateQueries({ queryKey: ['por-cobrar'] })
    },
  })
  return (
    <Tarjeta className="p-4">
      <h2 className="mb-3 text-sm font-semibold text-slate-800">Parámetros</h2>
      <form
        className="grid items-end gap-3 sm:grid-cols-4"
        onSubmit={(e) => {
          e.preventDefault()
          guardar.mutate()
        }}
      >
        <Campo etiqueta="Plazo de cobro (días)" ayuda="Pasado este plazo desde la entrega, el cobro está vencido.">
          <Entrada type="number" min={1} max={365} required value={f.dias_credito} onChange={(e) => setF((x) => ({ ...x, dias_credito: e.target.value }))} />
        </Campo>
        <Campo etiqueta="IVA (%)">
          <Entrada inputMode="decimal" required value={f.iva_pct} onChange={(e) => setF((x) => ({ ...x, iva_pct: e.target.value.replace(',', '.') }))} />
        </Campo>
        <Campo etiqueta="IT (%)">
          <Entrada inputMode="decimal" required value={f.it_pct} onChange={(e) => setF((x) => ({ ...x, it_pct: e.target.value.replace(',', '.') }))} />
        </Campo>
        <Boton type="submit" disabled={guardar.isPending}>
          Guardar
        </Boton>
      </form>
      {guardar.isError && <div className="mt-3"><Aviso>{mensajeError(guardar.error)}</Aviso></div>}
      {guardar.isSuccess && <div className="mt-3"><Aviso tipo="exito">Parámetros guardados.</Aviso></div>}
    </Tarjeta>
  )
}
