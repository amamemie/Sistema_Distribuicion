import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, X } from 'lucide-react'
import { useState } from 'react'
import { SelectorProducto } from '../../components/SelectorProducto'
import { Aviso, Boton, CABECERA_TABLA, Campo, Casilla, Encabezado, Entrada, Insignia, Modal, Tabla, Vacio } from '../../components/ui'
import { api, mensajeError } from '../../lib/api'
import { useProveedores } from '../../lib/consultas'
import { usePuede } from '../../lib/sesion'
import type { Proveedor } from '../../lib/tipos'

const CAMPOS = [
  ['nombre', 'Nombre o razón social'],
  ['nit', 'NIT'],
  ['telefono', 'Teléfono'],
  ['correo', 'Correo'],
  ['contacto', 'Persona de contacto'],
  ['direccion', 'Dirección'],
] as const

export function Proveedores() {
  const puede = usePuede()
  const proveedores = useProveedores()
  const [editando, setEditando] = useState<Proveedor | 'nuevo' | null>(null)

  return (
    <>
      <Encabezado
        titulo="Proveedores"
        descripcion="Empresas que abastecen a la distribuidora y los productos que proveen."
        acciones={
          puede('proveedores.gestionar') && (
            <Boton onClick={() => setEditando('nuevo')}>
              <Plus size={16} /> Nuevo proveedor
            </Boton>
          )
        }
      />
      {proveedores.isError && <Aviso>{mensajeError(proveedores.error)}</Aviso>}
      {proveedores.data?.length === 0 && <Vacio>Todavía no hay proveedores registrados.</Vacio>}
      {!!proveedores.data?.length && (
        <Tabla>
          <thead className={CABECERA_TABLA}>
            <tr>
              <th>Proveedor</th>
              <th className="hidden md:table-cell">Contacto</th>
              <th className="hidden sm:table-cell">Productos</th>
              <th>Estado</th>
              <th />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {proveedores.data.map((p) => (
              <tr key={p.id}>
                <td>
                  <div className="font-medium">{p.nombre}</div>
                  <div className="text-xs text-slate-500">{p.nit ? `NIT ${p.nit}` : 'Sin NIT'}</div>
                </td>
                <td className="hidden text-slate-600 md:table-cell">
                  {p.contacto ?? '—'}
                  {p.telefono && <div className="text-xs">{p.telefono}</div>}
                </td>
                <td className="hidden text-slate-600 sm:table-cell">{p.productos.length}</td>
                <td>{p.activo ? <Insignia tono="verde">Activo</Insignia> : <Insignia tono="rojo">Inactivo</Insignia>}</td>
                <td className="text-right">
                  {puede('proveedores.gestionar') && (
                    <Boton variante="fantasma" onClick={() => setEditando(p)}>
                      Editar
                    </Boton>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </Tabla>
      )}
      {editando && <FormularioProveedor proveedor={editando === 'nuevo' ? null : editando} onCerrar={() => setEditando(null)} />}
    </>
  )
}

function FormularioProveedor({ proveedor, onCerrar }: { proveedor: Proveedor | null; onCerrar: () => void }) {
  const queryClient = useQueryClient()
  const [datos, setDatos] = useState<Record<string, string>>(
    Object.fromEntries(CAMPOS.map(([c]) => [c, (proveedor?.[c] as string | null) ?? ''])),
  )
  const [activo, setActivo] = useState(proveedor?.activo ?? true)
  const [diasEntrega, setDiasEntrega] = useState(proveedor?.dias_entrega?.toString() ?? '')
  const [productos, setProductos] = useState(proveedor?.productos ?? [])

  const guardar = useMutation({
    mutationFn: () => {
      const cuerpo = {
        ...Object.fromEntries(CAMPOS.map(([c]) => [c, datos[c].trim() || null])),
        producto_ids: productos.map((p) => p.id),
        dias_entrega: diasEntrega === '' ? null : Number(diasEntrega),
      }
      return proveedor
        ? api(`/proveedores/${proveedor.id}`, { metodo: 'PATCH', cuerpo: { ...cuerpo, activo } })
        : api('/proveedores', { metodo: 'POST', cuerpo })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['proveedores'] })
      onCerrar()
    },
  })

  return (
    <Modal abierto titulo={proveedor ? 'Editar proveedor' : 'Nuevo proveedor'} onCerrar={onCerrar}>
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault()
          guardar.mutate()
        }}
      >
        {guardar.isError && <Aviso>{mensajeError(guardar.error)}</Aviso>}
        <div className="grid gap-4 sm:grid-cols-2">
          {CAMPOS.map(([campo, etiqueta]) => (
            <Campo key={campo} etiqueta={etiqueta}>
              <Entrada required={campo === 'nombre'} value={datos[campo]} onChange={(e) => setDatos((d) => ({ ...d, [campo]: e.target.value }))} />
            </Campo>
          ))}
          <Campo etiqueta="Días que tarda en entregar" ayuda="Vacío: se usa el valor general de Reposición.">
            <Entrada type="number" min={0} max={180} value={diasEntrega} onChange={(e) => setDiasEntrega(e.target.value)} />
          </Campo>
        </div>
        <div className="space-y-2">
          <span className="text-sm font-medium text-slate-700">Productos que provee</span>
          <div className="flex flex-wrap gap-1">
            {productos.map((p) => (
              <span key={p.id} className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-1 text-xs">
                {p.nombre}
                <button type="button" aria-label={`Quitar ${p.nombre}`} onClick={() => setProductos((l) => l.filter((x) => x.id !== p.id))}>
                  <X size={12} />
                </button>
              </span>
            ))}
          </div>
          <SelectorProducto
            valor={null}
            onCambio={(p) => p && !productos.some((x) => x.id === p.id) && setProductos((l) => [...l, { id: p.id, sku: p.sku, nombre: p.nombre }])}
          />
        </div>
        {proveedor && <Casilla etiqueta="Proveedor activo" checked={activo} onChange={(e) => setActivo(e.target.checked)} />}
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
