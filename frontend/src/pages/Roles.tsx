import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Lock, Plus } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Aviso, Boton, Casilla, Encabezado, Entrada, Tarjeta } from '../components/ui'
import { api, mensajeError } from '../lib/api'
import { usePuede } from '../lib/sesion'
import type { Permiso, Rol } from '../lib/tipos'

export function Roles() {
  const puede = usePuede()
  const queryClient = useQueryClient()
  const roles = useQuery({ queryKey: ['roles'], queryFn: () => api<Rol[]>('/roles') })
  const permisos = useQuery({ queryKey: ['permisos'], queryFn: () => api<Permiso[]>('/permisos') })
  const [seleccionadoId, setSeleccionadoId] = useState<string | null>(null)
  const [nuevoNombre, setNuevoNombre] = useState('')

  const seleccionado = roles.data?.find((r) => r.id === seleccionadoId) ?? roles.data?.[0]
  const porModulo = useMemo(() => {
    const grupos = new Map<string, Permiso[]>()
    for (const p of permisos.data ?? []) grupos.set(p.modulo, [...(grupos.get(p.modulo) ?? []), p])
    return [...grupos.entries()]
  }, [permisos.data])

  const crear = useMutation({
    mutationFn: (nombre: string) => api<Rol>('/roles', { metodo: 'POST', cuerpo: { nombre, permisos: [] } }),
    onSuccess: (rol) => {
      queryClient.invalidateQueries({ queryKey: ['roles'] })
      setSeleccionadoId(rol.id)
      setNuevoNombre('')
    },
  })

  return (
    <>
      <Encabezado
        titulo="Roles y permisos"
        descripcion="Cada rol es un conjunto de permisos. El rol Dueño siempre tiene acceso total."
      />
      {(roles.isError || crear.isError) && <Aviso>{mensajeError(roles.error ?? crear.error)}</Aviso>}
      <div className="grid gap-4 md:grid-cols-[16rem_1fr]">
        <div className="space-y-3">
          <Tarjeta className="divide-y divide-slate-100">
            {roles.data?.map((r) => (
              <button
                key={r.id}
                onClick={() => setSeleccionadoId(r.id)}
                className={`flex w-full items-center justify-between px-4 py-3 text-left text-sm ${
                  r.id === seleccionado?.id ? 'bg-marca-50 font-medium text-marca-800' : 'hover:bg-slate-50'
                }`}
              >
                {r.nombre}
                {r.es_sistema && <Lock size={14} className="text-slate-400" />}
              </button>
            ))}
          </Tarjeta>
          {puede('roles.gestionar') && (
            <form
              className="flex gap-2"
              onSubmit={(e) => {
                e.preventDefault()
                if (nuevoNombre.trim().length >= 2) crear.mutate(nuevoNombre.trim())
              }}
            >
              <Entrada placeholder="Nombre del nuevo rol" value={nuevoNombre} onChange={(e) => setNuevoNombre(e.target.value)} />
              <Boton type="submit" className="px-3" aria-label="Crear rol" disabled={crear.isPending}>
                <Plus size={16} />
              </Boton>
            </form>
          )}
        </div>
        {seleccionado && (
          <EditorPermisos
            key={seleccionado.id}
            rol={seleccionado}
            porModulo={porModulo}
            editable={puede('roles.gestionar') && !seleccionado.es_sistema}
          />
        )}
      </div>
    </>
  )
}

function EditorPermisos({
  rol,
  porModulo,
  editable,
}: {
  rol: Rol
  porModulo: [string, Permiso[]][]
  editable: boolean
}) {
  const queryClient = useQueryClient()
  const [marcados, setMarcados] = useState(() => new Set(rol.permisos))
  const guardar = useMutation({
    mutationFn: () => api<Rol>(`/roles/${rol.id}`, { metodo: 'PATCH', cuerpo: { permisos: [...marcados] } }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['roles'] }),
  })
  const alternar = (codigo: string) =>
    setMarcados((previo) => {
      const nuevo = new Set(previo)
      if (nuevo.has(codigo)) nuevo.delete(codigo)
      else nuevo.add(codigo)
      return nuevo
    })
  const cambiado = marcados.size !== rol.permisos.length || rol.permisos.some((p) => !marcados.has(p))

  return (
    <Tarjeta className="p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold">{rol.nombre}</h2>
          {rol.descripcion && <p className="text-sm text-slate-600">{rol.descripcion}</p>}
        </div>
        {editable && (
          <Boton onClick={() => guardar.mutate()} disabled={!cambiado || guardar.isPending}>
            Guardar cambios
          </Boton>
        )}
      </div>
      {guardar.isError && <Aviso>{mensajeError(guardar.error)}</Aviso>}
      {guardar.isSuccess && !cambiado && <Aviso tipo="exito">Permisos guardados.</Aviso>}
      <div className="mt-2 grid gap-6 sm:grid-cols-2">
        {porModulo.map(([modulo, lista]) => (
          <fieldset key={modulo}>
            <legend className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">{modulo}</legend>
            {lista.map((p) => (
              <Casilla
                key={p.codigo}
                etiqueta={p.descripcion}
                checked={marcados.has(p.codigo)}
                disabled={!editable}
                onChange={() => alternar(p.codigo)}
              />
            ))}
          </fieldset>
        ))}
      </div>
    </Tarjeta>
  )
}
