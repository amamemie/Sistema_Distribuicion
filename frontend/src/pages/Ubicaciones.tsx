import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Aviso, Boton, Campo, Casilla, Encabezado, Entrada, Insignia, Modal, Selector, Tabla } from '../components/ui'
import { api, mensajeError } from '../lib/api'
import { NOMBRE_TIPO_UBICACION, type TipoUbicacion, type Ubicacion } from '../lib/tipos'

interface Formulario {
  nombre: string
  tipo: TipoUbicacion
  direccion: string
  telefono: string
  activo: boolean
}

export function Ubicaciones() {
  const [editando, setEditando] = useState<Ubicacion | 'nueva' | null>(null)
  const ubicaciones = useQuery({ queryKey: ['ubicaciones'], queryFn: () => api<Ubicacion[]>('/ubicaciones') })

  return (
    <>
      <Encabezado
        titulo="Ubicaciones"
        descripcion="Depósitos (guardan mercadería) y sucursales (alistan y despachan pedidos)."
        acciones={
          <Boton onClick={() => setEditando('nueva')}>
            <Plus size={16} /> Nueva ubicación
          </Boton>
        }
      />
      {ubicaciones.isError && <Aviso>{mensajeError(ubicaciones.error)}</Aviso>}
      <Tabla>
        <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-500">
          <tr>
            <th>Nombre</th>
            <th>Tipo</th>
            <th className="hidden sm:table-cell">Dirección</th>
            <th>Estado</th>
            <th />
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {ubicaciones.data?.map((u) => (
            <tr key={u.id}>
              <td className="font-medium">{u.nombre}</td>
              <td>
                <Insignia tono={u.tipo === 'DEPOSITO' ? 'ambar' : 'azul'}>{NOMBRE_TIPO_UBICACION[u.tipo]}</Insignia>
              </td>
              <td className="hidden text-slate-600 sm:table-cell">{u.direccion ?? '—'}</td>
              <td>{u.activo ? <Insignia tono="verde">Activa</Insignia> : <Insignia tono="rojo">Inactiva</Insignia>}</td>
              <td className="text-right">
                <Boton variante="fantasma" onClick={() => setEditando(u)}>
                  Editar
                </Boton>
              </td>
            </tr>
          ))}
        </tbody>
      </Tabla>
      {editando && (
        <FormularioUbicacion ubicacion={editando === 'nueva' ? null : editando} onCerrar={() => setEditando(null)} />
      )}
    </>
  )
}

function FormularioUbicacion({ ubicacion, onCerrar }: { ubicacion: Ubicacion | null; onCerrar: () => void }) {
  const queryClient = useQueryClient()
  const form = useForm<Formulario>({
    defaultValues: {
      nombre: ubicacion?.nombre ?? '',
      tipo: ubicacion?.tipo ?? 'SUCURSAL',
      direccion: ubicacion?.direccion ?? '',
      telefono: ubicacion?.telefono ?? '',
      activo: ubicacion?.activo ?? true,
    },
  })
  const guardar = useMutation({
    mutationFn: (d: Formulario) => {
      const comun = { nombre: d.nombre, direccion: d.direccion || null, telefono: d.telefono || null }
      return ubicacion
        ? api(`/ubicaciones/${ubicacion.id}`, { metodo: 'PATCH', cuerpo: { ...comun, activo: d.activo } })
        : api('/ubicaciones', { metodo: 'POST', cuerpo: { ...comun, tipo: d.tipo } })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ubicaciones'] })
      onCerrar()
    },
  })

  return (
    <Modal abierto titulo={ubicacion ? 'Editar ubicación' : 'Nueva ubicación'} onCerrar={onCerrar}>
      <form onSubmit={form.handleSubmit((d) => guardar.mutate(d))} className="space-y-4">
        {guardar.isError && <Aviso>{mensajeError(guardar.error)}</Aviso>}
        <Campo etiqueta="Nombre" error={form.formState.errors.nombre?.message}>
          <Entrada {...form.register('nombre', { required: 'Obligatorio.', minLength: { value: 2, message: 'Muy corto.' } })} />
        </Campo>
        <Campo
          etiqueta="Tipo"
          ayuda={ubicacion ? 'El tipo no se puede cambiar una vez creada la ubicación.' : undefined}
        >
          <Selector disabled={!!ubicacion} {...form.register('tipo')}>
            <option value="SUCURSAL">Sucursal (alista y despacha pedidos)</option>
            <option value="DEPOSITO">Depósito (almacena; abastece a sucursales)</option>
          </Selector>
        </Campo>
        <Campo etiqueta="Dirección">
          <Entrada {...form.register('direccion')} />
        </Campo>
        <Campo etiqueta="Teléfono">
          <Entrada type="tel" {...form.register('telefono')} />
        </Campo>
        {ubicacion && <Casilla etiqueta="Ubicación activa" {...form.register('activo')} />}
        <div className="flex justify-end gap-2">
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
