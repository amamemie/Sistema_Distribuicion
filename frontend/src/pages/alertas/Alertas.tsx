import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertOctagon, AlertTriangle, CheckCheck, CheckCircle2, Info, RefreshCw } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { Aviso, Boton, Encabezado, Paginador, Selector, Tarjeta, Vacio } from '../../components/ui'
import { api, mensajeError } from '../../lib/api'
import { formatearFecha } from '../../lib/formato'
import { usePuedeAlguno } from '../../lib/sesion'
import type { Alerta, Pagina, SeveridadAlerta } from '../../lib/tipos'
import { useTranslation } from 'react-i18next'

const TAMANO = 30

const ESTILO: Record<SeveridadAlerta, { icono: typeof Info; texto: string; clase: string }> = {
  CRITICA: { icono: AlertOctagon, texto: 'Crítica', clase: 'border-l-red-600 text-red-700' },
  AVISO: { icono: AlertTriangle, texto: 'Aviso', clase: 'border-l-amber-500 text-amber-700' },
  INFO: { icono: Info, texto: 'Información', clase: 'border-l-slate-400 text-slate-600' },
}

const TIPOS: Record<string, string> = {
  quiebre: 'Sin stock',
  quiebre_global: 'Agotado en toda la empresa',
  stock_bajo: 'Stock bajo',
  sobre_stock: 'Sobre-stock',
  pedido_sin_stock: 'Pedidos sin stock',
  lote_vencido: 'Lote vencido',
  lote_por_vencer: 'Lote por vencer',
  sin_movimiento: 'Sin movimiento',
  oc_duplicada: 'Documento repetido',
  margen_negativo: 'Margen negativo',
  margen_bajo: 'Margen bajo',
  precio_distinto: 'Precio distinto',
  conteo_diferencia: 'Diferencia en conteo',
  anomalia_pedido: 'Pedido inusual',
  anomalia_compra: 'Compra inusual',
  anomalia_merma: 'Merma inusual',
  cobro_vencido: 'Cobro vencido',
  pago_proveedor: 'Pago a proveedor',
}

/** Centro de notificaciones: alertas automáticas visibles para el usuario. */
export function Alertas() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const puedeAlguno = usePuedeAlguno()
  const [estado, setEstado] = useState<'ACTIVA' | 'RESUELTA'>('ACTIVA')
  const [severidad, setSeveridad] = useState('')
  const [tipo, setTipo] = useState('')
  const [pagina, setPagina] = useState(1)
  const alertas = useQuery({
    queryKey: ['alertas', estado, severidad, tipo, pagina],
    queryFn: () => api<Pagina<Alerta>>('/alertas', { params: { estado, severidad, tipo, pagina, tamano: TAMANO } }),
    placeholderData: keepPreviousData,
    refetchInterval: 60_000,
  })
  const refrescar = () => void queryClient.invalidateQueries({ queryKey: ['alertas'] })
  const leer = useMutation({
    mutationFn: (ids: string[] | null) => api('/alertas/leidas', { metodo: 'POST', cuerpo: { ids } }),
    onSuccess: refrescar,
  })
  const atender = useMutation({
    mutationFn: (id: string) => api(`/alertas/${id}/atender`, { metodo: 'POST' }),
    onSuccess: refrescar,
  })
  const revisar = useMutation({
    mutationFn: () => api('/alertas/evaluar', { metodo: 'POST' }),
    onSuccess: refrescar,
  })
  const hayNoLeidas = alertas.data?.items.some((a) => !a.leida && a.estado === 'ACTIVA')

  return (
    <>
      <Encabezado
        titulo={t("Alertas")}
        descripcion={t("Avisos automáticos del sistema. Se revisan solos cada 10 minutos; los de stock se cierran solos al corregirse.")}
        acciones={
          <div className="flex flex-wrap gap-2">
            {puedeAlguno(['inventario.ver', 'configuracion.gestionar']) && (
              <Boton variante="secundario" disabled={revisar.isPending} onClick={() => revisar.mutate()}>
                <RefreshCw size={16} className={revisar.isPending ? 'animate-spin' : ''} /> {t("Revisar ahora")}
              </Boton>
            )}
            <Boton variante="secundario" disabled={!hayNoLeidas || leer.isPending} onClick={() => leer.mutate(null)}>
              <CheckCheck size={16} /> {t("Marcar todas como leídas")}
            </Boton>
          </div>
        }
      />

      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        <Selector aria-label={t("Estado")} value={estado} onChange={(e) => (setEstado(e.target.value as 'ACTIVA' | 'RESUELTA'), setPagina(1))}>
          <option value="ACTIVA">{t("Activas")}</option>
          <option value="RESUELTA">{t("Resueltas o atendidas")}</option>
        </Selector>
        <Selector aria-label={t("Gravedad")} value={severidad} onChange={(e) => (setSeveridad(e.target.value), setPagina(1))}>
          <option value="">{t("Todas las gravedades")}</option>
          <option value="CRITICA">{t("Críticas")}</option>
          <option value="AVISO">{t("Avisos")}</option>
          <option value="INFO">{t("Información")}</option>
        </Selector>
        <Selector aria-label={t("Tipo")} value={tipo} onChange={(e) => (setTipo(e.target.value), setPagina(1))}>
          <option value="">{t("Todos los tipos")}</option>
          {Object.entries(TIPOS).map(([valor, texto]) => (
            <option key={valor} value={valor}>
              {texto}
            </option>
          ))}
        </Selector>
      </div>

      {[alertas, leer, atender, revisar].map((m, i) => m.isError && <Aviso key={i}>{mensajeError(m.error)}</Aviso>)}
      {revisar.isSuccess && <Aviso tipo="exito">{t("Revisión terminada.")}</Aviso>}

      {alertas.data && alertas.data.items.length === 0 ? (
        <Vacio>
          <CheckCircle2 className="mx-auto mb-2 text-emerald-600" />
          {estado === 'ACTIVA' ? t("No hay alertas activas. Todo en orden.") : t("No hay alertas resueltas con estos filtros.")}
        </Vacio>
      ) : (
        <ul className="space-y-2">
          {alertas.data?.items.map((a) => {
            const e = ESTILO[a.severidad]
            return (
              <li key={a.id}>
                <Tarjeta className={`border-l-4 p-4 ${e.clase.split(' ')[0]} ${a.leida || a.estado === 'RESUELTA' ? '' : 'bg-marca-50/40'}`}>
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="min-w-0 space-y-1">
                      <p className="flex flex-wrap items-center gap-2 text-xs">
                        <span className={`inline-flex items-center gap-1 font-semibold ${e.clase.split(' ').slice(1).join(' ')}`}>
                          <e.icono size={14} aria-hidden /> {t(e.texto)}
                        </span>
                        <span className="text-slate-500">{t(TIPOS[a.tipo] ?? a.tipo)}</span>
                        {!a.leida && a.estado === 'ACTIVA' && <span className="rounded bg-marca-600 px-1.5 text-[10px] font-semibold text-white">{t("NUEVA")}</span>}
                      </p>
                      <p className="font-medium text-slate-900">{a.titulo}</p>
                      <p className="text-sm text-slate-700">{a.mensaje}</p>
                      <p className="text-xs text-slate-500">
                        {formatearFecha(a.creada_at)}
                        {a.estado === 'RESUELTA' &&
                          t(" · {{v0}} el {{v1}}", { v0: a.resuelta_por ? `atendida por ${a.resuelta_por}` : 'resuelta sola', v1: formatearFecha(a.resuelta_at) })}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {a.enlace && (
                        <Link
                          to={a.enlace}
                          onClick={() => !a.leida && leer.mutate([a.id])}
                          className="inline-flex min-h-9 items-center rounded-md border border-slate-300 bg-white px-3 text-sm font-medium hover:bg-slate-50"
                        >
                          {t("Ver")}
                        </Link>
                      )}
                      {a.estado === 'ACTIVA' && !a.auto_resolver && (
                        <Boton variante="secundario" className="min-h-9" disabled={atender.isPending} onClick={() => atender.mutate(a.id)}>
                          {t("Marcar atendida")}
                        </Boton>
                      )}
                      {a.estado === 'ACTIVA' && a.auto_resolver && !a.leida && (
                        <Boton variante="fantasma" className="min-h-9" onClick={() => leer.mutate([a.id])}>
                          {t("Marcar leída")}
                        </Boton>
                      )}
                    </div>
                  </div>
                </Tarjeta>
              </li>
            )
          })}
        </ul>
      )}
      {alertas.data && <Paginador pagina={pagina} total={alertas.data.total} tamano={TAMANO} onCambio={setPagina} />}
    </>
  )
}
