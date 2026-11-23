import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { BellRing, ScanText, Wallet } from 'lucide-react'
import { useForm } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import { Navigate, useLocation, useNavigate } from 'react-router'
import { z } from 'zod'
import { BotonTema, Marca, SelectorIdioma } from '../components/Controles'
import { Escena } from '../components/escena/Escena'
import { Aviso, Boton, Campo, Entrada } from '../components/ui'
import { api, ErrorApi, mensajeError } from '../lib/api'
import { CLAVE_YO, useYo } from '../lib/sesion'
import type { UsuarioYo } from '../lib/tipos'

const esquema = z.object({
  correo: z.email('Ingrese un correo válido.'),
  password: z.string().min(1, 'Ingrese su contraseña.'),
})
type Datos = z.infer<typeof esquema>

const HECHOS = [
  { icono: ScanText, texto: 'Lee sola las notas de recepción' },
  { icono: BellRing, texto: 'Avisa cuando algo se acaba' },
  { icono: Wallet, texto: 'Cobros por empresa' },
]

export function Login() {
  const { t } = useTranslation()
  const { data: yo } = useYo()
  const queryClient = useQueryClient()
  const navegar = useNavigate()
  const ubicacion = useLocation()
  const destino = (ubicacion.state as { desde?: string } | null)?.desde ?? '/'

  const form = useForm<Datos>({ resolver: zodResolver(esquema) })
  const ingresar = useMutation({
    mutationFn: async (d: Datos) => {
      const usuario = await api<UsuarioYo>('/auth/login', { metodo: 'POST', cuerpo: d })
      // La cookie de sesión es "Secure": si se entra por http (p. ej. la IP de la red local),
      // el navegador la descarta y cada pantalla volvería al login. Se comprueba aquí.
      try {
        await api<UsuarioYo>('/auth/yo')
      } catch (e) {
        if (e instanceof ErrorApi && e.status === 401) {
          throw new ErrorApi(
            400,
            'sesion_no_guardada',
            t('El navegador no guardó la sesión porque esta dirección no es segura (http). Ingrese por el enlace https del sistema.'),
          )
        }
        throw e
      }
      return usuario
    },
    onSuccess: (usuario) => {
      queryClient.setQueryData(CLAVE_YO, usuario)
      navegar(destino, { replace: true })
    },
  })

  if (yo) return <Navigate to={destino} replace />
  const error = (m?: string) => (m ? t(m) : undefined)

  return (
    <div className="grid min-h-dvh grid-rows-[12rem_1fr] bg-lienzo md:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)] md:grid-rows-1">
      {/* Escena y mensaje del sistema */}
      <section
        className="relative overflow-hidden border-b border-linea md:border-r md:border-b-0"
        style={{ background: 'radial-gradient(120% 90% at 20% 10%, var(--escena-fondo-1) 0%, var(--escena-fondo-2) 55%, var(--escena-fondo-3) 100%)' }}
      >
        <Escena variante="login" className="absolute inset-0 md:inset-x-0 md:top-0 md:bottom-[34%]" />
        <div className="absolute top-5 left-5 flex items-center gap-2.5 md:top-8 md:left-10">
          <Marca tamano={32} />
          <span className="text-[15px] font-semibold tracking-[-0.2px]">{t('Inventario')}</span>
        </div>
        <div className="absolute inset-x-10 bottom-10 hidden max-w-lg animate-[entra_.6s_var(--ease-entrada)_.1s_both] md:block">
          <h1 className="text-[34px] leading-[1.12] font-semibold tracking-[-0.8px] text-tinta">{t('Stock, pedidos y cobros de la distribuidora, al día.')}</h1>
          <p className="mt-3 text-[15px] text-tinta-2">
            {t('Del pedido del supermercado a la transferencia cobrada: todo queda registrado, con su responsable.')}
          </p>
          <ul className="mt-5 flex flex-wrap gap-2">
            {HECHOS.map((h) => (
              <li key={h.texto} className="inline-flex items-center gap-1.5 rounded-lg border border-linea bg-superficie/80 px-2.5 py-1.5 text-[13px] font-medium text-tinta-2 backdrop-blur">
                <h.icono size={15} aria-hidden className="text-acento" />
                {t(h.texto)}
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* Formulario */}
      <section className="flex flex-col px-5 py-4 md:px-10 md:py-6">
        <div className="flex justify-end gap-2">
          <SelectorIdioma />
          <BotonTema />
        </div>
        <div className="mx-auto my-8 w-full max-w-sm animate-[entra_.5s_var(--ease-entrada)_both] md:my-auto">
          <h2 className="text-2xl font-semibold tracking-[-0.4px]">{t('Ingresar')}</h2>
          <p className="mt-1 mb-7 text-sm text-tinta-3">{t('Con su cuenta de trabajo.')}</p>
          <form onSubmit={form.handleSubmit((d) => ingresar.mutate(d))} className="space-y-4" noValidate>
            {ingresar.isError && <Aviso>{mensajeError(ingresar.error)}</Aviso>}
            <Campo etiqueta={t('Correo')} error={error(form.formState.errors.correo?.message)}>
              <Entrada type="email" autoComplete="username" spellCheck={false} className="min-h-11" {...form.register('correo')} />
            </Campo>
            <Campo etiqueta={t('Contraseña')} error={error(form.formState.errors.password?.message)}>
              <Entrada type="password" autoComplete="current-password" className="min-h-11" {...form.register('password')} />
            </Campo>
            <Boton type="submit" className="mt-2 min-h-11 w-full" disabled={ingresar.isPending}>
              {ingresar.isPending ? t('Ingresando…') : t('Ingresar')}
            </Boton>
          </form>
        </div>
        <p className="text-center text-xs text-tinta-3">{t('Distribuidora · La Paz')}</p>
      </section>
    </div>
  )
}
