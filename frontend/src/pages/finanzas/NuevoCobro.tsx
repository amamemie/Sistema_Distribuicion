import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, ArrowLeft } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { Aviso, Boton, Campo, Encabezado, Entrada, Selector, Tarjeta, Vacio } from '../../components/ui'
import { api, mensajeError } from '../../lib/api'
import { useCadenas } from '../../lib/consultas'
import { formatearBs, formatearDia, hoyLaPaz } from '../../lib/formato'
import type { CobroDetalle, PorCobrar } from '../../lib/tipos'
import { repartir } from './utiles'
import { useTranslation } from 'react-i18next'

/** Registrar la transferencia de una empresa contra el TOTAL que debe (T-31): el sistema la
 * aplica sola a las entregas, de la más antigua a la más reciente. */
export function NuevoCobro() {
  const { t } = useTranslation()
  const navegar = useNavigate()
  const queryClient = useQueryClient()
  const [params] = useSearchParams()
  const cadenas = useCadenas()
  const activas = cadenas.data?.filter((c) => c.activo) ?? []
  const [cadenaElegida, setCadena] = useState(params.get('cadena') ?? '')
  const cadena = cadenaElegida || (activas.length === 1 ? activas[0].id : '')
  const [f, setF] = useState({ fecha: hoyLaPaz(), monto: '', banco: '', referencia: '', observaciones: '' })
  const [archivo, setArchivo] = useState<File | null>(null)

  const deuda = useQuery({
    queryKey: ['por-cobrar', cadena, false],
    queryFn: () => api<PorCobrar>('/finanzas/por-cobrar', { params: { cadena_id: cadena } }),
    enabled: !!cadena,
  })
  const resumen = deuda.data?.cadenas.find((c) => c.cadena.id === cadena)
  const debe = Number(resumen?.pendiente ?? 0)
  const pendientes = (deuda.data?.cuentas ?? []).filter((c) => Number(c.saldo) > 0)
  const monto = Number(f.monto || 0)
  const aplicado = repartir(f.monto || 0, pendientes.map((c) => c.saldo))
  const cubiertas = pendientes.filter((_, i) => aplicado[i] > 0 && aplicado[i] >= Number(pendientes[i].saldo))
  const quedaDebiendo = Math.max(0, Math.round((debe - monto) * 100) / 100)
  const excede = monto > debe + 0.004

  const registrar = useMutation({
    mutationFn: async () => {
      const cobro = await api<CobroDetalle>('/finanzas/cobros', {
        metodo: 'POST',
        cuerpo: {
          cadena_id: cadena,
          fecha: f.fecha,
          monto: f.monto,
          banco: f.banco || null,
          referencia: f.referencia || null,
          observaciones: f.observaciones || null,
        },
      })
      if (archivo) {
        const datos = new FormData()
        datos.append('archivo', archivo)
        await api(`/finanzas/cobros/${cobro.id}/comprobante`, { metodo: 'POST', cuerpo: datos })
      }
      return cobro
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['por-cobrar'] })
      void queryClient.invalidateQueries({ queryKey: ['cobros'] })
      navegar('/finanzas', { replace: true })
    },
  })

  return (
    <>
      <Link to="/finanzas" className="mb-2 inline-flex items-center gap-1 text-sm text-slate-600 hover:text-slate-900">
        <ArrowLeft size={16} /> {t("Finanzas")}
      </Link>
      <Encabezado titulo={t("Registrar cobro")} descripcion={t("Anote la transferencia que hizo la empresa. Se descuenta de lo que debe, empezando por las entregas más antiguas.")} />
      <form
        className="max-w-2xl space-y-5"
        onSubmit={(e) => {
          e.preventDefault()
          registrar.mutate()
        }}
      >
        <Tarjeta className="space-y-4 p-4">
          <Campo etiqueta={t("Empresa")}>
            <Selector required value={cadena} onChange={(e) => setCadena(e.target.value)}>
              <option value="">{t("Elegir…")}</option>
              {activas.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.nombre}
                </option>
              ))}
            </Selector>
          </Campo>
          {deuda.isError && <Aviso>{mensajeError(deuda.error)}</Aviso>}
          {cadena && deuda.data && (
            <div className="rounded-lg bg-slate-50 p-4">
              <p className="text-sm text-slate-500">{t("Le debe")}</p>
              <p className="text-3xl font-semibold tracking-tight tabular-nums">{formatearBs(debe)}</p>
              {Number(resumen?.vencido ?? 0) > 0 && (
                <p className="mt-1 flex items-center gap-1 text-sm font-medium text-red-700">
                  <AlertTriangle size={14} aria-hidden /> {t("Vencido:")} {formatearBs(resumen?.vencido)}
                </p>
              )}
            </div>
          )}
        </Tarjeta>

        {cadena && deuda.data && debe <= 0 && <Vacio>{t("Esta empresa no tiene nada pendiente de cobro.")}</Vacio>}

        {cadena && debe > 0 && (
          <>
            <Tarjeta className="grid gap-4 p-4 sm:grid-cols-2">
              <Campo etiqueta={t("Monto transferido (Bs)")}>
                <Entrada
                  required
                  inputMode="decimal"
                  autoFocus
                  value={f.monto}
                  aria-invalid={excede}
                  onChange={(e) => setF((x) => ({ ...x, monto: e.target.value.replace(',', '.') }))}
                />
              </Campo>
              <Campo etiqueta={t("Fecha de la transferencia")}>
                <Entrada type="date" required max={hoyLaPaz()} value={f.fecha} onChange={(e) => setF((x) => ({ ...x, fecha: e.target.value }))} />
              </Campo>
              <Campo etiqueta={t("Banco (opcional)")}>
                <Entrada maxLength={80} value={f.banco} onChange={(e) => setF((x) => ({ ...x, banco: e.target.value }))} />
              </Campo>
              <Campo etiqueta={t("N.º de operación (opcional)")} ayuda={t("Evita registrar dos veces la misma transferencia.")}>
                <Entrada maxLength={60} value={f.referencia} onChange={(e) => setF((x) => ({ ...x, referencia: e.target.value }))} />
              </Campo>
              <Campo etiqueta={t("Comprobante (foto o PDF, opcional)")}>
                <input type="file" accept="image/*,application/pdf" className="block w-full text-sm" onChange={(e) => setArchivo(e.target.files?.[0] ?? null)} />
              </Campo>
              <Campo etiqueta={t("Observaciones (opcional)")}>
                <Entrada maxLength={500} value={f.observaciones} onChange={(e) => setF((x) => ({ ...x, observaciones: e.target.value }))} />
              </Campo>
            </Tarjeta>

            {monto > 0 && (
              <Tarjeta className="space-y-1 p-4 text-sm">
                {excede ? (
                  <p className="font-medium text-red-700">{t("El monto es mayor a lo que debe (")}{formatearBs(debe)}{t("). Revíselo.")}</p>
                ) : (
                  <>
                    <p>
                      {t("Después de este cobro,")} {resumen?.cadena.nombre} {t("quedará debiendo")}{' '}
                      <strong className="tabular-nums">{formatearBs(quedaDebiendo)}</strong>.
                    </p>
                    {cubiertas.length > 0 && (
                      <p className="text-slate-500">
                        {t("Quedan pagadas")} {cubiertas.length} {t("entrega(s), hasta la del")} {formatearDia(cubiertas[cubiertas.length - 1].fecha)}.
                      </p>
                    )}
                    {quedaDebiendo > 0 && (
                      <p className="text-slate-500">
                        {t("Si la diferencia no se va a pagar (por un error en la factura), después use «Rebajar saldo» en Por cobrar.")}
                      </p>
                    )}
                  </>
                )}
              </Tarjeta>
            )}

            {registrar.isError && <Aviso>{mensajeError(registrar.error)}</Aviso>}
            <div className="flex justify-end">
              <Boton type="submit" disabled={!monto || excede || registrar.isPending}>
                {registrar.isPending ? t("Registrando…") : t("Registrar cobro")}
              </Boton>
            </div>
          </>
        )}
      </form>
    </>
  )
}
