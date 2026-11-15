import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, ArrowLeftRight, CheckCircle2, FilePlus2, Loader2, Plus, RefreshCw, ScanText, Sparkles, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { SelectorArchivos } from '../../components/pedidos/SelectorArchivos'
import { VisorDocumentos } from '../../components/pedidos/VisorDocumentos'
import { SelectorProducto } from '../../components/SelectorProducto'
import { Aviso, Boton, Campo, Entrada, Modal, Selector, Tarjeta } from '../../components/ui'
import { api, mensajeError } from '../../lib/api'
import { useCadenas, useUbicaciones } from '../../lib/consultas'
import { formatearBs, formatearCantidad, formatearCosto, formatearDia, hoyLaPaz } from '../../lib/formato'
import { nuevaClave } from '../../lib/lineas'
import { usePuede } from '../../lib/sesion'
import type { LecturaOC, PedidoDetalle, PedidoLinea, Producto, Sugerencia, Validacion } from '../../lib/tipos'
import { diferenciaLinea, numeroONulo, sumaLineas } from './calculos'

interface LineaForm {
  clave: string
  id: string | null // id en el servidor (para ubicar sus validaciones)
  codigo: string
  descripcion: string
  producto: Producto | null
  sugerido: boolean
  cantidad_oc: string
  precio_oc: string
  total_linea_oc: string
  confirmada: string
}

interface Formulario {
  ubicacion_id: string
  cadena_id: string
  sucursal_cliente_id: string
  numero_oc: string
  fecha_oc: string
  fecha_entrega: string
  emisor: string
  total_oc: string
  observaciones: string
  lineas: LineaForm[]
}

const texto = (v: string | null | undefined) => v ?? ''
const sinCeros = (v: string | null | undefined) => (v === null || v === undefined ? '' : String(Number(v)))

function desdePedido(p: PedidoDetalle): Formulario {
  return {
    ubicacion_id: p.ubicacion.id,
    cadena_id: texto(p.cadena?.id),
    sucursal_cliente_id: texto(p.sucursal_cliente?.id),
    numero_oc: texto(p.numero_oc),
    fecha_oc: texto(p.fecha_oc),
    fecha_entrega: texto(p.fecha_entrega),
    emisor: texto(p.emisor),
    total_oc: sinCeros(p.total_oc),
    observaciones: texto(p.observaciones),
    lineas: p.detalle_lineas.map((l) => ({
      clave: nuevaClave(),
      id: l.id,
      codigo: texto(l.codigo_cliente),
      descripcion: l.descripcion_cliente,
      producto: l.producto,
      sugerido: false,
      cantidad_oc: sinCeros(l.cantidad_oc),
      precio_oc: sinCeros(l.precio_oc),
      total_linea_oc: sinCeros(l.total_linea_oc),
      confirmada: sinCeros(l.cantidad_confirmada),
    })),
  }
}

const lineaVacia = (): LineaForm => ({
  clave: nuevaClave(),
  id: null,
  codigo: '',
  descripcion: '',
  producto: null,
  sugerido: false,
  cantidad_oc: '',
  precio_oc: '',
  total_linea_oc: '',
  confirmada: '',
})

function aCuerpo(f: Formulario) {
  return {
    ubicacion_id: f.ubicacion_id,
    cadena_id: f.cadena_id || null,
    sucursal_cliente_id: f.sucursal_cliente_id || null,
    numero_oc: f.numero_oc.trim() || null,
    fecha_oc: f.fecha_oc || null,
    fecha_entrega: f.fecha_entrega || null,
    emisor: f.emisor.trim() || null,
    total_oc: numeroONulo(f.total_oc),
    observaciones: f.observaciones.trim() || null,
    lineas: f.lineas
      .filter((l) => l.descripcion.trim() || l.producto || l.cantidad_oc)
      .map((l) => ({
        codigo_cliente: l.codigo.trim() || null,
        descripcion_cliente: l.descripcion.trim() || l.producto?.nombre || 'Sin descripción',
        producto_id: l.producto?.id ?? null,
        cantidad_oc: numeroONulo(l.cantidad_oc),
        precio_oc: numeroONulo(l.precio_oc) ?? '0',
        total_linea_oc: numeroONulo(l.total_linea_oc),
        cantidad_confirmada: numeroONulo(l.confirmada),
      })),
  }
}

/** Revisión de la OC en BORRADOR: documento al lado, todo editable, validaciones y confirmación. */
export function RevisionPedido({ pedido, puedeAnular, onAnular }: { pedido: PedidoDetalle; puedeAnular: boolean; onAnular: () => void }) {
  const puede = usePuede()
  const queryClient = useQueryClient()
  const cadenas = useCadenas()
  const ubicaciones = useUbicaciones()
  const sucursales = (ubicaciones.data ?? []).filter((u) => u.tipo === 'SUCURSAL')
  const [form, setForm] = useState<Formulario>(() => desdePedido(pedido))
  const [sucio, setSucio] = useState(false)
  const [agregando, setAgregando] = useState(false)
  const cadena = cadenas.data?.find((c) => c.id === form.cadena_id)

  const cambiar = (cambios: Partial<Formulario>) => {
    setForm((f) => ({ ...f, ...cambios }))
    setSucio(true)
  }
  const cambiarLinea = (clave: string, cambios: Partial<LineaForm>) => {
    setForm((f) => ({ ...f, lineas: f.lineas.map((l) => (l.clave === clave ? { ...l, ...cambios } : l)) }))
    setSucio(true)
  }

  const aplicar = (nuevo: PedidoDetalle) => {
    queryClient.setQueryData(['pedido', pedido.id], nuevo)
    void queryClient.invalidateQueries({ queryKey: ['pedidos'] })
    setForm(desdePedido(nuevo))
    setSucio(false)
  }

  const guardar = useMutation({
    mutationFn: () => api<PedidoDetalle>(`/pedidos/${pedido.id}`, { metodo: 'PUT', cuerpo: aCuerpo(form) }),
    onSuccess: aplicar,
  })
  const confirmar = useMutation({
    mutationFn: async () => {
      if (sucio) aplicar(await api<PedidoDetalle>(`/pedidos/${pedido.id}`, { metodo: 'PUT', cuerpo: aCuerpo(form) }))
      return api<PedidoDetalle>(`/pedidos/${pedido.id}/confirmar`, { metodo: 'POST' })
    },
    onSuccess: (nuevo) => {
      queryClient.setQueryData(['pedido', pedido.id], nuevo)
      void queryClient.invalidateQueries({ queryKey: ['pedidos'] })
      void queryClient.invalidateQueries({ queryKey: ['stock'] })
    },
  })
  const leer = useMutation({
    mutationFn: () => api<PedidoDetalle>(`/pedidos/${pedido.id}/leer`, { metodo: 'POST' }),
    onSuccess: (nuevo) => queryClient.setQueryData(['pedido', pedido.id], nuevo),
  })
  const leyendo = ['PENDIENTE', 'PROCESANDO'].includes(pedido.lectura?.estado ?? '')
  const quitarDocumento = useMutation({
    mutationFn: (archivoId: string) => api<PedidoDetalle>(`/pedidos/${pedido.id}/documentos/${archivoId}`, { metodo: 'DELETE' }),
    onSuccess: (nuevo) => queryClient.setQueryData(['pedido', pedido.id], nuevo),
  })

  const servidor = new Map(pedido.detalle_lineas.map((l) => [l.id, l]))
  const porLinea = new Map<string, Validacion[]>()
  for (const v of pedido.validaciones) if (v.linea_id) porLinea.set(v.linea_id, [...(porLinea.get(v.linea_id) ?? []), v])
  const generales = pedido.validaciones.filter((v) => !v.linea_id)
  const errores = pedido.validaciones.filter((v) => v.nivel === 'error')
  const suma = sumaLineas(form.lineas)
  const totalOc = numeroONulo(form.total_oc)
  const diferenciaTotal = totalOc !== null && form.lineas.length > 0 && Math.abs(suma - Number(totalOc)) > 0.01

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
      <div className="space-y-2 lg:sticky lg:top-4 lg:self-start">
        <VisorDocumentos pedidoId={pedido.id} documentos={pedido.detalle_documentos} onQuitar={(id) => quitarDocumento.mutate(id)} />
        <Boton variante="secundario" className="w-full" onClick={() => setAgregando(true)}>
          <FilePlus2 size={16} /> Agregar páginas
        </Boton>
        {quitarDocumento.isError && <Aviso>{mensajeError(quitarDocumento.error)}</Aviso>}
      </div>

      <form
        className="space-y-5"
        onSubmit={(e) => {
          e.preventDefault()
          guardar.mutate()
        }}
      >
        <EstadoLectura
          lectura={pedido.lectura}
          avisos={pedido.confianza?.avisos ?? []}
          ocupado={leer.isPending}
          onLeer={() => {
            if (!form.lineas.length || confirm('Se volverá a leer la OC y se reemplazarán los datos cargados. ¿Continuar?')) leer.mutate()
          }}
        />
        {leer.isError && <Aviso>{mensajeError(leer.error)}</Aviso>}
        <Tarjeta className={`grid gap-4 p-4 sm:grid-cols-2 ${leyendo ? 'pointer-events-none opacity-50' : ''}`}>
          <Campo etiqueta="Cadena">
            <Selector value={form.cadena_id} onChange={(e) => cambiar({ cadena_id: e.target.value, sucursal_cliente_id: '' })}>
              <option value="">Elegir…</option>
              {cadenas.data
                ?.filter((c) => c.activo || c.id === form.cadena_id)
                .map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.nombre}
                  </option>
                ))}
            </Selector>
          </Campo>
          <Campo
            etiqueta="Sucursal de supermercado"
            ayuda={!form.sucursal_cliente_id && pedido.confianza?.destino_texto ? `La OC dice: «${pedido.confianza.destino_texto}»` : undefined}
          >
            <Selector value={form.sucursal_cliente_id} disabled={!cadena} onChange={(e) => cambiar({ sucursal_cliente_id: e.target.value })}>
              <option value="">{cadena ? 'Elegir…' : 'Primero la cadena'}</option>
              {cadena?.sucursales
                .filter((s) => s.activo || s.id === form.sucursal_cliente_id)
                .map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.nombre}
                  </option>
                ))}
            </Selector>
          </Campo>
          <Campo etiqueta="N.º de OC">
            <Entrada className={claseDudosa(pedido.confianza?.numero_oc)} value={form.numero_oc} onChange={(e) => cambiar({ numero_oc: e.target.value })} />
          </Campo>
          <Campo etiqueta="Fecha de la OC">
            <Entrada type="date" className={claseDudosa(pedido.confianza?.fecha_oc)} max={hoyLaPaz()} value={form.fecha_oc} onChange={(e) => cambiar({ fecha_oc: e.target.value })} />
          </Campo>
          <Campo etiqueta="Total de la OC (Bs)" ayuda={`Suma de las líneas: ${formatearBs(suma)}`} error={diferenciaTotal ? `No coincide con la suma de las líneas (${formatearBs(suma)}).` : undefined}>
            <Entrada inputMode="decimal" className={claseDudosa(pedido.confianza?.total)} value={form.total_oc} onChange={(e) => cambiar({ total_oc: e.target.value.replace(',', '.') })} />
          </Campo>
          <Campo etiqueta="Sucursal que despacha">
            <Selector value={form.ubicacion_id} onChange={(e) => cambiar({ ubicacion_id: e.target.value })}>
              {sucursales.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.nombre}
                </option>
              ))}
            </Selector>
          </Campo>
          <Campo etiqueta="Emitida por (opcional)">
            <Entrada value={form.emisor} onChange={(e) => cambiar({ emisor: e.target.value })} />
          </Campo>
          <Campo etiqueta="Fecha de entrega (opcional)">
            <Entrada type="date" value={form.fecha_entrega} onChange={(e) => cambiar({ fecha_entrega: e.target.value })} />
          </Campo>
        </Tarjeta>

        <div className="space-y-3">
          <h2 className="text-sm font-semibold text-slate-700 uppercase">Líneas de la OC</h2>
          {form.lineas.map((l, i) => (
            <LineaRevision
              key={l.clave}
              numero={i + 1}
              linea={l}
              servidor={l.id ? servidor.get(l.id) : undefined}
              validaciones={l.id ? porLinea.get(l.id) ?? [] : []}
              cadenaId={form.cadena_id}
              ubicacionId={form.ubicacion_id}
              sucio={sucio}
              puedeTransferir={puede('inventario.transferir')}
              onCambio={(c) => cambiarLinea(l.clave, c)}
              onQuitar={() => cambiar({ lineas: form.lineas.filter((x) => x.clave !== l.clave) })}
            />
          ))}
          <Boton variante="secundario" onClick={() => cambiar({ lineas: [...form.lineas, lineaVacia()] })}>
            <Plus size={16} /> Agregar línea
          </Boton>
        </div>

        <Campo etiqueta="Observaciones">
          <Entrada value={form.observaciones} onChange={(e) => cambiar({ observaciones: e.target.value })} />
        </Campo>

        {sucio ? (
          <Aviso>Hay cambios sin guardar. Guarde para ver las validaciones actualizadas.</Aviso>
        ) : (
          <PanelValidaciones generales={generales} errores={errores.length} total={pedido.validaciones.length} />
        )}
        {guardar.isError && <Aviso>{mensajeError(guardar.error)}</Aviso>}
        {confirmar.isError && <Aviso>{mensajeError(confirmar.error)}</Aviso>}

        <div className="sticky bottom-0 -mx-4 flex flex-wrap justify-end gap-2 border-t border-slate-200 bg-white/95 px-4 py-3 backdrop-blur sm:static sm:mx-0 sm:border-0 sm:bg-transparent sm:p-0">
          {puedeAnular && (
            <Boton variante="fantasma" className="mr-auto text-red-600" onClick={onAnular}>
              Anular
            </Boton>
          )}
          <Boton type="submit" variante="secundario" disabled={guardar.isPending || !sucio}>
            {guardar.isPending ? 'Guardando…' : 'Guardar borrador'}
          </Boton>
          {puede('pedidos.confirmar') && (
            <Boton
              disabled={confirmar.isPending || (!sucio && errores.length > 0)}
              onClick={() => {
                if (confirm('Al confirmar se reserva el stock de la sucursal. ¿Continuar?')) confirmar.mutate()
              }}
            >
              <CheckCircle2 size={16} /> {confirmar.isPending ? 'Confirmando…' : sucio ? 'Guardar y confirmar' : 'Confirmar pedido'}
            </Boton>
          )}
        </div>
      </form>

      <AgregarPaginas pedidoId={pedido.id} abierto={agregando} onCerrar={() => setAgregando(false)} />
    </div>
  )
}

const UMBRAL_DUDOSO = 0.85

/** Resalta en ámbar los campos que la lectura automática leyó con poca seguridad. */
function claseDudosa(confianza: unknown): string {
  return typeof confianza === 'number' && confianza < UMBRAL_DUDOSO ? 'border-amber-400! bg-amber-50! ring-1 ring-amber-300' : ''
}

const NOMBRE_PLANTILLA: Record<string, string> = { hipermaxi: 'formato Hipermaxi', generica: 'lectura genérica (formato sin plantilla)' }

function EstadoLectura({
  lectura,
  avisos,
  ocupado,
  onLeer,
}: {
  lectura: LecturaOC | null
  avisos: string[]
  ocupado: boolean
  onLeer: () => void
}) {
  const boton = (
    <Boton variante="secundario" className="min-h-8 text-xs" disabled={ocupado} onClick={onLeer}>
      <RefreshCw size={14} /> {lectura ? 'Volver a leer' : 'Leer la OC automáticamente'}
    </Boton>
  )
  if (!lectura) return <div className="flex justify-end">{boton}</div>
  if (lectura.estado === 'PENDIENTE' || lectura.estado === 'PROCESANDO') {
    return (
      <div role="status" className="flex items-center gap-2 rounded-md border border-marca-200 bg-marca-50 px-3 py-2 text-sm text-marca-900">
        <Loader2 size={16} className="animate-spin" /> Leyendo la OC automáticamente… suele tardar entre 10 y 30 segundos por página.
      </div>
    )
  }
  if (lectura.estado === 'FALLIDA') {
    return (
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
        <span>{lectura.error ?? 'No se pudo leer la OC.'}</span>
        {boton}
      </div>
    )
  }
  return (
    <div className="space-y-1 rounded-md border border-slate-200 bg-white px-3 py-2 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="inline-flex items-center gap-1.5 text-slate-700">
          <ScanText size={16} className="text-marca-700" />
          {lectura.aplicada ? 'Datos leídos automáticamente' : 'Se leyó la OC, pero el borrador ya tenía datos: no se reemplazaron'} ·{' '}
          {NOMBRE_PLANTILLA[lectura.plantilla ?? ''] ?? lectura.plantilla} · confianza {Math.round(Number(lectura.confianza ?? 0))} %
          {lectura.aritmetica_ok ? ' · las cuentas cuadran' : ' · revise: las cuentas no cuadran'}
        </span>
        {boton}
      </div>
      {lectura.aplicada && <p className="text-xs text-slate-500">Compare con el documento; los campos en ámbar se leyeron con poca seguridad.</p>}
      {avisos.map((a, i) => (
        <p key={i} className="text-xs text-amber-800">
          {a}
        </p>
      ))}
    </div>
  )
}

function PanelValidaciones({ generales, errores, total }: { generales: Validacion[]; errores: number; total: number }) {
  if (total === 0) {
    return (
      <Aviso tipo="exito">
        <span className="inline-flex items-center gap-1">
          <CheckCircle2 size={16} /> Todo cuadra: la OC está lista para confirmar.
        </span>
      </Aviso>
    )
  }
  return (
    <div className="space-y-2">
      {generales.map((v, i) => (
        <MensajeValidacion key={i} v={v} />
      ))}
      <p className="text-xs text-slate-500">
        {errores > 0 ? `${errores} problema(s) impiden confirmar. ` : 'Sin problemas que impidan confirmar. '}
        Los avisos en amarillo conviene revisarlos contra el documento.
      </p>
    </div>
  )
}

function MensajeValidacion({ v }: { v: Validacion }) {
  return (
    <p
      className={`flex items-start gap-1.5 rounded-md px-2.5 py-1.5 text-sm ${
        v.nivel === 'error' ? 'bg-red-50 text-red-800' : 'bg-amber-50 text-amber-900'
      }`}
    >
      <AlertTriangle size={15} className="mt-0.5 shrink-0" /> {v.mensaje}
    </p>
  )
}

function LineaRevision({
  numero,
  linea,
  servidor,
  validaciones,
  cadenaId,
  ubicacionId,
  sucio,
  puedeTransferir,
  onCambio,
  onQuitar,
}: {
  numero: number
  linea: LineaForm
  servidor: PedidoLinea | undefined
  validaciones: Validacion[]
  cadenaId: string
  ubicacionId: string
  sucio: boolean
  puedeTransferir: boolean
  onCambio: (cambios: Partial<LineaForm>) => void
  onQuitar: () => void
}) {
  const diferencia = diferenciaLinea(linea)
  const confirmada = linea.confirmada === '' ? Number(linea.cantidad_oc) || 0 : Number(linea.confirmada)
  const disponible = servidor?.disponible != null ? Number(servidor.disponible) : null
  const faltante = disponible !== null && servidor?.producto?.id === linea.producto?.id ? confirmada - disponible : 0
  const unidad = linea.producto?.unidad_base ?? 'unid.'
  const conError = validaciones.some((v) => v.nivel === 'error')
  const conf = servidor?.confianza ?? null

  return (
    <div className={`rounded-lg border p-3 ${conError && !sucio ? 'border-red-300 bg-red-50/40' : 'border-slate-200 bg-white'}`}>
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs font-semibold text-slate-500 uppercase">Línea {numero}</span>
        <Boton variante="fantasma" className="min-h-8 px-2 text-red-600" onClick={onQuitar} aria-label={`Quitar línea ${numero}`}>
          <Trash2 size={16} />
        </Boton>
      </div>
      <div className="grid gap-3 sm:grid-cols-[8rem_minmax(0,1fr)]">
        <Entrada aria-label="Código en la OC" placeholder="Código" className={claseDudosa(conf?.codigo)} value={linea.codigo} onChange={(e) => onCambio({ codigo: e.target.value })} />
        <Entrada aria-label="Descripción en la OC" placeholder="Descripción como figura en la OC" className={claseDudosa(conf?.descripcion)} value={linea.descripcion} onChange={(e) => onCambio({ descripcion: e.target.value })} />
      </div>
      <div className="mt-3">
        <SelectorProducto valor={linea.producto} onCambio={(producto) => onCambio({ producto, sugerido: false })} />
        {linea.sugerido && linea.producto && (
          <p className="mt-1 inline-flex items-center gap-1 text-xs text-marca-800">
            <Sparkles size={12} /> Emparejado por una equivalencia aprendida. Verifique que sea correcto.
          </p>
        )}
        {!linea.producto && (
          <Sugerencias
            cadenaId={cadenaId}
            codigo={linea.codigo}
            descripcion={linea.descripcion}
            onElegir={(producto, automatico) => onCambio({ producto, sugerido: automatico })}
          />
        )}
      </div>
      <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Campo etiqueta={`Cantidad OC (${unidad})`}>
          <Entrada inputMode="decimal" className={claseDudosa(conf?.cantidad)} value={linea.cantidad_oc} onChange={(e) => onCambio({ cantidad_oc: e.target.value.replace(',', '.') })} />
        </Campo>
        <Campo etiqueta="Precio unitario">
          <Entrada inputMode="decimal" className={claseDudosa(conf?.precio)} value={linea.precio_oc} onChange={(e) => onCambio({ precio_oc: e.target.value.replace(',', '.') })} />
        </Campo>
        <Campo etiqueta="Total línea (OC)">
          <Entrada inputMode="decimal" className={claseDudosa(conf?.total)} value={linea.total_linea_oc} onChange={(e) => onCambio({ total_linea_oc: e.target.value.replace(',', '.') })} />
        </Campo>
        <Campo etiqueta="A confirmar">
          <Entrada inputMode="decimal" placeholder={linea.cantidad_oc || '0'} value={linea.confirmada} onChange={(e) => onCambio({ confirmada: e.target.value.replace(',', '.') })} />
        </Campo>
      </div>
      <div className="mt-2 space-y-1 text-xs text-slate-600">
        {diferencia && <p className="font-medium text-red-700">{diferencia}</p>}
        {servidor && servidor.producto && disponible !== null && servidor.producto.id === linea.producto?.id && (
          <p>
            Disponible en la sucursal: <strong className={faltante > 0 ? 'text-red-700' : 'text-emerald-700'}>{formatearCantidad(disponible)}</strong>
            {servidor.disponible_depositos !== null && <> · en depósitos: {formatearCantidad(servidor.disponible_depositos)}</>}
          </p>
        )}
        {servidor?.precio_anterior && servidor.producto?.id === linea.producto?.id && (
          <p>
            Último precio para esta cadena: {formatearCosto(servidor.precio_anterior)} (pedido #{servidor.precio_anterior_pedido}, {formatearDia(servidor.precio_anterior_fecha)})
          </p>
        )}
      </div>
      {!sucio && validaciones.length > 0 && (
        <div className="mt-2 space-y-1">
          {validaciones.map((v, i) => (
            <MensajeValidacion key={i} v={v} />
          ))}
        </div>
      )}
      {!sucio && faltante > 0 && linea.producto && (
        <div className="mt-2 flex flex-wrap gap-2">
          <Boton variante="secundario" className="min-h-8 text-xs" onClick={() => onCambio({ confirmada: String(Math.max(0, disponible ?? 0)) })}>
            Confirmar solo lo disponible ({formatearCantidad(disponible)})
          </Boton>
          {puedeTransferir && Number(servidor?.disponible_depositos ?? 0) > 0 && (
            <Link
              to="/transferencias/nueva"
              state={{ destino: ubicacionId, lineas: [{ producto: linea.producto, cantidad: String(faltante) }] }}
              className="inline-flex min-h-8 items-center gap-1 rounded-md border border-slate-300 bg-white px-3 text-xs font-medium hover:bg-slate-50"
            >
              <ArrowLeftRight size={14} /> Transferir {formatearCantidad(faltante)} desde el depósito
            </Link>
          )}
        </div>
      )}
    </div>
  )
}

/** Sugiere el producto interno para una línea; si hay una equivalencia aprendida, la aplica sola. */
function Sugerencias({
  cadenaId,
  codigo,
  descripcion,
  onElegir,
}: {
  cadenaId: string
  codigo: string
  descripcion: string
  onElegir: (producto: Producto, automatico: boolean) => void
}) {
  const [consulta, setConsulta] = useState({ codigo: '', descripcion: '' })
  useEffect(() => {
    const t = setTimeout(() => setConsulta({ codigo: codigo.trim(), descripcion: descripcion.trim() }), 400)
    return () => clearTimeout(t)
  }, [codigo, descripcion])
  const sugerencias = useQuery({
    queryKey: ['emparejar', cadenaId, consulta.codigo, consulta.descripcion],
    queryFn: () =>
      api<Sugerencia[]>('/pedidos/emparejar', {
        params: { cadena_id: cadenaId, codigo: consulta.codigo, descripcion: consulta.descripcion },
      }),
    enabled: !!(consulta.codigo || consulta.descripcion.length >= 3),
    staleTime: 60_000,
  })
  const primera = sugerencias.data?.[0]
  useEffect(() => {
    if (primera?.fuente === 'equivalencia') onElegir(primera.producto, true)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [primera?.producto.id, primera?.fuente])

  if (!sugerencias.data?.length) return null
  return (
    <div className="mt-2 flex flex-wrap items-center gap-1.5">
      <span className="text-xs text-slate-500">¿Es…?</span>
      {sugerencias.data.map((s) => (
        <button
          key={s.producto.id}
          type="button"
          onClick={() => onElegir(s.producto, false)}
          className="rounded-full border border-marca-200 bg-marca-50 px-2.5 py-1 text-xs text-marca-900 hover:bg-marca-100"
          title={s.fuente === 'codigo' ? 'Coincide el código' : s.fuente === 'equivalencia' ? 'Usado antes con esta cadena' : 'Nombre parecido'}
        >
          {s.producto.nombre}
        </button>
      ))}
    </div>
  )
}

function AgregarPaginas({ pedidoId, abierto, onCerrar }: { pedidoId: string; abierto: boolean; onCerrar: () => void }) {
  const queryClient = useQueryClient()
  const [archivos, setArchivos] = useState<File[]>([])
  const [error, setError] = useState<string | null>(null)
  const [preparando, setPreparando] = useState(false)
  const subir = useMutation({
    mutationFn: async () => {
      let ultimo: PedidoDetalle | null = null
      for (const archivo of archivos) {
        const datos = new FormData()
        datos.append('archivos', archivo, archivo.name)
        ultimo = await api<PedidoDetalle>(`/pedidos/${pedidoId}/documentos`, { metodo: 'POST', cuerpo: datos })
      }
      return ultimo
    },
    onSuccess: (nuevo) => {
      if (nuevo) queryClient.setQueryData(['pedido', pedidoId], nuevo)
      setArchivos([])
      onCerrar()
    },
  })
  return (
    <Modal abierto={abierto} titulo="Agregar páginas de la OC" onCerrar={onCerrar}>
      <div className="space-y-4">
        <SelectorArchivos archivos={archivos} onCambio={setArchivos} onError={setError} ocupado={setPreparando} />
        {error && <Aviso>{error}</Aviso>}
        {subir.isError && <Aviso>{mensajeError(subir.error)}</Aviso>}
        <div className="flex justify-end">
          <Boton disabled={!archivos.length || preparando || subir.isPending} onClick={() => subir.mutate()}>
            {subir.isPending ? 'Subiendo…' : 'Subir'}
          </Boton>
        </div>
      </div>
    </Modal>
  )
}
