import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { Navigate, useLocation, useNavigate } from 'react-router'
import { z } from 'zod'
import { Aviso, Boton, Campo, Entrada, Tarjeta } from '../components/ui'
import { api, ErrorApi, mensajeError } from '../lib/api'
import { CLAVE_YO, useYo } from '../lib/sesion'
import type { UsuarioYo } from '../lib/tipos'

const esquema = z.object({
  correo: z.email('Ingrese un correo válido.'),
  password: z.string().min(1, 'Ingrese su contraseña.'),
})
type Datos = z.infer<typeof esquema>

export function Login() {
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
            'El navegador no guardó la sesión porque esta dirección no es segura (http). ' +
              'Ingrese por el enlace https del sistema.',
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

  return (
    <div className="flex min-h-dvh items-center justify-center bg-slate-100 px-4">
      <Tarjeta className="w-full max-w-sm p-6 sm:p-8">
        <div className="mb-6 flex flex-col items-center gap-3 text-center">
          <img src="/icono.svg" alt="" className="size-12" />
          <div>
            <h1 className="text-xl font-semibold">Sistema de Inventario</h1>
            <p className="text-sm text-slate-600">Ingrese con su cuenta de trabajo</p>
          </div>
        </div>
        <form onSubmit={form.handleSubmit((d) => ingresar.mutate(d))} className="space-y-4" noValidate>
          {ingresar.isError && <Aviso>{mensajeError(ingresar.error)}</Aviso>}
          <Campo etiqueta="Correo" error={form.formState.errors.correo?.message}>
            <Entrada type="email" autoComplete="username" autoFocus {...form.register('correo')} />
          </Campo>
          <Campo etiqueta="Contraseña" error={form.formState.errors.password?.message}>
            <Entrada type="password" autoComplete="current-password" {...form.register('password')} />
          </Campo>
          <Boton type="submit" className="w-full" disabled={ingresar.isPending}>
            {ingresar.isPending ? 'Ingresando…' : 'Ingresar'}
          </Boton>
        </form>
      </Tarjeta>
    </div>
  )
}
