import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { ArrowDownRight, ArrowUpRight, FileSpreadsheet, FileText, Minus, SlidersHorizontal } from 'lucide-react'
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { Grafico } from '../../components/reportes/Grafico'
import { SelectorProducto } from '../../components/SelectorProducto'
import { Aviso, Boton, CABECERA_TABLA, Campo, Encabezado, Entrada, Selector, Tabla, Tarjeta } from '../../components/ui'
import { api, construirUrl, mensajeError } from '../../lib/api'
import { useCadenas, useCategorias, useUbicaciones } from '../../lib/consultas'
import { hoyLaPaz } from '../../lib/formato'
import { PERMISOS_REPORTES_OPERATIVOS, usePuede } from '../../lib/sesion'
import type { Kpi, Producto, Reporte, TablaReporte } from '../../lib/tipos'
import { agrupacionSugerida, esNumerico, fechasDeRango, formatear, type Rango } from './utiles'

interface DefReporte {
  clave: string
  titulo: string
  rentabilidad?: boolean // solo con reportes.rentabilidad
  finanzas?: boolean // solo con finanzas.ver (resultados además con costos.ver)
  agrupacion?: boolean
  clientes?: boolean // admite filtro por cadena y sucursal
  soloCadena?: boolean // admite filtro por cadena (sin sucursal)
  sinMovimiento?: boolean
}

const REPORTES: DefReporte[] = [
  { clave: 'ganancias', titulo: 'Ganancias', rentabilidad: true, agrupacion: true, clientes: true },
  { clave: 'productos', titulo: 'Productos', clientes: true },
  { clave: 'clientes', titulo: 'Clientes', clientes: true },
  { clave: 'inventario', titulo: 'Inventario', sinMovimiento: true },
  { clave: 'ajustes', titulo: 'Mermas y ajustes', agrupacion: true },
  { clave: 'precios_compra', titulo: 'Precios de compra', rentabilidad: true },
  { clave: 'usuarios', titulo: 'Usuarios y lectura', agrupacion: true, clientes: true },
  { clave: 'resultados', titulo: 'Estado de resultados', finanzas: true, agrupacion: true, soloCadena: true },
  { clave: 'flujo_caja', titulo: 'Flujo de caja', finanzas: true, agrupacion: true, soloCadena: true },
  { clave: 'cobranza', titulo: 'Cobranza', finanzas: true, soloCadena: true },
  { clave: 'impuestos', titulo: 'Impuestos', finanzas: true },
]

function disponible(r: DefReporte, puede: (permiso: string) => boolean): boolean {
  if (r.finanzas) return puede('finanzas.ver') && (r.clave !== 'resultados' || puede('costos.ver'))
  if (r.rentabilidad) return puede('reportes.rentabilidad')
  return PERMISOS_REPORTES_OPERATIVOS.some(puede)
}

const RANGOS: { valor: Rango; texto: string }[] = [
  { valor: 'mes', texto: 'Este mes' },
  { valor: 'mes_anterior', texto: 'Mes anterior' },
  { valor: '7', texto: 'Últimos 7 días' },
  { valor: '30', texto: 'Últimos 30 días' },
  { valor: '90', texto: 'Últimos 90 días' },
  { valor: 'anio', texto: 'Este año' },
  { valor: 'personalizado', texto: 'Personalizado' },
]

const AGRUPACIONES = [
  { valor: 'dia', texto: 'Por día' },
  { valor: 'semana', texto: 'Por semana' },
  { valor: 'mes', texto: 'Por mes' },
  { valor: 'anio', texto: 'Por año' },
]

export function Reportes() {
  const puede = usePuede()
  const disponibles = REPORTES.filter((r) => disponible(r, puede))
  const [params, setParams] = useSearchParams()
  const actual = disponibles.find((r) => r.clave === params.get('r')) ?? disponibles[0]

  const hoy = hoyLaPaz()
  const [rango, setRango] = useState<Rango>('30')
  const [fechas, setFechas] = useState(() => fechasDeRango('30', hoy))
  const [agrupacion, setAgrupacion] = useState<string | null>(null) // null = automática
  const [ubicacion, setUbicacion] = useState('')
  const [cadena, setCadena] = useState('')
  const [sucursal, setSucursal] = useState('')
  const [categoria, setCategoria] = useState('')
  const [producto, setProducto] = useState<Producto | null>(null)
  const [diasQuieto, setDiasQuieto] = useState('30')
  const [masFiltros, setMasFiltros] = useState(false)

  const ubicaciones = useUbicaciones()
  const cadenas = useCadenas()
  const categorias = useCategorias()
  const sucursalesCadena = cadenas.data?.find((c) => c.id === cadena)?.sucursales ?? []

  const fechasValidas = !!fechas.desde && !!fechas.hasta && fechas.desde <= fechas.hasta
  const filtros = {
    desde: fechas.desde,
    hasta: fechas.hasta,
    agrupacion: agrupacion ?? (fechasValidas ? agrupacionSugerida(fechas.desde, fechas.hasta) : 'dia'),
    ubicacion_id: ubicacion || null,
    cadena_id: actual.clientes || actual.soloCadena ? cadena || null : null,
    sucursal_cliente_id: actual.clientes ? sucursal || null : null,
    categoria_id: actual.finanzas ? null : categoria || null,
    producto_id: actual.finanzas ? null : (producto?.id ?? null),
    dias_sin_movimiento: actual.sinMovimiento ? Number(diasQuieto) || 30 : null,
  }
  const reporte = useQuery({
    queryKey: ['reporte', actual.clave, filtros],
    queryFn: () => api<Reporte>(`/reportes/${actual.clave}`, { params: filtros }),
    enabled: fechasValidas,
    placeholderData: keepPreviousData,
  })
  const exportar = (formato: 'xlsx' | 'pdf') => construirUrl(`/reportes/${actual.clave}/exportar`, { ...filtros, formato })
  const filtrosActivos = [
    ubicacion,
    (actual.clientes || actual.soloCadena) && cadena,
    !actual.finanzas && categoria,
    !actual.finanzas && producto,
  ].filter(Boolean).length

  return (
    <>
      <Encabezado
        titulo="Reportes"
        descripcion="Ventas, rentabilidad, inventario y finanzas. Todo se puede exportar a Excel o PDF."
        acciones={
          <div className="flex gap-2">
            <a href={exportar('xlsx')} download className={CLASE_BOTON_EXPORTAR} aria-disabled={!fechasValidas}>
              <FileSpreadsheet size={16} /> Excel
            </a>
            <a href={exportar('pdf')} download className={CLASE_BOTON_EXPORTAR} aria-disabled={!fechasValidas}>
              <FileText size={16} /> PDF
            </a>
          </div>
        }
      />

      <nav aria-label="Reportes" className="-mx-4 mb-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
        <ul className="flex min-w-max gap-1 border-b border-slate-200">
          {disponibles.map((r) => (
            <li key={r.clave}>
              <button
                type="button"
                onClick={() => setParams({ r: r.clave }, { replace: true })}
                aria-current={r.clave === actual.clave ? 'page' : undefined}
                className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium whitespace-nowrap ${
                  r.clave === actual.clave ? 'border-marca-600 text-marca-700' : 'border-transparent text-slate-600 hover:text-slate-900'
                }`}
              >
                {r.titulo}
              </button>
            </li>
          ))}
        </ul>
      </nav>

      <Tarjeta className="mb-5 space-y-3 p-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Campo etiqueta={actual.clave === 'inventario' ? 'Ventas del período (rotación)' : 'Período'}>
            <Selector
              value={rango}
              onChange={(e) => {
                const valor = e.target.value as Rango
                setRango(valor)
                if (valor !== 'personalizado') setFechas(fechasDeRango(valor, hoy))
              }}
            >
              {RANGOS.map((r) => (
                <option key={r.valor} value={r.valor}>
                  {r.texto}
                </option>
              ))}
            </Selector>
          </Campo>
          <Campo etiqueta="Desde">
            <Entrada type="date" value={fechas.desde} max={fechas.hasta || hoy} onChange={(e) => (setRango('personalizado'), setFechas((f) => ({ ...f, desde: e.target.value })))} />
          </Campo>
          <Campo etiqueta="Hasta">
            <Entrada type="date" value={fechas.hasta} min={fechas.desde} onChange={(e) => (setRango('personalizado'), setFechas((f) => ({ ...f, hasta: e.target.value })))} />
          </Campo>
          {actual.agrupacion ? (
            <Campo etiqueta="Agrupar">
              <Selector value={filtros.agrupacion} onChange={(e) => setAgrupacion(e.target.value)}>
                {AGRUPACIONES.map((a) => (
                  <option key={a.valor} value={a.valor}>
                    {a.texto}
                  </option>
                ))}
              </Selector>
            </Campo>
          ) : actual.sinMovimiento ? (
            <Campo etiqueta="Sin movimiento desde hace (días)">
              <Entrada type="number" min={1} max={3650} value={diasQuieto} onChange={(e) => setDiasQuieto(e.target.value)} />
            </Campo>
          ) : null}
        </div>
        <Boton variante="fantasma" className="min-h-8 px-2 text-xs" onClick={() => setMasFiltros((v) => !v)} aria-expanded={masFiltros}>
          <SlidersHorizontal size={14} /> {masFiltros ? 'Menos filtros' : 'Más filtros'}
          {filtrosActivos > 0 && ` (${filtrosActivos} activos)`}
        </Boton>
        {masFiltros && (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Campo etiqueta="Ubicación">
              <Selector value={ubicacion} onChange={(e) => setUbicacion(e.target.value)}>
                <option value="">Todas</option>
                {ubicaciones.data?.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.nombre}
                  </option>
                ))}
              </Selector>
            </Campo>
            {(actual.clientes || actual.soloCadena) && (
              <>
                <Campo etiqueta="Cadena">
                  <Selector value={cadena} onChange={(e) => (setCadena(e.target.value), setSucursal(''))}>
                    <option value="">Todas</option>
                    {cadenas.data?.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.nombre}
                      </option>
                    ))}
                  </Selector>
                </Campo>
                {actual.clientes && (
                  <Campo etiqueta="Sucursal de cliente">
                    <Selector value={sucursal} disabled={!cadena} onChange={(e) => setSucursal(e.target.value)}>
                      <option value="">{cadena ? 'Todas' : 'Primero la cadena'}</option>
                      {sucursalesCadena.map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.nombre}
                        </option>
                      ))}
                    </Selector>
                  </Campo>
                )}
              </>
            )}
{!actual.finanzas && (
              <>
                <Campo etiqueta="Categoría">
                  <Selector value={categoria} onChange={(e) => setCategoria(e.target.value)}>
                    <option value="">Todas</option>
                    {categorias.data?.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.nombre}
                      </option>
                    ))}
                  </Selector>
                </Campo>
                <div className="sm:col-span-2">
                  <span className="mb-1 block text-sm font-medium text-slate-700">Producto</span>
                  <SelectorProducto valor={producto} onCambio={setProducto} />
                </div>
              </>
            )}
          </div>
        )}
        {!fechasValidas && <p className="text-xs text-red-600">Revise las fechas: «desde» debe ser anterior a «hasta».</p>}
      </Tarjeta>

      {reporte.isError && <Aviso>{mensajeError(reporte.error)}</Aviso>}
      {reporte.isPending && fechasValidas && <p className="text-sm text-slate-500">Cargando…</p>}
      {reporte.data && (
        <div className={`space-y-5 transition-opacity ${reporte.isFetching ? 'opacity-60' : ''}`}>
          <p className="text-sm text-slate-600">{reporte.data.descripcion}</p>
          {reporte.data.kpis.length > 0 && (
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
              {reporte.data.kpis.map((k) => (
                <TarjetaKpi key={k.clave} kpi={k} />
              ))}
            </div>
          )}
          {reporte.data.series.map((s) => (
            <Grafico key={s.clave} serie={s} />
          ))}
          {reporte.data.tablas.map((t) => (
            <TablaDeReporte key={t.clave} tabla={t} />
          ))}
        </div>
      )}
    </>
  )
}

const CLASE_BOTON_EXPORTAR =
  'inline-flex min-h-10 items-center gap-2 rounded-md border border-slate-300 bg-white px-3 text-sm font-medium hover:bg-slate-50 aria-disabled:pointer-events-none aria-disabled:opacity-50'

function TarjetaKpi({ kpi }: { kpi: Kpi }) {
  const variacion = kpi.variacion === null ? null : Number(kpi.variacion)
  // El costo que sube no es una buena noticia: la flecha se colorea según convenga.
  const buena = variacion === null || variacion === 0 ? null : kpi.clave === 'costo' ? variacion < 0 : variacion > 0
  const Icono = variacion === null || variacion === 0 ? Minus : variacion > 0 ? ArrowUpRight : ArrowDownRight
  return (
    <Tarjeta className="p-3">
      <p className="text-xs text-slate-500">{kpi.titulo}</p>
      <p className="mt-1 text-lg font-semibold text-slate-900 tabular-nums">{formatear(kpi.valor, kpi.tipo)}</p>
      {kpi.anterior !== null && (
        <p className="mt-1 flex flex-wrap items-center gap-1 text-xs text-slate-500">
          {variacion !== null && (
            <span className={`inline-flex items-center font-medium ${buena === null ? 'text-slate-600' : buena ? 'text-emerald-700' : 'text-red-700'}`}>
              <Icono size={14} aria-hidden />
              {variacion > 0 ? '+' : ''}
              {formatear(variacion, 'porcentaje')}
            </span>
          )}
          <span>antes: {formatear(kpi.anterior, kpi.tipo)}</span>
        </p>
      )}
    </Tarjeta>
  )
}

const FILAS_VISIBLES = 25

function TablaDeReporte({ tabla }: { tabla: TablaReporte }) {
  const [todas, setTodas] = useState(false)
  const filas = todas ? tabla.filas : tabla.filas.slice(0, FILAS_VISIBLES)
  return (
    <section className="space-y-2">
      <div>
        <h2 className="text-sm font-semibold text-slate-800">{tabla.titulo}</h2>
        {tabla.descripcion && <p className="text-xs text-slate-500">{tabla.descripcion}</p>}
      </div>
      {tabla.filas.length === 0 ? (
        <p className="rounded-lg border border-dashed border-slate-300 p-4 text-center text-sm text-slate-500">Sin datos en el período.</p>
      ) : (
        <Tabla>
          <thead className={CABECERA_TABLA}>
            <tr>
              {tabla.columnas.map((c) => (
                <th key={c.clave} className={esNumerico(c.tipo) ? 'text-right' : ''}>
                  {c.titulo}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {filas.map((f, i) => (
              <tr key={i} className={f.nivel === 'total' ? 'bg-slate-50 font-semibold' : ''}>
                {tabla.columnas.map((c) => (
                  <td key={c.clave} className={esNumerico(c.tipo) ? 'text-right whitespace-nowrap tabular-nums' : c.tipo === 'fecha' ? 'whitespace-nowrap' : ''}>
                    {c.clave === 'numero' && f.id ? (
                      <Link to={`/pedidos/${f.id}`} className="font-medium text-marca-700 hover:underline">
                        #{f.numero}
                      </Link>
                    ) : (
                      formatear(f[c.clave], c.tipo)
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </Tabla>
      )}
      {tabla.filas.length > FILAS_VISIBLES && (
        <Boton variante="fantasma" className="min-h-8 text-xs" onClick={() => setTodas((v) => !v)}>
          {todas ? 'Ver menos' : `Ver las ${tabla.filas.length} filas`}
        </Boton>
      )}
    </section>
  )
}
