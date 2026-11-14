import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, CloudOff, Plus, RefreshCw, Search, Trash2 } from 'lucide-react'
import { useCallback, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { SelectorArchivos } from '../../components/pedidos/SelectorArchivos'
import { Aviso, Boton, CABECERA_TABLA, Campo, Encabezado, Entrada, Insignia, Paginador, Selector, Tabla, Tarjeta, Vacio } from '../../components/ui'
import { api, ErrorApi, mensajeError } from '../../lib/api'
import { guardarEnvio, nuevoEnvio, procesarEnvio, useColaSubida } from '../../lib/colaSubida'
import { useCadenas, useUbicaciones } from '../../lib/consultas'
import { formatearBs, formatearDia, formatearFecha, formatearPorcentaje } from '../../lib/formato'
import { usePuede, useYo } from '../../lib/sesion'
import { NOMBRE_ESTADO_PEDIDO, type EstadoPedido, type Pagina, type PedidoResumen } from '../../lib/tipos'

const TAMANO = 30

const TONO_ESTADO: Record<EstadoPedido, 'gris' | 'azul' | 'ambar' | 'verde' | 'rojo'> = {
  BORRADOR: 'gris',
  CONFIRMADO: 'azul',
  ALISTADO: 'ambar',
  ENTREGADO: 'verde',
  ANULADO: 'rojo',
}

export function InsigniaEstado({ estado }: { estado: EstadoPedido }) {
  return <Insignia tono={TONO_ESTADO[estado]}>{NOMBRE_ESTADO_PEDIDO[estado]}</Insignia>
}

const ESTADOS: (EstadoPedido | '')[] = ['', 'BORRADOR', 'CONFIRMADO', 'ALISTADO', 'ENTREGADO', 'ANULADO']

export function Pedidos() {
  const puede = usePuede()
  const queryClient = useQueryClient()
  const cadenas = useCadenas()
  const [estado, setEstado] = useState<EstadoPedido | ''>('')
  const [cadena, setCadena] = useState('')
  const [buscar, setBuscar] = useState('')
  const [pagina, setPagina] = useState(1)
  const pedidos = useQuery({
    queryKey: ['pedidos', estado, cadena, buscar, pagina],
    queryFn: () =>
      api<Pagina<PedidoResumen>>('/pedidos', { params: { estado, cadena_id: cadena, buscar, pagina, tamano: TAMANO } }),
    placeholderData: keepPreviousData,
  })
  const alSubir = useCallback(() => void queryClient.invalidateQueries({ queryKey: ['pedidos'] }), [queryClient])
  const cola = useColaSubida(alSubir)
  const verGanancia = puede('costos.ver')

  return (
    <>
      <Encabezado
        titulo="Pedidos"
        descripcion="Órdenes de compra de los supermercados: revisión, reserva, alistado y entrega."
        acciones={
          puede('pedidos.escanear') && (
            <Link to="/pedidos/nuevo">
              <Boton>
                <Plus size={16} /> Nuevo pedido
              </Boton>
            </Link>
          )
        }
      />

      {cola.pendientes.length > 0 && (
        <Tarjeta className="mb-4 border-amber-300 bg-amber-50 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="flex items-center gap-2 text-sm font-medium text-amber-900">
              <CloudOff size={18} /> {cola.pendientes.length} OC guardada(s) en este dispositivo, pendientes de subir
            </p>
            <Boton variante="secundario" disabled={cola.subiendo} onClick={() => void cola.reintentar()}>
              <RefreshCw size={16} className={cola.subiendo ? 'animate-spin' : ''} /> {cola.subiendo ? 'Subiendo…' : 'Subir ahora'}
            </Boton>
          </div>
          <ul className="mt-2 space-y-1 text-sm text-amber-900">
            {cola.pendientes.map((e) => (
              <li key={e.id} className="flex items-center justify-between gap-2">
                <span>
                  {e.ubicacion_nombre} · {e.archivos.length} archivo(s) · {formatearFecha(new Date(e.creado).toISOString())}
                  {e.error && <span className="block text-xs text-red-700">Último intento: {e.error}</span>}
                </span>
                <Boton
                  variante="fantasma"
                  className="min-h-8 px-2 text-red-600"
                  aria-label="Descartar"
                  onClick={() => {
                    if (confirm('¿Descartar estas fotos? No se podrán recuperar.')) void cola.descartar(e.id)
                  }}
                >
                  <Trash2 size={16} />
                </Boton>
              </li>
            ))}
          </ul>
        </Tarjeta>
      )}

      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        <Campo etiqueta="Buscar">
          <div className="relative">
            <Search size={16} className="pointer-events-none absolute top-3 left-3 text-slate-400" />
            <Entrada
              className="pl-9"
              placeholder="N.º de OC o de pedido"
              value={buscar}
              onChange={(e) => {
                setBuscar(e.target.value)
                setPagina(1)
              }}
            />
          </div>
        </Campo>
        <Campo etiqueta="Estado">
          <Selector
            value={estado}
            onChange={(e) => {
              setEstado(e.target.value as EstadoPedido | '')
              setPagina(1)
            }}
          >
            {ESTADOS.map((e) => (
              <option key={e} value={e}>
                {e ? NOMBRE_ESTADO_PEDIDO[e] : 'Todos'}
              </option>
            ))}
          </Selector>
        </Campo>
        <Campo etiqueta="Cadena">
          <Selector
            value={cadena}
            onChange={(e) => {
              setCadena(e.target.value)
              setPagina(1)
            }}
          >
            <option value="">Todas</option>
            {cadenas.data?.map((c) => (
              <option key={c.id} value={c.id}>
                {c.nombre}
              </option>
            ))}
          </Selector>
        </Campo>
      </div>

      {pedidos.isError && <Aviso>{mensajeError(pedidos.error)}</Aviso>}
      {pedidos.data?.items.length === 0 && <Vacio>No hay pedidos con esos filtros.</Vacio>}
      {!!pedidos.data?.items.length && (
        <>
          {/* Celular: tarjetas */}
          <ul className="space-y-2 md:hidden">
            {pedidos.data.items.map((p) => (
              <li key={p.id}>
                <Link to={`/pedidos/${p.id}`} className="block rounded-lg border border-slate-200 bg-white p-3 shadow-sm active:bg-slate-50">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="font-medium">
                        #{p.numero} {p.numero_oc && <span className="text-slate-500">· OC {p.numero_oc}</span>}
                      </p>
                      <p className="truncate text-sm text-slate-600">
                        {p.cadena ? `${p.cadena.nombre} · ${p.sucursal_cliente?.nombre ?? '—'}` : 'Sin datos de la OC'}
                      </p>
                    </div>
                    <InsigniaEstado estado={p.estado} />
                  </div>
                  <div className="mt-2 flex justify-between text-xs text-slate-500">
                    <span>
                      {p.ubicacion.nombre} · {formatearDia(p.fecha_oc) !== '—' ? formatearDia(p.fecha_oc) : formatearFecha(p.created_at)}
                    </span>
                    <span className="font-medium text-slate-700">{formatearBs(p.total_calculado)}</span>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
          {/* Escritorio: tabla */}
          <div className="hidden md:block">
            <Tabla>
              <thead className={CABECERA_TABLA}>
                <tr>
                  <th>N.º</th>
                  <th>OC</th>
                  <th>Cliente</th>
                  <th>Despacha</th>
                  <th>Fecha OC</th>
                  <th className="text-right">Total</th>
                  {verGanancia && <th className="text-right">Margen</th>}
                  <th>Estado</th>
                  <th>Responsable</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {pedidos.data.items.map((p) => (
                  <tr key={p.id} className="hover:bg-slate-50">
                    <td>
                      <Link to={`/pedidos/${p.id}`} className="font-medium text-marca-800 hover:underline">
                        #{p.numero}
                      </Link>
                    </td>
                    <td>{p.numero_oc ?? '—'}</td>
                    <td>
                      {p.cadena?.nombre ?? '—'}
                      {p.sucursal_cliente && <span className="block text-xs text-slate-500">{p.sucursal_cliente.nombre}</span>}
                    </td>
                    <td className="text-slate-600">{p.ubicacion.nombre}</td>
                    <td className="whitespace-nowrap text-slate-600">{formatearDia(p.fecha_oc)}</td>
                    <td className="text-right whitespace-nowrap">{formatearBs(p.total_calculado)}</td>
                    {verGanancia && <td className="text-right">{formatearPorcentaje(p.margen)}</td>}
                    <td>
                      <InsigniaEstado estado={p.estado} />
                    </td>
                    <td className="text-slate-600">{p.responsable_nombre}</td>
                  </tr>
                ))}
              </tbody>
            </Tabla>
          </div>
        </>
      )}
      <Paginador pagina={pagina} total={pedidos.data?.total ?? 0} tamano={TAMANO} onCambio={setPagina} />
    </>
  )
}

/** Paso 1: elegir la sucursal que despacha y adjuntar la OC (fotos o PDF). */
export function NuevoPedido() {
  const navegar = useNavigate()
  const queryClient = useQueryClient()
  const { data: yo } = useYo()
  const ubicaciones = useUbicaciones()
  const sucursales = (ubicaciones.data ?? []).filter((u) => u.tipo === 'SUCURSAL')
  const predeterminada =
    sucursales.find((s) => s.id === yo?.ubicacion_predeterminada_id)?.id ??
    sucursales.find((s) => yo?.ubicaciones.some((u) => u.id === s.id))?.id ??
    (sucursales.length === 1 ? sucursales[0].id : '')
  const [elegida, setElegida] = useState<string | null>(null)
  const ubicacion = elegida ?? predeterminada
  const [archivos, setArchivos] = useState<File[]>([])
  const [error, setError] = useState<string | null>(null)
  const [preparando, setPreparando] = useState(false)
  const [progreso, setProgreso] = useState<string | null>(null)

  const enviar = async () => {
    setError(null)
    const sucursal = sucursales.find((s) => s.id === ubicacion)
    if (!sucursal) return setError('Elija la sucursal que despacha el pedido.')
    if (!archivos.length) return setError('Adjunte al menos una foto o PDF de la OC.')
    const envio = nuevoEnvio(sucursal, archivos)
    try {
      // Primero se guarda en el dispositivo: si se corta la señal, no se pierde nada.
      await guardarEnvio(envio)
    } catch {
      // Sin IndexedDB (modo privado): se intenta subir directamente.
    }
    try {
      const pedido = await procesarEnvio(envio, setProgreso)
      await queryClient.invalidateQueries({ queryKey: ['pedidos'] })
      if (pedido) navegar(`/pedidos/${pedido.id}`, { replace: true })
    } catch (e) {
      setProgreso(null)
      if (e instanceof ErrorApi && e.status === 0) {
        navegar('/pedidos', { replace: true })
        return
      }
      setError(mensajeError(e))
    }
  }

  return (
    <>
      <Link to="/pedidos" className="mb-2 inline-flex items-center gap-1 text-sm text-slate-600 hover:text-slate-900">
        <ArrowLeft size={16} /> Pedidos
      </Link>
      <Encabezado titulo="Nuevo pedido" descripcion="Fotografíe la OC (todas sus páginas) o adjunte el PDF. Luego revisará y completará los datos." />
      <div className="max-w-2xl space-y-5">
        <Campo etiqueta="Sucursal que despacha">
          <Selector value={ubicacion} onChange={(e) => setElegida(e.target.value)}>
            <option value="">Elegir…</option>
            {sucursales.map((s) => (
              <option key={s.id} value={s.id}>
                {s.nombre}
              </option>
            ))}
          </Selector>
        </Campo>
        <SelectorArchivos archivos={archivos} onCambio={setArchivos} onError={setError} ocupado={setPreparando} />
        {error && <Aviso>{error}</Aviso>}
        {progreso && <Aviso tipo="exito">{progreso}</Aviso>}
        <p className="text-xs text-slate-500">
          Si no hay señal, la OC queda guardada en este dispositivo y se sube sola al recuperar la conexión.
        </p>
        <Boton className="w-full sm:w-auto" disabled={preparando || !!progreso} onClick={() => void enviar()}>
          {preparando ? 'Preparando fotos…' : progreso ? 'Subiendo…' : 'Crear pedido y revisar'}
        </Boton>
      </div>
    </>
  )
}
