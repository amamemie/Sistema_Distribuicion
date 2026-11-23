import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, CloudOff, FileUp, PencilLine, Plus, RefreshCw, Search, Trash2 } from 'lucide-react'
import { useCallback, useState, type ReactNode } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { SelectorArchivos } from '../../components/pedidos/SelectorArchivos'
import { Aviso, Boton, CABECERA_TABLA, Campo, Encabezado, Entrada, Insignia, Paginador, Selector, Tabla, Tarjeta, Vacio } from '../../components/ui'
import { api, ErrorApi, mensajeError } from '../../lib/api'
import { guardarEnvio, nuevoEnvio, procesarEnvio, useColaSubida } from '../../lib/colaSubida'
import { useCadenas, useUbicaciones } from '../../lib/consultas'
import { formatearBs, formatearDia, formatearFecha, formatearPorcentaje } from '../../lib/formato'
import { usePuede, useYo } from '../../lib/sesion'
import { NOMBRE_ESTADO_PEDIDO, type EstadoPedido, type Pagina, type PedidoDetalle, type PedidoResumen } from '../../lib/tipos'
import { useTranslation } from 'react-i18next'

const TAMANO = 30

const TONO_ESTADO: Record<EstadoPedido, 'gris' | 'azul' | 'ambar' | 'verde' | 'rojo'> = {
  BORRADOR: 'gris',
  CONFIRMADO: 'azul',
  ALISTADO: 'ambar',
  ENTREGADO: 'verde',
  ANULADO: 'rojo',
}

export function InsigniaEstado({ estado }: { estado: EstadoPedido }) {
  const { t } = useTranslation()
  return <Insignia tono={TONO_ESTADO[estado]}>{t(NOMBRE_ESTADO_PEDIDO[estado])}</Insignia>
}

const ESTADOS: (EstadoPedido | '')[] = ['', 'BORRADOR', 'CONFIRMADO', 'ALISTADO', 'ENTREGADO', 'ANULADO']

export function Pedidos() {
  const { t } = useTranslation()
  const puede = usePuede()
  const queryClient = useQueryClient()
  const cadenas = useCadenas()
  const [params] = useSearchParams()
  const [estado, setEstado] = useState<EstadoPedido | ''>(() => {
    const inicial = params.get('estado') as EstadoPedido | null
    return inicial && ESTADOS.includes(inicial) ? inicial : ''
  })
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
        titulo={t("Pedidos")}
        descripcion={t("Órdenes de compra de los supermercados: revisión, reserva, alistado y entrega.")}
        acciones={
          puede('pedidos.escanear') && (
            <Link to="/pedidos/nuevo">
              <Boton>
                <Plus size={16} /> {t("Nuevo pedido")}
              </Boton>
            </Link>
          )
        }
      />

      {cola.pendientes.length > 0 && (
        <Tarjeta className="mb-4 border-amber-300 bg-amber-50 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="flex items-center gap-2 text-sm font-medium text-amber-900">
              <CloudOff size={18} /> {cola.pendientes.length} {t("documento(s) guardado(s) en este dispositivo, pendientes de subir")}
            </p>
            <Boton variante="secundario" disabled={cola.subiendo} onClick={() => void cola.reintentar()}>
              <RefreshCw size={16} className={cola.subiendo ? 'animate-spin' : ''} /> {cola.subiendo ? t("Subiendo…") : t("Subir ahora")}
            </Boton>
          </div>
          <ul className="mt-2 space-y-1 text-sm text-amber-900">
            {cola.pendientes.map((e) => (
              <li key={e.id} className="flex items-center justify-between gap-2">
                <span>
                  {e.ubicacion_nombre} · {e.archivos.length} {t("archivo(s) ·")} {formatearFecha(new Date(e.creado).toISOString())}
                  {e.error && <span className="block text-xs text-red-700">{t("Último intento:")} {e.error}</span>}
                </span>
                <Boton
                  variante="fantasma"
                  className="min-h-8 px-2 text-red-600"
                  aria-label={t("Descartar")}
                  onClick={() => {
                    if (confirm(t('¿Descartar estas fotos? No se podrán recuperar.'))) void cola.descartar(e.id)
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
        <Campo etiqueta={t("Buscar")}>
          <div className="relative">
            <Search size={16} className="pointer-events-none absolute top-3 left-3 text-slate-400" />
            <Entrada
              className="pl-9"
              placeholder={t("N.º de OC o de pedido")}
              value={buscar}
              onChange={(e) => {
                setBuscar(e.target.value)
                setPagina(1)
              }}
            />
          </div>
        </Campo>
        <Campo etiqueta={t("Estado")}>
          <Selector
            value={estado}
            onChange={(e) => {
              setEstado(e.target.value as EstadoPedido | '')
              setPagina(1)
            }}
          >
            {ESTADOS.map((e) => (
              <option key={e} value={e}>
                {e ? t(NOMBRE_ESTADO_PEDIDO[e]) : t("Todos")}
              </option>
            ))}
          </Selector>
        </Campo>
        <Campo etiqueta={t("Cadena")}>
          <Selector
            value={cadena}
            onChange={(e) => {
              setCadena(e.target.value)
              setPagina(1)
            }}
          >
            <option value="">{t("Todas")}</option>
            {cadenas.data?.map((c) => (
              <option key={c.id} value={c.id}>
                {c.nombre}
              </option>
            ))}
          </Selector>
        </Campo>
      </div>

      {pedidos.isError && <Aviso>{mensajeError(pedidos.error)}</Aviso>}
      {pedidos.data?.items.length === 0 && <Vacio>{t("No hay pedidos con esos filtros.")}</Vacio>}
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
                        #{p.numero} {p.numero_oc && <span className="text-slate-500">{t("· OC")} {p.numero_oc}</span>}
                      </p>
                      <p className="truncate text-sm text-slate-600">
                        {p.cadena ? `${p.cadena.nombre} · ${p.sucursal_cliente?.nombre ?? '—'}` : t("Sin datos del cliente")}
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
                  <th>{t('N.º')}</th>
                  <th>{t('OC')}</th>
                  <th>{t("Cliente")}</th>
                  <th>{t("Despacha")}</th>
                  <th>{t("Fecha")}</th>
                  <th className="text-right">{t("Total")}</th>
                  {verGanancia && <th className="text-right">{t("Margen")}</th>}
                  <th>{t("Estado")}</th>
                  <th>{t("Responsable")}</th>
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

/** Paso 1: elegir la sucursal que despacha y adjuntar la nota de recepción o cargar a mano. */
export function NuevoPedido() {
  const { t } = useTranslation()
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
  const [modo, setModo] = useState<'documento' | 'manual'>('documento')

  const enviar = async () => {
    setError(null)
    const sucursal = sucursales.find((s) => s.id === ubicacion)
    if (!sucursal) return setError(t('Elija la sucursal que despacha el pedido.'))
    if (modo === 'manual') {
      // D-20: pedido sin documento; los datos se cargan a mano en la revisión.
      setProgreso(t('Creando el pedido…'))
      try {
        const pedido = await api<PedidoDetalle>('/pedidos', { metodo: 'POST', cuerpo: { ubicacion_id: sucursal.id } })
        await queryClient.invalidateQueries({ queryKey: ['pedidos'] })
        navegar(`/pedidos/${pedido.id}`, { replace: true })
      } catch (e) {
        setProgreso(null)
        setError(mensajeError(e))
      }
      return
    }
    if (!archivos.length) return setError(t('Adjunte al menos una foto o PDF de la nota de recepción.'))
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
        <ArrowLeft size={16} /> {t("Pedidos")}
      </Link>
      <Encabezado titulo={t("Nuevo pedido")} descripcion={t("Adjunte la nota de recepción (PDF o fotos) para que se lea sola, o cargue el pedido a mano.")} />
      <div className="max-w-2xl space-y-5">
        <Campo etiqueta={t("Sucursal que despacha")}>
          <Selector value={ubicacion} onChange={(e) => setElegida(e.target.value)}>
            <option value="">{t("Elegir…")}</option>
            {sucursales.map((s) => (
              <option key={s.id} value={s.id}>
                {s.nombre}
              </option>
            ))}
          </Selector>
        </Campo>
        <div role="radiogroup" aria-label={t("Cómo cargar el pedido")} className="grid gap-3 sm:grid-cols-2">
          <OpcionModo activo={modo === 'documento'} onClick={() => setModo('documento')} icono={<FileUp size={18} />} titulo={t("Subir nota de recepción")}>
            {t("PDF, foto o galería. El sistema lee los datos y usted los revisa.")}
          </OpcionModo>
          <OpcionModo activo={modo === 'manual'} onClick={() => setModo('manual')} icono={<PencilLine size={18} />} titulo={t("Cargar a mano")}>
            {t("Usted escribe la cadena, la sucursal, la fecha y los productos.")}
          </OpcionModo>
        </div>
        {modo === 'documento' && (
          <>
            <SelectorArchivos archivos={archivos} onCambio={setArchivos} onError={setError} ocupado={setPreparando} />
            <p className="text-xs text-slate-500">
              {t("Si no hay señal, el documento queda guardado en este dispositivo y se sube solo al recuperar la conexión.")}
            </p>
          </>
        )}
        {error && <Aviso>{error}</Aviso>}
        {progreso && <Aviso tipo="exito">{progreso}</Aviso>}
        <Boton className="w-full sm:w-auto" disabled={preparando || !!progreso} onClick={() => void enviar()}>
          {preparando ? t("Preparando fotos…") : progreso ? t("Un momento…") : modo === 'manual' ? t("Crear pedido y cargar datos") : t("Crear pedido y revisar")}
        </Boton>
      </div>
    </>
  )
}

function OpcionModo({
  activo,
  onClick,
  icono,
  titulo,
  children,
}: {
  activo: boolean
  onClick: () => void
  icono: ReactNode
  titulo: string
  children: ReactNode
}) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={activo}
      onClick={onClick}
      className={`rounded-lg border p-3 text-left transition ${
        activo ? 'border-marca-600 bg-marca-50 ring-2 ring-marca-100' : 'border-slate-300 bg-white hover:bg-slate-50'
      }`}
    >
      <span className="flex items-center gap-2 font-medium text-slate-900">
        {icono} {titulo}
      </span>
      <span className="mt-1 block text-xs text-slate-600">{children}</span>
    </button>
  )
}
