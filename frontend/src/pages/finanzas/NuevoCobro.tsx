import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { Aviso, Boton, Campo, Casilla, Encabezado, Entrada, Selector, Tarjeta, Vacio } from '../../components/ui'
import { api, mensajeError } from '../../lib/api'
import { useCadenas } from '../../lib/consultas'
import { formatearBs, formatearDia, hoyLaPaz } from '../../lib/formato'
import type { CobroDetalle, CuentaPorCobrar, PorCobrar } from '../../lib/tipos'
import { InsigniaCuenta } from './Finanzas'
import { agruparPorMes, aTextoBs, cuadra, nombreMes, sumarBs } from './utiles'

interface Aplicacion {
  monto: string
  cerrar: boolean
  motivo: string
}

/** Registrar la transferencia de un supermercado y a qué pedidos corresponde (D-27, D-28). */
export function NuevoCobro() {
  const navegar = useNavigate()
  const queryClient = useQueryClient()
  const cadenas = useCadenas()
  const activas = cadenas.data?.filter((c) => c.activo) ?? []
  const [cadenaElegida, setCadena] = useState('')
  const cadena = cadenaElegida || (activas.length === 1 ? activas[0].id : '')
  const [cabecera, setCabecera] = useState({ fecha: hoyLaPaz(), banco: '', referencia: '', observaciones: '' })
  const [montoManual, setMontoManual] = useState<string | null>(null)
  const [seleccion, setSeleccion] = useState<Record<string, Aplicacion>>({})
  const [archivo, setArchivo] = useState<File | null>(null)

  const pendientes = useQuery({
    queryKey: ['por-cobrar', cadena, false],
    queryFn: () => api<PorCobrar>('/finanzas/por-cobrar', { params: { cadena_id: cadena } }),
    enabled: !!cadena,
    select: (d) => d.cuentas.filter((c) => Number(c.saldo) > 0),
  })
  const cuentas = pendientes.data ?? []
  const elegidas = cuentas.filter((c) => seleccion[c.pedido_id])
  const aplicado = sumarBs(elegidas.map((c) => seleccion[c.pedido_id].monto))
  const monto = montoManual ?? (elegidas.length ? aTextoBs(aplicado) : '')
  const diferencias = sumarBs(
    elegidas.filter((c) => seleccion[c.pedido_id].cerrar).map((c) => Number(c.saldo) - Number(seleccion[c.pedido_id].monto || 0)),
  )
  const cuadrado = elegidas.length > 0 && cuadra(elegidas.map((c) => seleccion[c.pedido_id].monto), monto)

  const alternar = (lista: CuentaPorCobrar[], marcar: boolean) =>
    setSeleccion((s) => {
      const nueva = { ...s }
      for (const c of lista) {
        if (marcar) nueva[c.pedido_id] ??= { monto: c.saldo, cerrar: false, motivo: '' }
        else delete nueva[c.pedido_id]
      }
      return nueva
    })
  const actualizar = (id: string, cambio: Partial<Aplicacion>) => setSeleccion((s) => ({ ...s, [id]: { ...s[id], ...cambio } }))

  const registrar = useMutation({
    mutationFn: async () => {
      const cobro = await api<CobroDetalle>('/finanzas/cobros', {
        metodo: 'POST',
        cuerpo: {
          cadena_id: cadena,
          fecha: cabecera.fecha,
          monto,
          banco: cabecera.banco || null,
          referencia: cabecera.referencia || null,
          observaciones: cabecera.observaciones || null,
          detalles: elegidas.map((c) => {
            const a = seleccion[c.pedido_id]
            const falta = Number(a.monto || 0) < Number(c.saldo)
            return {
              pedido_id: c.pedido_id,
              monto: a.monto || '0',
              cerrar_diferencia: falta && a.cerrar,
              motivo_diferencia: falta && a.cerrar ? a.motivo : null,
            }
          }),
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
      navegar('/finanzas?pestana=cobros', { replace: true })
    },
  })

  return (
    <>
      <Link to="/finanzas" className="mb-2 inline-flex items-center gap-1 text-sm text-slate-600 hover:text-slate-900">
        <ArrowLeft size={16} /> Finanzas
      </Link>
      <Encabezado
        titulo="Registrar cobro"
        descripcion="Anote la transferencia que hizo el supermercado y marque los pedidos que paga (normalmente, todo lo de un mes)."
      />
      <form
        className="space-y-5"
        onSubmit={(e) => {
          e.preventDefault()
          registrar.mutate()
        }}
      >
        <Tarjeta className="grid gap-4 p-4 sm:grid-cols-2 lg:grid-cols-3">
          <Campo etiqueta="Cadena">
            <Selector
              required
              value={cadena}
              onChange={(e) => {
                setCadena(e.target.value)
                setSeleccion({})
                setMontoManual(null)
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
          <Campo etiqueta="Fecha de la transferencia">
            <Entrada type="date" required max={hoyLaPaz()} value={cabecera.fecha} onChange={(e) => setCabecera((c) => ({ ...c, fecha: e.target.value }))} />
          </Campo>
          <Campo etiqueta="Monto transferido (Bs)" ayuda={montoManual === null ? 'Se calcula con los pedidos marcados; puede cambiarlo.' : undefined}>
            <Entrada required inputMode="decimal" value={monto} onChange={(e) => setMontoManual(e.target.value.replace(',', '.'))} />
          </Campo>
          <Campo etiqueta="Banco (opcional)">
            <Entrada maxLength={80} value={cabecera.banco} onChange={(e) => setCabecera((c) => ({ ...c, banco: e.target.value }))} />
          </Campo>
          <Campo etiqueta="N.º de operación (opcional)" ayuda="Evita registrar dos veces la misma transferencia.">
            <Entrada maxLength={60} value={cabecera.referencia} onChange={(e) => setCabecera((c) => ({ ...c, referencia: e.target.value }))} />
          </Campo>
          <Campo etiqueta="Comprobante (foto o PDF, opcional)">
            <input type="file" accept="image/*,application/pdf" className="block w-full text-sm" onChange={(e) => setArchivo(e.target.files?.[0] ?? null)} />
          </Campo>
        </Tarjeta>

        {pendientes.isError && <Aviso>{mensajeError(pendientes.error)}</Aviso>}
        {cadena && pendientes.data && cuentas.length === 0 && <Vacio>Esta cadena no tiene pedidos entregados pendientes de cobro.</Vacio>}
        {agruparPorMes(cuentas, (c) => c.fecha).map(([mes, lista]) => {
          const todos = lista.every((c) => seleccion[c.pedido_id])
          return (
            <section key={mes} className="space-y-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <Casilla
                  etiqueta={`Entregas de ${nombreMes(mes)}`}
                  descripcion={`${lista.length} pedido(s) · ${formatearBs(sumarBs(lista.map((c) => c.saldo)))}`}
                  checked={todos}
                  onChange={(e) => alternar(lista, e.target.checked)}
                />
              </div>
              <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white">
                {lista.map((c) => {
                  const a = seleccion[c.pedido_id]
                  const falta = a ? Number(c.saldo) - Number(a.monto || 0) : 0
                  return (
                    <li key={c.pedido_id} className="space-y-2 px-3 py-2">
                      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                        <input
                          type="checkbox"
                          aria-label={`Cobrar pedido ${c.numero}`}
                          className="size-4 accent-marca-700"
                          checked={!!a}
                          onChange={(e) => alternar([c], e.target.checked)}
                        />
                        <div className="min-w-0 flex-1 text-sm">
                          <span className="font-medium">#{c.numero}</span>
                          {c.numero_oc && <span className="text-slate-500"> · O/C {c.numero_oc}</span>}
                          <div className="text-xs text-slate-500">
                            {c.sucursal ?? c.cadena.nombre} · entregado {formatearDia(c.fecha)}
                          </div>
                        </div>
                        <div className="text-right text-sm tabular-nums">
                          {formatearBs(c.saldo)}
                          <div>
                            <InsigniaCuenta cuenta={c} />
                          </div>
                        </div>
                      </div>
                      {a && (
                        <div className="grid gap-2 pl-7 sm:grid-cols-[10rem_1fr]">
                          <Campo etiqueta="Pagaron (Bs)">
                            <Entrada inputMode="decimal" required value={a.monto} onChange={(e) => actualizar(c.pedido_id, { monto: e.target.value.replace(',', '.') })} />
                          </Campo>
                          {falta > 0.004 && (
                            <div className="space-y-1 self-end text-sm">
                              <p className="text-amber-800">Faltan {formatearBs(falta)}.</p>
                              <Casilla
                                etiqueta="No lo van a pagar: cerrar la diferencia"
                                descripcion="Si no la marca, el pedido queda con ese saldo pendiente."
                                checked={a.cerrar}
                                onChange={(e) => actualizar(c.pedido_id, { cerrar: e.target.checked })}
                              />
                              {a.cerrar && (
                                <Entrada
                                  required
                                  minLength={3}
                                  maxLength={300}
                                  placeholder="Motivo (p. ej. error en la factura)"
                                  value={a.motivo}
                                  onChange={(e) => actualizar(c.pedido_id, { motivo: e.target.value })}
                                />
                              )}
                            </div>
                          )}
                        </div>
                      )}
                    </li>
                  )
                })}
              </ul>
            </section>
          )
        })}

        <Campo etiqueta="Observaciones (opcional)">
          <Entrada maxLength={500} value={cabecera.observaciones} onChange={(e) => setCabecera((c) => ({ ...c, observaciones: e.target.value }))} />
        </Campo>

        <Tarjeta className="flex flex-wrap items-center justify-between gap-3 p-4">
          <div className="space-y-0.5 text-sm">
            <p>
              {elegidas.length} pedido(s) · aplicado <strong className="tabular-nums">{formatearBs(aplicado)}</strong> de{' '}
              <strong className="tabular-nums">{formatearBs(monto || 0)}</strong> transferidos
            </p>
            {diferencias > 0 && <p className="text-amber-800">Diferencias que se cierran: {formatearBs(diferencias)}</p>}
            {elegidas.length > 0 && !cuadrado && (
              <p className="text-red-700">
                Lo aplicado no coincide con lo transferido (diferencia {formatearBs(Number(monto || 0) - aplicado)}). Ajuste los montos de los pedidos.
              </p>
            )}
          </div>
          <Boton type="submit" disabled={!cuadrado || registrar.isPending}>
            {registrar.isPending ? 'Registrando…' : 'Registrar cobro'}
          </Boton>
        </Tarjeta>
        {registrar.isError && <Aviso>{mensajeError(registrar.error)}</Aviso>}
      </form>
    </>
  )
}
