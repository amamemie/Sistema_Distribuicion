import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Aviso, Boton, Campo, Encabezado, Entrada, Selector, Tabla } from '../components/ui'
import { api, mensajeError } from '../lib/api'
import { formatearFecha } from '../lib/formato'
import type { Pagina, RegistroAuditoria } from '../lib/tipos'
import { useTranslation } from 'react-i18next'

const ENTIDADES = [
  { valor: '', texto: 'Todas' },
  { valor: 'usuario', texto: 'Usuarios' },
  { valor: 'rol', texto: 'Roles' },
  { valor: 'ubicacion', texto: 'Ubicaciones' },
]

const TAMANO = 50

export function Auditoria() {
  const { t } = useTranslation()
  const [entidad, setEntidad] = useState('')
  const [accion, setAccion] = useState('')
  const [desde, setDesde] = useState('')
  const [hasta, setHasta] = useState('')
  const [pagina, setPagina] = useState(1)
  const [abierto, setAbierto] = useState<number | null>(null)

  const registros = useQuery({
    queryKey: ['auditoria', entidad, accion, desde, hasta, pagina],
    queryFn: () =>
      api<Pagina<RegistroAuditoria>>('/auditoria', {
        params: {
          entidad,
          accion,
          // Fechas interpretadas en la hora de La Paz (UTC-4).
          desde: desde ? `${desde}T00:00:00-04:00` : undefined,
          hasta: hasta ? `${hasta}T23:59:59-04:00` : undefined,
          pagina,
          tamano: TAMANO,
        },
      }),
    placeholderData: keepPreviousData,
  })
  const total = registros.data?.total ?? 0
  const paginas = Math.max(1, Math.ceil(total / TAMANO))
  const filtrar = <T,>(setter: (v: T) => void) => (v: T) => {
    setter(v)
    setPagina(1)
  }

  return (
    <>
      <Encabezado titulo={t("Auditoría")} descripcion={t("Registro inmutable de quién hizo qué y cuándo.")} />
      <div className="mb-4 grid gap-3 sm:grid-cols-4">
        <Campo etiqueta={t("Entidad")}>
          <Selector value={entidad} onChange={(e) => filtrar(setEntidad)(e.target.value)}>
            {ENTIDADES.map((e) => (
              <option key={e.valor} value={e.valor}>
                {t(e.texto)}
              </option>
            ))}
          </Selector>
        </Campo>
        <Campo etiqueta={t("Acción (empieza con)")}>
          <Entrada value={accion} placeholder={t("usuario.")} onChange={(e) => filtrar(setAccion)(e.target.value)} />
        </Campo>
        <Campo etiqueta={t("Desde")}>
          <Entrada type="date" value={desde} onChange={(e) => filtrar(setDesde)(e.target.value)} />
        </Campo>
        <Campo etiqueta={t("Hasta")}>
          <Entrada type="date" value={hasta} onChange={(e) => filtrar(setHasta)(e.target.value)} />
        </Campo>
      </div>
      {registros.isError && <Aviso>{mensajeError(registros.error)}</Aviso>}
      <Tabla>
        <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-500">
          <tr>
            <th>{t("Fecha")}</th>
            <th>{t("Usuario")}</th>
            <th>{t("Acción")}</th>
            <th className="hidden md:table-cell">{t("IP")}</th>
            <th />
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {registros.data?.items.map((r) => (
            <FilaAuditoria
              key={r.id}
              registro={r}
              abierto={abierto === r.id}
              onAlternar={() => setAbierto(abierto === r.id ? null : r.id)}
            />
          ))}
          {registros.data?.items.length === 0 && (
            <tr>
              <td colSpan={5} className="text-center text-slate-500">
                {t("Sin registros para estos filtros.")}
              </td>
            </tr>
          )}
        </tbody>
      </Tabla>
      <div className="mt-4 flex items-center justify-between text-sm text-slate-600">
        <span>{total} {t("registros")}</span>
        <div className="flex items-center gap-2">
          <Boton variante="secundario" disabled={pagina <= 1} onClick={() => setPagina(pagina - 1)}>
            {t("Anterior")}
          </Boton>
          <span>
            {pagina} / {paginas}
          </span>
          <Boton variante="secundario" disabled={pagina >= paginas} onClick={() => setPagina(pagina + 1)}>
            {t("Siguiente")}
          </Boton>
        </div>
      </div>
    </>
  )
}

function FilaAuditoria({
  registro: r,
  abierto,
  onAlternar,
}: {
  registro: RegistroAuditoria
  abierto: boolean
  onAlternar: () => void
}) {
  const { t } = useTranslation()
  const tieneDetalle = r.antes || r.despues
  return (
    <>
      <tr>
        <td className="whitespace-nowrap text-slate-600">{formatearFecha(r.fecha)}</td>
        <td>{r.usuario_nombre ?? t("Sistema")}</td>
        <td>
          <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs">{r.accion}</code>
        </td>
        <td className="hidden text-slate-500 md:table-cell">{r.ip ?? '—'}</td>
        <td className="text-right">
          {tieneDetalle && (
            <Boton variante="fantasma" onClick={onAlternar}>
              {abierto ? t("Ocultar") : t("Detalle")}
            </Boton>
          )}
        </td>
      </tr>
      {abierto && (
        <tr className="bg-slate-50">
          <td colSpan={5}>
            <div className="grid gap-3 md:grid-cols-2">
              <Json titulo={t("Antes")} valor={r.antes} />
              <Json titulo={t("Después")} valor={r.despues} />
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

function Json({ titulo, valor }: { titulo: string; valor: Record<string, unknown> | null }) {
  return (
    <div>
      <div className="mb-1 text-xs font-semibold uppercase text-slate-500">{titulo}</div>
      <pre className="overflow-x-auto rounded border border-slate-200 bg-white p-3 text-xs">
        {valor ? JSON.stringify(valor, null, 2) : '—'}
      </pre>
    </div>
  )
}
