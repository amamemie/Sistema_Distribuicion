import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, ArrowRight, Plus } from 'lucide-react'
import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router'
import { EditorLineas } from '../../components/EditorLineas'
import { nuevaClave, type LineaBase } from '../../lib/lineas'
import { Aviso, Boton, CABECERA_TABLA, Campo, Encabezado, Entrada, Insignia, Modal, Paginador, Selector, Tabla, Tarjeta, Vacio } from '../../components/ui'
import { api, mensajeError } from '../../lib/api'
import { useUbicaciones } from '../../lib/consultas'
import { formatearCantidad, formatearFecha } from '../../lib/formato'
import { usePuede } from '../../lib/sesion'
import type { Pagina, Producto, Transferencia } from '../../lib/tipos'
import { useTranslation } from 'react-i18next'

const TAMANO = 50

export function Transferencias() {
  const { t } = useTranslation()
  const puede = usePuede()
  const [pagina, setPagina] = useState(1)
  const [detalle, setDetalle] = useState<Transferencia | null>(null)
  const transferencias = useQuery({
    queryKey: ['transferencias', pagina],
    queryFn: () => api<Pagina<Transferencia>>('/transferencias', { params: { pagina, tamano: TAMANO } }),
    placeholderData: keepPreviousData,
  })

  return (
    <>
      <Encabezado
        titulo={t("Transferencias")}
        descripcion={t("Movimientos de mercadería entre depósitos y sucursales. Llegan el mismo día.")}
        acciones={
          puede('inventario.transferir') && (
            <Link to="/transferencias/nueva">
              <Boton>
                <Plus size={16} /> {t("Nueva transferencia")}
              </Boton>
            </Link>
          )
        }
      />
      {transferencias.isError && <Aviso>{mensajeError(transferencias.error)}</Aviso>}
      {transferencias.data?.items.length === 0 && <Vacio>{t("No hay transferencias registradas.")}</Vacio>}
      {!!transferencias.data?.items.length && (
        <Tabla>
          <thead className={CABECERA_TABLA}>
            <tr>
              <th>{t('N.º')}</th>
              <th>{t("Fecha")}</th>
              <th>{t("Origen → destino")}</th>
              <th className="hidden md:table-cell">{t("Productos")}</th>
              <th>{t("Estado")}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {transferencias.data.items.map((tr) => (
              <tr key={tr.id}>
                <td>
                  <button className="font-medium text-marca-800 hover:underline" onClick={() => setDetalle(tr)}>
                    #{tr.numero}
                  </button>
                </td>
                <td className="whitespace-nowrap text-slate-600">{formatearFecha(tr.fecha)}</td>
                <td>
                  <span className="inline-flex items-center gap-1">
                    {tr.origen.nombre} <ArrowRight size={14} className="text-slate-400" /> {tr.destino.nombre}
                  </span>
                </td>
                <td className="hidden text-slate-600 md:table-cell">{tr.lineas.length}</td>
                <td>{tr.estado === 'ANULADA' ? <Insignia tono="rojo">{t("Anulada")}</Insignia> : <Insignia tono="verde">{t("Realizada")}</Insignia>}</td>
              </tr>
            ))}
          </tbody>
        </Tabla>
      )}
      <Paginador pagina={pagina} total={transferencias.data?.total ?? 0} tamano={TAMANO} onCambio={setPagina} />
      {detalle && <DetalleTransferencia transferencia={detalle} onCerrar={() => setDetalle(null)} />}
    </>
  )
}

function DetalleTransferencia({ transferencia: tf, onCerrar }: { transferencia: Transferencia; onCerrar: () => void }) {
  const { t } = useTranslation()
  const puede = usePuede()
  const queryClient = useQueryClient()
  const [motivo, setMotivo] = useState('')
  const anular = useMutation({
    mutationFn: () => api(`/transferencias/${tf.id}/anular`, { metodo: 'POST', cuerpo: { motivo } }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transferencias'] })
      queryClient.invalidateQueries({ queryKey: ['stock'] })
      onCerrar()
    },
  })
  return (
    <Modal abierto titulo={t("Transferencia #{{v0}}", { v0: tf.numero })} onCerrar={onCerrar}>
      <div className="space-y-4 text-sm">
        <p>
          <strong>{tf.origen.nombre}</strong> → <strong>{tf.destino.nombre}</strong>
          <br />
          <span className="text-slate-500">
            {formatearFecha(tf.fecha)} · {tf.usuario_nombre}
          </span>
        </p>
        {tf.observaciones && <p className="text-slate-600">{tf.observaciones}</p>}
        <ul className="divide-y divide-slate-100 rounded border border-slate-200">
          {tf.lineas.map((l, i) => (
            <li key={i} className="flex justify-between gap-2 px-3 py-2">
              <span>{l.producto_nombre}</span>
              <span className="text-right whitespace-nowrap">
                {formatearCantidad(l.cantidad)} {l.presentacion_nombre}
                {Number(l.factor) !== 1 && (
                  <span className="block text-xs text-slate-500">
                    {formatearCantidad(l.cantidad_base)} {l.unidad_base}
                  </span>
                )}
              </span>
            </li>
          ))}
        </ul>
        {tf.estado === 'ANULADA' && <Aviso>{t("Anulada:")} {tf.anulacion_motivo}</Aviso>}
        {tf.estado === 'REALIZADA' && puede('inventario.transferir') && (
          <form
            className="space-y-2 border-t border-slate-200 pt-4"
            onSubmit={(e) => {
              e.preventDefault()
              anular.mutate()
            }}
          >
            {anular.isError && <Aviso>{mensajeError(anular.error)}</Aviso>}
            <Campo etiqueta={t("Anular (devuelve la mercadería al origen)")}>
              <Entrada placeholder={t("Motivo")} required minLength={5} value={motivo} onChange={(e) => setMotivo(e.target.value)} />
            </Campo>
            <Boton type="submit" variante="peligro" disabled={anular.isPending}>
              {t("Anular transferencia")}
            </Boton>
          </form>
        )}
      </div>
    </Modal>
  )
}

const lineaVacia = (): LineaBase => ({ clave: nuevaClave(), producto: null, presentacion_id: '', cantidad: '' })

/** Datos para precargar la transferencia (desde un pedido sin stock o una sugerencia de reposición). */
interface Precarga {
  origen?: string
  destino?: string
  lineas?: { producto: Producto; cantidad: string; presentacion_id?: string }[]
}

export function NuevaTransferencia() {
  const { t } = useTranslation()
  const navegar = useNavigate()
  const queryClient = useQueryClient()
  const ubicaciones = useUbicaciones()
  const precarga = (useLocation().state as Precarga | null) ?? {}
  const desdePedido = !!precarga.lineas?.length
  const depositos = (ubicaciones.data ?? []).filter((u) => u.tipo === 'DEPOSITO')
  const [origenElegido, setOrigen] = useState<string | null>(null)
  // Desde un pedido, por defecto sale del único depósito (si hay uno solo).
  const origen = origenElegido ?? precarga.origen ?? (desdePedido && depositos.length === 1 ? depositos[0].id : '')
  const [destino, setDestino] = useState(precarga.destino ?? '')
  const [observaciones, setObservaciones] = useState('')
  const [lineas, setLineas] = useState<LineaBase[]>(() =>
    desdePedido
      ? precarga.lineas!.map((l) => ({ clave: nuevaClave(), producto: l.producto, presentacion_id: l.presentacion_id ?? '', cantidad: l.cantidad }))
      : [lineaVacia()],
  )

  const transferir = useMutation({
    mutationFn: () =>
      api('/transferencias', {
        metodo: 'POST',
        cuerpo: {
          origen_id: origen,
          destino_id: destino,
          observaciones: observaciones || null,
          lineas: lineas
            .filter((l) => l.producto)
            .map((l) => ({ producto_id: l.producto!.id, presentacion_id: l.presentacion_id || null, cantidad: l.cantidad })),
        },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transferencias'] })
      queryClient.invalidateQueries({ queryKey: ['stock'] })
      queryClient.invalidateQueries({ queryKey: ['pedido'] })
      // Si vino de un pedido, vuelve a la revisión para confirmarlo.
      if (desdePedido) navegar(-1)
      else navegar('/transferencias', { replace: true })
    },
  })

  return (
    <>
      <Link to="/transferencias" className="mb-2 inline-flex items-center gap-1 text-sm text-slate-600 hover:text-slate-900">
        <ArrowLeft size={16} /> {t("Transferencias")}
      </Link>
      <Encabezado titulo={t("Nueva transferencia")} descripcion={t("Se descuenta del origen y se suma al destino al guardar. No se envían unidades de lotes vencidos.")} />
      <form
        className="space-y-6"
        onSubmit={(e) => {
          e.preventDefault()
          transferir.mutate()
        }}
      >
        <Tarjeta className="grid gap-4 p-4 sm:grid-cols-2">
          <Campo etiqueta={t("Desde")}>
            <Selector required value={origen} onChange={(e) => setOrigen(e.target.value)}>
              <option value="">{t("Elegir…")}</option>
              {ubicaciones.data?.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.nombre}
                </option>
              ))}
            </Selector>
          </Campo>
          <Campo etiqueta={t("Hacia")}>
            <Selector required value={destino} onChange={(e) => setDestino(e.target.value)}>
              <option value="">{t("Elegir…")}</option>
              {ubicaciones.data?.filter((u) => u.id !== origen).map((u) => (
                <option key={u.id} value={u.id}>
                  {u.nombre}
                </option>
              ))}
            </Selector>
          </Campo>
        </Tarjeta>
        <EditorLineas lineas={lineas} onCambio={setLineas} nueva={lineaVacia} />
        <Campo etiqueta={t("Observaciones")}>
          <Entrada value={observaciones} onChange={(e) => setObservaciones(e.target.value)} />
        </Campo>
        {transferir.isError && <Aviso>{mensajeError(transferir.error)}</Aviso>}
        <div className="flex justify-end">
          <Boton type="submit" disabled={transferir.isPending || !lineas.some((l) => l.producto)}>
            {transferir.isPending ? t("Transfiriendo…") : t("Realizar transferencia")}
          </Boton>
        </div>
      </form>
    </>
  )
}
