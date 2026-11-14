import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Store } from 'lucide-react'
import { useState } from 'react'
import { Aviso, Boton, Campo, Casilla, Encabezado, Entrada, Insignia, Modal, Tarjeta, Vacio } from '../../components/ui'
import { api, mensajeError } from '../../lib/api'
import { useCadenas } from '../../lib/consultas'
import { usePuede } from '../../lib/sesion'
import type { Cadena, SucursalCliente } from '../../lib/tipos'

type Edicion =
  | { tipo: 'cadena'; cadena: Cadena | null }
  | { tipo: 'sucursal'; cadena: Cadena; sucursal: SucursalCliente | null }

export function Clientes() {
  const puede = usePuede()
  const editable = puede('clientes.gestionar')
  const cadenas = useCadenas()
  const [edicion, setEdicion] = useState<Edicion | null>(null)

  return (
    <>
      <Encabezado
        titulo="Clientes"
        descripcion="Cadenas de supermercados y sus sucursales. El precio de venta es por cadena."
        acciones={
          editable && (
            <Boton onClick={() => setEdicion({ tipo: 'cadena', cadena: null })}>
              <Plus size={16} /> Nueva cadena
            </Boton>
          )
        }
      />
      {cadenas.isError && <Aviso>{mensajeError(cadenas.error)}</Aviso>}
      {cadenas.data?.length === 0 && <Vacio>Todavía no hay cadenas registradas.</Vacio>}
      <div className="grid gap-4 md:grid-cols-2">
        {cadenas.data?.map((c) => (
          <Tarjeta key={c.id} className="p-4">
            <div className="flex items-start justify-between gap-2">
              <div>
                <h2 className="font-semibold">{c.nombre}</h2>
                <p className="text-xs text-slate-500">
                  {c.nit ? `NIT ${c.nit}` : 'Sin NIT'}
                  {c.contacto && ` · ${c.contacto}`}
                </p>
              </div>
              <div className="flex items-center gap-1">
                {!c.activo && <Insignia tono="rojo">Inactiva</Insignia>}
                {editable && (
                  <Boton variante="fantasma" className="min-h-8 px-2" onClick={() => setEdicion({ tipo: 'cadena', cadena: c })}>
                    Editar
                  </Boton>
                )}
              </div>
            </div>
            <ul className="mt-3 divide-y divide-slate-100">
              {c.sucursales.map((s) => (
                <li key={s.id} className="flex items-center justify-between gap-2 py-2 text-sm">
                  <span className={`flex items-center gap-2 ${s.activo ? '' : 'text-slate-400 line-through'}`}>
                    <Store size={14} className="text-slate-400" />
                    {s.nombre}
                  </span>
                  {editable && (
                    <Boton variante="fantasma" className="min-h-8 px-2" onClick={() => setEdicion({ tipo: 'sucursal', cadena: c, sucursal: s })}>
                      Editar
                    </Boton>
                  )}
                </li>
              ))}
              {c.sucursales.length === 0 && <li className="py-2 text-sm text-slate-500">Sin sucursales</li>}
            </ul>
            {editable && (
              <Boton variante="secundario" className="mt-2" onClick={() => setEdicion({ tipo: 'sucursal', cadena: c, sucursal: null })}>
                <Plus size={16} /> Agregar sucursal
              </Boton>
            )}
          </Tarjeta>
        ))}
      </div>
      {edicion && <FormularioCliente edicion={edicion} onCerrar={() => setEdicion(null)} />}
    </>
  )
}

function FormularioCliente({ edicion, onCerrar }: { edicion: Edicion; onCerrar: () => void }) {
  const queryClient = useQueryClient()
  const esCadena = edicion.tipo === 'cadena'
  const actual = esCadena ? edicion.cadena : edicion.sucursal
  const campos = esCadena
    ? ([['nombre', 'Nombre de la cadena'], ['nit', 'NIT'], ['telefono', 'Teléfono'], ['correo', 'Correo'], ['contacto', 'Contacto']] as const)
    : ([['nombre', 'Nombre de la sucursal'], ['direccion', 'Dirección'], ['telefono', 'Teléfono'], ['contacto', 'Contacto']] as const)
  const [datos, setDatos] = useState<Record<string, string>>(
    Object.fromEntries(campos.map(([c]) => [c, ((actual as unknown as Record<string, string | null>) ?? {})[c] ?? ''])),
  )
  const [activo, setActivo] = useState(actual?.activo ?? true)

  const guardar = useMutation({
    mutationFn: () => {
      const cuerpo = Object.fromEntries(campos.map(([c]) => [c, datos[c].trim() || null]))
      if (esCadena) {
        return actual
          ? api(`/cadenas/${actual.id}`, { metodo: 'PATCH', cuerpo: { ...cuerpo, activo } })
          : api('/cadenas', { metodo: 'POST', cuerpo })
      }
      return actual
        ? api(`/sucursales-cliente/${actual.id}`, { metodo: 'PATCH', cuerpo: { ...cuerpo, activo } })
        : api(`/cadenas/${edicion.cadena.id}/sucursales`, { metodo: 'POST', cuerpo })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cadenas'] })
      onCerrar()
    },
  })

  const titulo = esCadena
    ? actual ? 'Editar cadena' : 'Nueva cadena'
    : `${actual ? 'Editar' : 'Nueva'} sucursal de ${edicion.cadena.nombre}`

  return (
    <Modal abierto titulo={titulo} onCerrar={onCerrar}>
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault()
          guardar.mutate()
        }}
      >
        {guardar.isError && <Aviso>{mensajeError(guardar.error)}</Aviso>}
        {campos.map(([campo, etiqueta]) => (
          <Campo key={campo} etiqueta={etiqueta}>
            <Entrada required={campo === 'nombre'} value={datos[campo]} onChange={(e) => setDatos((d) => ({ ...d, [campo]: e.target.value }))} />
          </Campo>
        ))}
        {actual && <Casilla etiqueta="Activo" checked={activo} onChange={(e) => setActivo(e.target.checked)} />}
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
