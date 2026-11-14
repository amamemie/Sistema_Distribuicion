import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { useState } from 'react'
import { useForm, useWatch } from 'react-hook-form'
import {
  Aviso,
  Boton,
  Campo,
  Casilla,
  Encabezado,
  Entrada,
  Insignia,
  Modal,
  Selector,
  Tabla,
} from '../components/ui'
import { api, ErrorApi, mensajeError } from '../lib/api'
import { formatearFecha } from '../lib/formato'
import { usePuede } from '../lib/sesion'
import { NOMBRE_TIPO_UBICACION, type Rol, type Ubicacion, type Usuario } from '../lib/tipos'

interface Formulario {
  nombre: string
  apellido: string
  correo: string
  telefono: string
  password: string
  activo: boolean
  rol_ids: string[]
  ubicacion_ids: string[]
  ubicacion_predeterminada_id: string
}

export function Usuarios() {
  const puede = usePuede()
  const [editando, setEditando] = useState<Usuario | 'nuevo' | null>(null)
  const [restableciendo, setRestableciendo] = useState<Usuario | null>(null)
  const usuarios = useQuery({ queryKey: ['usuarios'], queryFn: () => api<Usuario[]>('/usuarios') })

  return (
    <>
      <Encabezado
        titulo="Usuarios"
        descripcion="Trabajadores con acceso al sistema, sus roles y ubicaciones."
        acciones={
          puede('usuarios.gestionar') && (
            <Boton onClick={() => setEditando('nuevo')}>
              <Plus size={16} /> Nuevo usuario
            </Boton>
          )
        }
      />
      {usuarios.isError && <Aviso>{mensajeError(usuarios.error)}</Aviso>}
      <Tabla>
        <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-500">
          <tr>
            <th>Nombre</th>
            <th>Roles</th>
            <th className="hidden md:table-cell">Ubicaciones</th>
            <th>Estado</th>
            <th className="hidden md:table-cell">Último acceso</th>
            <th />
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {usuarios.data?.map((u) => (
            <tr key={u.id}>
              <td>
                <div className="font-medium">
                  {u.nombre} {u.apellido}
                </div>
                <div className="text-xs text-slate-500">{u.correo}</div>
              </td>
              <td>
                <div className="flex flex-wrap gap-1">
                  {u.roles.map((r) => (
                    <Insignia key={r.id} tono="azul">
                      {r.nombre}
                    </Insignia>
                  ))}
                </div>
              </td>
              <td className="hidden text-slate-600 md:table-cell">
                {u.ubicaciones.map((x) => x.nombre).join(', ') || '—'}
              </td>
              <td>
                {u.activo ? <Insignia tono="verde">Activo</Insignia> : <Insignia tono="rojo">Inactivo</Insignia>}
              </td>
              <td className="hidden text-slate-600 md:table-cell">{formatearFecha(u.ultimo_acceso)}</td>
              <td className="text-right whitespace-nowrap">
                {puede('usuarios.gestionar') && (
                  <>
                    <Boton variante="fantasma" onClick={() => setEditando(u)}>
                      Editar
                    </Boton>
                    <Boton variante="fantasma" onClick={() => setRestableciendo(u)}>
                      Clave
                    </Boton>
                  </>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </Tabla>
      {editando && <FormularioUsuario usuario={editando === 'nuevo' ? null : editando} onCerrar={() => setEditando(null)} />}
      {restableciendo && (
        <RestablecerClave usuario={restableciendo} onCerrar={() => setRestableciendo(null)} />
      )}
    </>
  )
}

function FormularioUsuario({ usuario, onCerrar }: { usuario: Usuario | null; onCerrar: () => void }) {
  const queryClient = useQueryClient()
  const roles = useQuery({ queryKey: ['roles'], queryFn: () => api<Rol[]>('/roles') })
  const ubicaciones = useQuery({
    queryKey: ['ubicaciones'],
    queryFn: () => api<Ubicacion[]>('/ubicaciones'),
  })
  const form = useForm<Formulario>({
    defaultValues: {
      nombre: usuario?.nombre ?? '',
      apellido: usuario?.apellido ?? '',
      correo: usuario?.correo ?? '',
      telefono: usuario?.telefono ?? '',
      password: '',
      activo: usuario?.activo ?? true,
      rol_ids: usuario?.roles.map((r) => r.id) ?? [],
      ubicacion_ids: usuario?.ubicaciones.map((u) => u.id) ?? [],
      ubicacion_predeterminada_id: usuario?.ubicacion_predeterminada_id ?? '',
    },
  })
  const seleccionadas = useWatch({ control: form.control, name: 'ubicacion_ids' })

  const guardar = useMutation({
    mutationFn: (d: Formulario) => {
      const cuerpo = {
        nombre: d.nombre,
        apellido: d.apellido,
        correo: d.correo,
        telefono: d.telefono || null,
        rol_ids: d.rol_ids,
        ubicacion_ids: d.ubicacion_ids,
        ubicacion_predeterminada_id: seleccionadas.includes(d.ubicacion_predeterminada_id)
          ? d.ubicacion_predeterminada_id
          : null,
      }
      return usuario
        ? api<Usuario>(`/usuarios/${usuario.id}`, { metodo: 'PATCH', cuerpo: { ...cuerpo, activo: d.activo } })
        : api<Usuario>('/usuarios', { metodo: 'POST', cuerpo: { ...cuerpo, password: d.password } })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['usuarios'] })
      onCerrar()
    },
    onError: (error) => {
      if (error instanceof ErrorApi) {
        for (const e of error.errores) {
          form.setError(e.campo as keyof Formulario, { message: e.mensaje })
        }
      }
    },
  })
  const errores = form.formState.errors

  return (
    <Modal abierto titulo={usuario ? 'Editar usuario' : 'Nuevo usuario'} onCerrar={onCerrar}>
      <form onSubmit={form.handleSubmit((d) => guardar.mutate(d))} className="space-y-4">
        {guardar.isError && <Aviso>{mensajeError(guardar.error)}</Aviso>}
        <div className="grid gap-4 sm:grid-cols-2">
          <Campo etiqueta="Nombre" error={errores.nombre?.message}>
            <Entrada {...form.register('nombre', { required: 'Obligatorio.' })} />
          </Campo>
          <Campo etiqueta="Apellido" error={errores.apellido?.message}>
            <Entrada {...form.register('apellido', { required: 'Obligatorio.' })} />
          </Campo>
        </div>
        <Campo etiqueta="Correo (usuario de acceso)" error={errores.correo?.message}>
          <Entrada type="email" {...form.register('correo', { required: 'Obligatorio.' })} />
        </Campo>
        <Campo etiqueta="Teléfono" error={errores.telefono?.message}>
          <Entrada type="tel" {...form.register('telefono')} />
        </Campo>
        {!usuario && (
          <Campo etiqueta="Contraseña inicial" error={errores.password?.message} ayuda="Mínimo 10 caracteres.">
            <Entrada
              type="password"
              autoComplete="new-password"
              {...form.register('password', { minLength: { value: 10, message: 'Mínimo 10 caracteres.' } })}
            />
          </Campo>
        )}
        <fieldset>
          <legend className="text-sm font-medium text-slate-700">Roles</legend>
          {roles.data?.map((r) => (
            <Casilla
              key={r.id}
              etiqueta={r.nombre}
              descripcion={r.descripcion ?? undefined}
              value={r.id}
              {...form.register('rol_ids', { validate: (v) => v.length > 0 || 'Elija al menos un rol.' })}
            />
          ))}
          {errores.rol_ids && <p className="text-xs text-red-600">{errores.rol_ids.message}</p>}
        </fieldset>
        <fieldset>
          <legend className="text-sm font-medium text-slate-700">Ubicaciones donde trabaja</legend>
          {ubicaciones.data?.map((u) => (
            <Casilla
              key={u.id}
              etiqueta={u.nombre}
              descripcion={NOMBRE_TIPO_UBICACION[u.tipo]}
              value={u.id}
              {...form.register('ubicacion_ids')}
            />
          ))}
        </fieldset>
        <Campo etiqueta="Ubicación predeterminada" error={errores.ubicacion_predeterminada_id?.message}>
          <Selector {...form.register('ubicacion_predeterminada_id')}>
            <option value="">Ninguna</option>
            {ubicaciones.data
              ?.filter((u) => seleccionadas.includes(u.id))
              .map((u) => (
                <option key={u.id} value={u.id}>
                  {u.nombre}
                </option>
              ))}
          </Selector>
        </Campo>
        {usuario && <Casilla etiqueta="Cuenta activa" {...form.register('activo')} />}
        <div className="flex justify-end gap-2 pt-2">
          <Boton variante="secundario" onClick={onCerrar}>
            Cancelar
          </Boton>
          <Boton type="submit" disabled={guardar.isPending}>
            Guardar
          </Boton>
        </div>
      </form>
    </Modal>
  )
}

function RestablecerClave({ usuario, onCerrar }: { usuario: Usuario; onCerrar: () => void }) {
  const form = useForm<{ password: string }>()
  const restablecer = useMutation({
    mutationFn: (d: { password: string }) =>
      api<void>(`/usuarios/${usuario.id}/restablecer-password`, { metodo: 'POST', cuerpo: d }),
    onSuccess: onCerrar,
  })
  return (
    <Modal abierto titulo={`Restablecer contraseña de ${usuario.nombre}`} onCerrar={onCerrar}>
      <form onSubmit={form.handleSubmit((d) => restablecer.mutate(d))} className="space-y-4">
        {restablecer.isError && <Aviso>{mensajeError(restablecer.error)}</Aviso>}
        <p className="text-sm text-slate-600">
          Se cerrarán todas las sesiones abiertas del usuario. Comuníquele la nueva contraseña por un
          medio seguro.
        </p>
        <Campo etiqueta="Nueva contraseña" error={form.formState.errors.password?.message}>
          <Entrada
            type="password"
            autoComplete="new-password"
            {...form.register('password', { minLength: { value: 10, message: 'Mínimo 10 caracteres.' } })}
          />
        </Campo>
        <div className="flex justify-end gap-2">
          <Boton variante="secundario" onClick={onCerrar}>
            Cancelar
          </Boton>
          <Boton type="submit" disabled={restablecer.isPending}>
            Restablecer
          </Boton>
        </div>
      </form>
    </Modal>
  )
}
