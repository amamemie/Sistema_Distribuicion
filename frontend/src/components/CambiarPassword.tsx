import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { api, mensajeError } from '../lib/api'
import { Aviso, Boton, Campo, Entrada, Modal } from './ui'
import { useTranslation } from 'react-i18next'

const esquema = z
  .object({
    password_actual: z.string().min(1, 'Ingrese su contraseña actual.'),
    password_nueva: z.string().min(10, 'Debe tener al menos 10 caracteres.'),
    confirmacion: z.string(),
  })
  .refine((d) => d.password_nueva === d.confirmacion, {
    message: 'Las contraseñas no coinciden.',
    path: ['confirmacion'],
  })

type Datos = z.infer<typeof esquema>

export function CambiarPassword({ abierto, onCerrar }: { abierto: boolean; onCerrar: () => void }) {
  const { t } = useTranslation()
  const form = useForm<Datos>({ resolver: zodResolver(esquema) })
  const cambiar = useMutation({
    mutationFn: (d: Datos) =>
      api<void>('/auth/cambiar-password', {
        metodo: 'POST',
        cuerpo: { password_actual: d.password_actual, password_nueva: d.password_nueva },
      }),
  })

  const cerrar = () => {
    form.reset()
    cambiar.reset()
    onCerrar()
  }

  return (
    <Modal abierto={abierto} titulo={t("Cambiar contraseña")} onCerrar={cerrar}>
      {cambiar.isSuccess ? (
        <div className="space-y-4">
          <Aviso tipo="exito">{t("Contraseña actualizada. Sus otras sesiones se cerraron.")}</Aviso>
          <Boton onClick={cerrar}>{t("Listo")}</Boton>
        </div>
      ) : (
        <form onSubmit={form.handleSubmit((d) => cambiar.mutate(d))} className="space-y-4">
          {cambiar.isError && <Aviso>{mensajeError(cambiar.error)}</Aviso>}
          <Campo etiqueta={t("Contraseña actual")} error={form.formState.errors.password_actual?.message}>
            <Entrada type="password" autoComplete="current-password" {...form.register('password_actual')} />
          </Campo>
          <Campo etiqueta={t("Nueva contraseña")} error={form.formState.errors.password_nueva?.message}>
            <Entrada type="password" autoComplete="new-password" {...form.register('password_nueva')} />
          </Campo>
          <Campo etiqueta={t("Repita la nueva contraseña")} error={form.formState.errors.confirmacion?.message}>
            <Entrada type="password" autoComplete="new-password" {...form.register('confirmacion')} />
          </Campo>
          <div className="flex justify-end gap-2">
            <Boton variante="secundario" onClick={cerrar}>
              {t("Cancelar")}
            </Boton>
            <Boton type="submit" disabled={cambiar.isPending}>
              {t("Guardar")}
            </Boton>
          </div>
        </form>
      )}
    </Modal>
  )
}
