import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeftRight, LineChart, RefreshCw, ShoppingCart } from 'lucide-react'
import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router'
import { Grafico } from '../../components/reportes/Grafico'
import { Aviso, Boton, CABECERA_TABLA, Campo, Encabezado, Entrada, Insignia, Modal, Tabla, Vacio } from '../../components/ui'
import { api, mensajeError } from '../../lib/api'
import { formatearBs, formatearCantidad, formatearDia, hoyLaPaz } from '../../lib/formato'
import { usePuede } from '../../lib/sesion'
import type {
  Confianza,
  FilaReposicion,
  ParametrosAlertas,
  Producto,
  PronosticoProducto,
  SugerenciaCompra,
  SugerenciaTransferencia,
} from '../../lib/tipos'
import type { TFunction } from 'i18next'
import { useTranslation } from 'react-i18next'

type Pestana = 'transferencias' | 'compras' | 'plan' | 'parametros'

export function Reposicion() {
  const { t } = useTranslation()
  const puede = usePuede()
  const pestanas: { clave: Pestana; texto: string; visible: boolean }[] = [
    { clave: 'transferencias', texto: 'Depósito → sucursal', visible: puede('inventario.transferir') },
    { clave: 'compras', texto: 'Proveedor → depósito', visible: puede('compras.registrar') },
    { clave: 'plan', texto: 'Plan completo', visible: true },
    { clave: 'parametros', texto: 'Parámetros', visible: true },
  ]
  const visibles = pestanas.filter((p) => p.visible)
  const [params, setParams] = useSearchParams()
  const actual = visibles.find((p) => p.clave === params.get('tab'))?.clave ?? visibles[0].clave
  const [pronostico, setPronostico] = useState<{ id: string; nombre: string } | null>(null)

  return (
    <>
      <Encabezado
        titulo={t("Reposición")}
        descripcion={t("Qué transferir a cada sucursal y qué comprar al proveedor, según lo que se vende y el stock de hoy.")}
      />
      <nav aria-label={t("Secciones")} className="-mx-4 mb-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
        <ul className="flex min-w-max gap-1 border-b border-slate-200">
          {visibles.map((p) => (
            <li key={p.clave}>
              <button
                type="button"
                onClick={() => setParams({ tab: p.clave }, { replace: true })}
                aria-current={p.clave === actual ? 'page' : undefined}
                className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium whitespace-nowrap ${
                  p.clave === actual ? 'border-marca-600 text-marca-700' : 'border-transparent text-slate-600 hover:text-slate-900'
                }`}
              >
                {t(p.texto)}
              </button>
            </li>
          ))}
        </ul>
      </nav>
      {actual === 'transferencias' && <Transferencias onPronostico={setPronostico} />}
      {actual === 'compras' && <Compras onPronostico={setPronostico} />}
      {actual === 'plan' && <Plan onPronostico={setPronostico} />}
      {actual === 'parametros' && <Parametros />}
      <ModalPronostico producto={pronostico} onCerrar={() => setPronostico(null)} />
    </>
  )
}

type AbrirPronostico = (p: { id: string; nombre: string }) => void

const CONFIANZA: Record<Confianza, { texto: string; tono: 'ambar' | 'azul' | 'verde'; ayuda: string }> = {
  BAJA: { texto: 'Confianza baja', tono: 'ambar', ayuda: 'Poco historial de ventas (menos de 4 semanas): revise la sugerencia.' },
  MEDIA: { texto: 'Confianza media', tono: 'azul', ayuda: 'Algunas semanas de historial; el pronóstico se afina con el tiempo.' },
  ALTA: { texto: 'Confianza alta', tono: 'verde', ayuda: '12 semanas o más de historial y error bajo en las pruebas.' },
}

function InsigniaConfianza({ c }: { c: Confianza }) {
  const { t } = useTranslation()
  return (
    <span title={t(CONFIANZA[c].ayuda)}>
      <Insignia tono={CONFIANZA[c].tono}>{t(CONFIANZA[c].texto)}</Insignia>
    </span>
  )
}

function NombreProducto({ f, onPronostico }: { f: FilaReposicion; onPronostico: AbrirPronostico }) {
  const { t } = useTranslation()
  return (
    <button type="button" onClick={() => onPronostico(f.producto)} className="text-left hover:underline" title={t("Ver el pronóstico")}>
      <span className="font-medium text-slate-900">{f.producto.nombre}</span>
      <span className="block text-xs text-slate-500">
        {f.sku} · {formatearCantidad(f.demanda_semanal)} {f.unidad}{t("/semana")}
      </span>
    </button>
  )
}

const cobertura = (f: FilaReposicion, t: TFunction) =>
  f.cobertura_dias === null ? t('sin ventas') : t('{{n}} días', { n: formatearCantidad(f.cobertura_dias) })

async function cargarProductos(ids: string[]): Promise<Map<string, Producto>> {
  const productos = await Promise.all([...new Set(ids)].map((id) => api<Producto>(`/productos/${id}`)))
  return new Map(productos.map((p) => [p.id, p]))
}

function presentacionDe(producto: Producto, nombre: string, cantidadBase: string, cantidadPres: string) {
  const pres = producto.presentaciones.find((p) => p.nombre === nombre)
  return pres ? { presentacion_id: pres.id, cantidad: String(Number(cantidadPres)) } : { presentacion_id: '', cantidad: String(Number(cantidadBase)) }
}

function agrupar<T>(items: T[], clave: (x: T) => string): [string, T[]][] {
  const grupos = new Map<string, T[]>()
  for (const x of items) grupos.set(clave(x), [...(grupos.get(clave(x)) ?? []), x])
  return [...grupos.entries()]
}

// ---------------------------------------------------------------- depósito → sucursal

function Transferencias({ onPronostico }: { onPronostico: AbrirPronostico }) {
  const { t } = useTranslation()
  const navegar = useNavigate()
  const sugerencias = useQuery({
    queryKey: ['reposicion', 'transferencias'],
    queryFn: () => api<SugerenciaTransferencia[]>('/reposicion/transferencias'),
  })
  const [quitadas, setQuitadas] = useState<Set<string>>(new Set())
  const clave = (s: SugerenciaTransferencia) => `${s.ubicacion.id}:${s.producto.id}`
  const crear = useMutation({
    mutationFn: async (grupo: SugerenciaTransferencia[]) => {
      const elegidas = grupo.filter((s) => !quitadas.has(clave(s)) && Number(s.cantidad) > 0)
      const productos = await cargarProductos(elegidas.map((s) => s.producto.id))
      navegar('/transferencias/nueva', {
        state: {
          origen: grupo[0].origen.id,
          destino: grupo[0].ubicacion.id,
          lineas: elegidas.map((s) => {
            const producto = productos.get(s.producto.id)!
            return { producto, ...presentacionDe(producto, s.presentacion, s.cantidad, s.cantidad_presentacion) }
          }),
        },
      })
    },
  })
  if (sugerencias.isError) return <Aviso>{mensajeError(sugerencias.error)}</Aviso>
  if (!sugerencias.data) return <p className="text-sm text-slate-500">{t("Calculando…")}</p>
  if (sugerencias.data.length === 0) return <Vacio>{t("Ninguna sucursal necesita reposición por ahora.")}</Vacio>
  return (
    <div className="space-y-6">
      {crear.isError && <Aviso>{mensajeError(crear.error)}</Aviso>}
      {agrupar(sugerencias.data, (s) => `${s.origen.id}→${s.ubicacion.id}`).map(([k, grupo]) => (
        <section key={k} className="space-y-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="font-semibold">
              {grupo[0].origen.nombre} → {grupo[0].ubicacion.nombre}
            </h2>
            <Boton disabled={crear.isPending || grupo.every((s) => quitadas.has(clave(s)))} onClick={() => crear.mutate(grupo)}>
              <ArrowLeftRight size={16} /> {t("Crear transferencia")}
            </Boton>
          </div>
          <Tabla>
            <thead className={CABECERA_TABLA}>
              <tr>
                <th className="w-10" />
                <th>{t("Producto")}</th>
                <th className="text-right">{t("Disponible")}</th>
                <th className="text-right">{t("Alcanza para")}</th>
                <th className="text-right">{t("En el depósito")}</th>
                <th className="text-right">{t("Transferir")}</th>
                <th>{t("Pronóstico")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {grupo.map((s) => (
                <tr key={clave(s)}>
                  <td>
                    <input
                      type="checkbox"
                      className="size-4 accent-marca-600"
                      aria-label={t("Incluir {{v0}}", { v0: s.producto.nombre })}
                      checked={!quitadas.has(clave(s))}
                      onChange={(e) =>
                        setQuitadas((q) => {
                          const n = new Set(q)
                          if (e.target.checked) n.delete(clave(s))
                          else n.add(clave(s))
                          return n
                        })
                      }
                    />
                  </td>
                  <td className="min-w-48">
                    <NombreProducto f={s} onPronostico={onPronostico} />
                  </td>
                  <td className="text-right tabular-nums">{formatearCantidad(s.disponible)}</td>
                  <td className="text-right whitespace-nowrap">{cobertura(s, t)}</td>
                  <td className="text-right tabular-nums">{formatearCantidad(s.origen_disponible)}</td>
                  <td className="text-right whitespace-nowrap">
                    <strong className="tabular-nums">
                      {formatearCantidad(s.cantidad_presentacion)} {s.presentacion === 'unidad' ? s.unidad : s.presentacion.toLowerCase()}
                    </strong>
                    {s.presentacion !== 'unidad' && <span className="block text-xs text-slate-500">{formatearCantidad(s.cantidad)} {s.unidad}</span>}
                    {s.insuficiente && <span className="block text-xs text-red-700">{t("El depósito no alcanza: hay que comprar")}</span>}
                  </td>
                  <td>
                    <InsigniaConfianza c={s.confianza} />
                  </td>
                </tr>
              ))}
            </tbody>
          </Tabla>
        </section>
      ))}
      <p className="text-xs text-slate-500">
        {t("Se sugiere reponer cuando lo disponible baja del punto de reorden, hasta cubrir los días configurados. El depósito de origen es el que suele abastecer a esa sucursal (según las transferencias registradas). Puede cambiar todo en la transferencia antes de guardarla.")}
      </p>
    </div>
  )
}

// ---------------------------------------------------------------- proveedor → depósito

function Compras({ onPronostico }: { onPronostico: AbrirPronostico }) {
  const { t } = useTranslation()
  const navegar = useNavigate()
  const sugerencias = useQuery({ queryKey: ['reposicion', 'compras'], queryFn: () => api<SugerenciaCompra[]>('/reposicion/compras') })
  const hoy = hoyLaPaz()
  const crear = useMutation({
    mutationFn: async (grupo: SugerenciaCompra[]) => {
      const productos = await cargarProductos(grupo.map((s) => s.producto.id))
      navegar('/compras/nueva', {
        state: {
          proveedor_id: grupo[0].proveedor?.id,
          ubicacion_id: grupo[0].ubicacion.id,
          lineas: grupo.map((s) => {
            const producto = productos.get(s.producto.id)!
            const { presentacion_id, cantidad } = presentacionDe(producto, s.presentacion, s.cantidad, s.cantidad_presentacion)
            const precio = s.costo_estimado ? String(Math.round((Number(s.costo_estimado) / Number(cantidad)) * 100) / 100) : ''
            return { producto, presentacion_id, cantidad, precio }
          }),
        },
      })
    },
  })
  if (sugerencias.isError) return <Aviso>{mensajeError(sugerencias.error)}</Aviso>
  if (!sugerencias.data) return <p className="text-sm text-slate-500">{t("Calculando…")}</p>
  if (sugerencias.data.length === 0) return <Vacio>{t("No hace falta comprar nada en los próximos 14 días.")}</Vacio>
  return (
    <div className="space-y-6">
      {crear.isError && <Aviso>{mensajeError(crear.error)}</Aviso>}
      {agrupar(sugerencias.data, (s) => `${s.proveedor?.id ?? '-'}→${s.ubicacion.id}`).map(([k, grupo]) => {
        const ahora = grupo.filter((s) => s.fecha <= hoy)
        const total = grupo.reduce((t, s) => t + Number(s.costo_estimado ?? 0), 0)
        return (
          <section key={k} className="space-y-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="font-semibold">
                {grupo[0].proveedor?.nombre ?? t("Sin proveedor asociado")} → {grupo[0].ubicacion.nombre}
                {total > 0 && <span className="ml-2 text-sm font-normal text-slate-500">≈ {formatearBs(total)}</span>}
              </h2>
              <Boton disabled={crear.isPending} onClick={() => crear.mutate(ahora.length ? ahora : grupo)}>
                <ShoppingCart size={16} /> {ahora.length ? t("Crear compra ({{v0}} para ya)", { v0: ahora.length }) : t("Crear compra")}
              </Boton>
            </div>
            <Tabla>
              <thead className={CABECERA_TABLA}>
                <tr>
                  <th>{t("Producto")}</th>
                  <th className="text-right">{t("Disponible")}</th>
                  <th className="text-right">{t("Alcanza para")}</th>
                  <th>{t("Cuándo")}</th>
                  <th className="text-right">{t("Comprar")}</th>
                  {grupo.some((s) => s.costo_estimado) && <th className="text-right">{t("Costo estimado")}</th>}
                  <th>{t("Pronóstico")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {grupo.map((s) => (
                  <tr key={s.producto.id}>
                    <td className="min-w-48">
                      <NombreProducto f={s} onPronostico={onPronostico} />
                    </td>
                    <td className="text-right tabular-nums">{formatearCantidad(s.disponible)}</td>
                    <td className="text-right whitespace-nowrap">{cobertura(s, t)}</td>
                    <td className="whitespace-nowrap">
                      {s.fecha <= hoy ? <strong className="text-red-700">{t("Ya")}</strong> : formatearDia(s.fecha)}
                      <span className="block text-xs text-slate-500">{t("entrega en")} {s.dias_entrega} {t("días")}</span>
                    </td>
                    <td className="text-right whitespace-nowrap">
                      <strong className="tabular-nums">
                        {formatearCantidad(s.cantidad_presentacion)} {s.presentacion === 'unidad' ? s.unidad : s.presentacion.toLowerCase()}
                      </strong>
                      {s.presentacion !== 'unidad' && <span className="block text-xs text-slate-500">{formatearCantidad(s.cantidad)} {s.unidad}</span>}
                    </td>
                    {grupo.some((x) => x.costo_estimado) && <td className="text-right tabular-nums">{formatearBs(s.costo_estimado)}</td>}
                    <td>
                      <InsigniaConfianza c={s.confianza} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </Tabla>
          </section>
        )
      })}
      <p className="text-xs text-slate-500">
        {t("La demanda de cada depósito es la de las sucursales que abastece. «Ya» significa que el stock está por debajo del punto de reorden (lo que se vende mientras llega la compra, más un margen de seguridad). El costo estimado usa el precio de la última compra.")}
      </p>
    </div>
  )
}

// ---------------------------------------------------------------- plan completo

function Plan({ onPronostico }: { onPronostico: AbrirPronostico }) {
  const { t } = useTranslation()
  const plan = useQuery({ queryKey: ['reposicion', 'plan'], queryFn: () => api<FilaReposicion[]>('/reposicion/plan') })
  const [filtro, setFiltro] = useState('')
  if (plan.isError) return <Aviso>{mensajeError(plan.error)}</Aviso>
  if (!plan.data) return <p className="text-sm text-slate-500">{t("Calculando…")}</p>
  const urgente = (f: FilaReposicion) => (Number(f.demanda_semanal) > 0 || f.con_limites) && Number(f.disponible) <= Number(f.punto_reorden)
  // Primero lo que hay que reponer, luego lo que más se vende.
  const filas = plan.data
    .filter((f) => `${f.producto.nombre} ${f.sku} ${f.ubicacion.nombre}`.toLowerCase().includes(filtro.toLowerCase()))
    .sort((a, b) => Number(urgente(b)) - Number(urgente(a)) || Number(b.demanda_semanal) - Number(a.demanda_semanal))
  return (
    <div className="space-y-3">
      <Entrada placeholder={t("Buscar producto o ubicación…")} value={filtro} onChange={(e) => setFiltro(e.target.value)} className="max-w-sm" />
      <Tabla>
        <thead className={CABECERA_TABLA}>
          <tr>
            <th>{t("Ubicación")}</th>
            <th>{t("Producto")}</th>
            <th className="text-right">{t("Disponible")}</th>
            <th className="text-right">{t("Alcanza para")}</th>
            <th className="text-right">{t("Seguridad")}</th>
            <th className="text-right">{t("Punto de reorden")}</th>
            <th className="text-right">{t("Objetivo")}</th>
            <th>{t("Pronóstico")}</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {filas.map((f) => {
            const bajo = urgente(f)
            return (
              <tr key={`${f.ubicacion.id}:${f.producto.id}`}>
                <td className="whitespace-nowrap">{f.ubicacion.nombre}</td>
                <td className="min-w-48">
                  <NombreProducto f={f} onPronostico={onPronostico} />
                </td>
                <td className={`text-right tabular-nums ${bajo ? 'font-semibold text-red-700' : ''}`}>{formatearCantidad(f.disponible)}</td>
                <td className="text-right whitespace-nowrap">{cobertura(f, t)}</td>
                <td className="text-right tabular-nums">{formatearCantidad(f.stock_seguridad)}</td>
                <td className="text-right tabular-nums">{formatearCantidad(f.punto_reorden)}</td>
                <td className="text-right tabular-nums">
                  {formatearCantidad(f.objetivo)}
                  {f.con_limites && <span className="block text-xs text-slate-500">{t("mín./máx. cargados")}</span>}
                </td>
                <td className="whitespace-nowrap">
                  <InsigniaConfianza c={f.confianza} />
                  <span className="block text-xs text-slate-500">{f.metodo}</span>
                </td>
              </tr>
            )
          })}
        </tbody>
      </Tabla>
    </div>
  )
}

// ---------------------------------------------------------------- parámetros

const CAMPOS: { clave: keyof ParametrosAlertas; etiqueta: string; ayuda: string }[] = [
  { clave: 'dias_entrega_proveedor', etiqueta: 'Días de entrega del proveedor', ayuda: 'Cuánto tarda en llegar una compra (cada proveedor puede tener el suyo).' },
  { clave: 'dias_reposicion_sucursal', etiqueta: 'Días para reponer una sucursal', ayuda: 'Las transferencias llegan el mismo día: 1.' },
  { clave: 'cobertura_sucursal_dias', etiqueta: 'Cobertura de la sucursal (días)', ayuda: 'Al reponer, stock para estos días de venta.' },
  { clave: 'cobertura_deposito_dias', etiqueta: 'Cobertura del depósito (días)', ayuda: 'Al comprar, stock para estos días de venta.' },
  { clave: 'margen_minimo', etiqueta: 'Margen mínimo (%)', ayuda: 'Avisa si un pedido gana menos (el negativo avisa siempre).' },
  { clave: 'dias_sin_movimiento', etiqueta: 'Sin movimiento (días)', ayuda: 'Avisa del stock que no sale en este tiempo.' },
  { clave: 'dias_aviso_vencimiento', etiqueta: 'Aviso de vencimiento (días antes)', ayuda: 'Avisa de los lotes que vencen pronto.' },
  { clave: 'diferencia_conteo_pct', etiqueta: 'Diferencia en conteos (%)', ayuda: 'Avisa si lo contado se aparta tanto del sistema.' },
  { clave: 'sobre_stock_veces', etiqueta: 'Sobre-stock (veces la cobertura)', ayuda: 'Avisa si el stock alcanza para más de N veces la cobertura.' },
]

function Parametros() {
  const { t } = useTranslation()
  const puede = usePuede()
  const queryClient = useQueryClient()
  const editable = puede('configuracion.gestionar')
  const actuales = useQuery({ queryKey: ['alertas', 'parametros'], queryFn: () => api<ParametrosAlertas>('/alertas/parametros') })
  const [form, setForm] = useState<Record<string, string> | null>(null)
  const valores = form ?? Object.fromEntries(Object.entries(actuales.data ?? {}).map(([k, v]) => [k, String(v)]))
  const guardar = useMutation({
    mutationFn: () =>
      api<ParametrosAlertas>('/alertas/parametros', {
        metodo: 'PUT',
        cuerpo: Object.fromEntries(Object.entries(valores).map(([k, v]) => [k, Number(v)])),
      }),
    onSuccess: () => {
      setForm(null)
      void queryClient.invalidateQueries({ queryKey: ['alertas'] })
      void queryClient.invalidateQueries({ queryKey: ['reposicion'] })
    },
  })
  const recalcular = useMutation({
    mutationFn: () => api<{ pronosticos: number }>('/alertas/evaluar', { metodo: 'POST', params: { recalcular_pronostico: true } }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['reposicion'] })
      void queryClient.invalidateQueries({ queryKey: ['alertas'] })
    },
  })
  if (!actuales.data) return actuales.isError ? <Aviso>{mensajeError(actuales.error)}</Aviso> : <p className="text-sm text-slate-500">{t("Cargando…")}</p>
  return (
    <form
      className="max-w-3xl space-y-4"
      onSubmit={(e) => {
        e.preventDefault()
        guardar.mutate()
      }}
    >
      <div className="grid gap-4 sm:grid-cols-2">
        {CAMPOS.map((c) => (
          <Campo key={c.clave} etiqueta={t(c.etiqueta)} ayuda={t(c.ayuda)}>
            <Entrada
              type="number"
              min={0}
              step="any"
              disabled={!editable}
              value={valores[c.clave] ?? ''}
              onChange={(e) => setForm({ ...valores, [c.clave]: e.target.value })}
            />
          </Campo>
        ))}
      </div>
      {guardar.isError && <Aviso>{mensajeError(guardar.error)}</Aviso>}
      {guardar.isSuccess && <Aviso tipo="exito">{t("Parámetros guardados; las alertas ya usan los nuevos valores.")}</Aviso>}
      {recalcular.isSuccess && <Aviso tipo="exito">{t("Pronóstico recalculado para")} {recalcular.data.pronosticos} {t("productos.")}</Aviso>}
      {recalcular.isError && <Aviso>{mensajeError(recalcular.error)}</Aviso>}
      <div className="flex flex-wrap gap-2">
        {editable && (
          <Boton type="submit" disabled={!form || guardar.isPending}>
            {guardar.isPending ? t("Guardando…") : t("Guardar parámetros")}
          </Boton>
        )}
        <Boton variante="secundario" disabled={recalcular.isPending} onClick={() => recalcular.mutate()}>
          <RefreshCw size={16} className={recalcular.isPending ? 'animate-spin' : ''} /> {t("Recalcular pronóstico ahora")}
        </Boton>
      </div>
      <p className="text-xs text-slate-500">
        {t("El pronóstico se recalcula solo cada lunes de madrugada con las ventas de hasta 52 semanas: prueba varios métodos (promedio, promedio móvil y suavizado exponencial) y usa el que mejor acierta con las ventas pasadas.")}
        {!editable && t(" Solo quien tiene permiso de configuración puede cambiar estos valores.")}
      </p>
    </form>
  )
}

// ---------------------------------------------------------------- pronóstico de un producto

function ModalPronostico({ producto, onCerrar }: { producto: { id: string; nombre: string } | null; onCerrar: () => void }) {
  const { t } = useTranslation()
  const datos = useQuery({
    queryKey: ['reposicion', 'pronostico', producto?.id],
    queryFn: () => api<PronosticoProducto[]>(`/reposicion/pronostico/${producto!.id}`),
    enabled: !!producto,
  })
  const conVentas = (datos.data ?? []).filter((p) => p.historial.some((v) => v > 0))
  return (
    <Modal abierto={!!producto} titulo={t("Pronóstico: {{v0}}", { v0: producto?.nombre ?? '' })} onCerrar={onCerrar}>
      <div className="space-y-4">
        {datos.isError && <Aviso>{mensajeError(datos.error)}</Aviso>}
        {datos.data && conVentas.length === 0 && <p className="text-sm text-slate-500">{t("Todavía no hay ventas de este producto: no hay pronóstico.")}</p>}
        {conVentas.map((p) => (
          <div key={p.ubicacion.id} className="space-y-2">
            <p className="flex flex-wrap items-center gap-2 text-sm">
              <strong>{p.ubicacion.nombre}</strong>
              <InsigniaConfianza c={p.confianza} />
              <span className="text-slate-600">
                {formatearCantidad(p.demanda_semanal)} {t("por semana ·")} {p.metodo} · {p.semanas} {t("semana(s) de historial")}
                {p.error_medio !== null && t(" · error medio {{v0}}", { v0: formatearCantidad(p.error_medio) })}
              </span>
            </p>
            <Grafico
              serie={{
                clave: p.ubicacion.id,
                titulo: 'Unidades vendidas por semana y pronóstico de la próxima',
                tipo: 'cantidad',
                forma: 'barras',
                eje: 'tiempo',
                claves: [
                  { clave: 'vendido', titulo: 'Vendido', tipo: 'cantidad' },
                  { clave: 'pronostico', titulo: 'Pronóstico', tipo: 'cantidad' },
                ],
                puntos: [
                  ...p.historial.map((v, i) => ({
                    etiqueta: i === p.historial.length - 1 ? 'Esta semana' : `Hace ${p.historial.length - 1 - i} sem.`,
                    vendido: v,
                    pronostico: null,
                  })),
                  { etiqueta: t('Próxima'), vendido: null, pronostico: Number(p.demanda_semanal) },
                ],
              }}
            />
          </div>
        ))}
        <p className="flex items-center gap-1 text-xs text-slate-500">
          <LineChart size={14} aria-hidden /> {t("Con más semanas de ventas el pronóstico gana confianza.")}
        </p>
      </div>
    </Modal>
  )
}
