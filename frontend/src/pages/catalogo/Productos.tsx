import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import {
  Aviso,
  Boton,
  CABECERA_TABLA,
  Campo,
  Casilla,
  Encabezado,
  Entrada,
  Insignia,
  Modal,
  Paginador,
  Selector,
  Tabla,
} from '../../components/ui'
import { api, mensajeError } from '../../lib/api'
import { useCategorias, useMarcas, useUbicaciones } from '../../lib/consultas'
import { formatearCantidad } from '../../lib/formato'
import { usePuede } from '../../lib/sesion'
import type { Pagina, Producto, ProductoDetalle } from '../../lib/tipos'
import { Clasificacion } from './Clasificacion'

const TAMANO = 50

export function Productos() {
  const puede = usePuede()
  const [pestana, setPestana] = useState<'productos' | 'clasificacion'>('productos')
  const [buscar, setBuscar] = useState('')
  const [categoria, setCategoria] = useState('')
  const [verInactivos, setVerInactivos] = useState(false)
  const [pagina, setPagina] = useState(1)
  const [editando, setEditando] = useState<string | 'nuevo' | null>(null)
  const categorias = useCategorias()

  const productos = useQuery({
    queryKey: ['productos', buscar, categoria, verInactivos, pagina],
    queryFn: () =>
      api<Pagina<Producto>>('/productos', {
        params: { buscar, categoria_id: categoria, activo: verInactivos ? undefined : true, pagina, tamano: TAMANO },
      }),
    placeholderData: keepPreviousData,
  })

  return (
    <>
      <Encabezado
        titulo="Catálogo"
        descripcion="Productos, sus presentaciones de compra y su clasificación."
        acciones={
          puede('catalogo.gestionar') &&
          pestana === 'productos' && (
            <Boton onClick={() => setEditando('nuevo')}>
              <Plus size={16} /> Nuevo producto
            </Boton>
          )
        }
      />
      <div className="mb-4 flex gap-1 border-b border-slate-200">
        {(['productos', 'clasificacion'] as const).map((p) => (
          <button
            key={p}
            onClick={() => setPestana(p)}
            className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium ${
              pestana === p ? 'border-marca-700 text-marca-800' : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            {p === 'productos' ? 'Productos' : 'Categorías y marcas'}
          </button>
        ))}
      </div>

      {pestana === 'clasificacion' ? (
        <Clasificacion />
      ) : (
        <>
          <div className="mb-4 grid gap-3 sm:grid-cols-[1fr_14rem_auto] sm:items-end">
            <Campo etiqueta="Buscar">
              <Entrada
                value={buscar}
                placeholder="Nombre, SKU o código de barras"
                onChange={(e) => {
                  setBuscar(e.target.value)
                  setPagina(1)
                }}
              />
            </Campo>
            <Campo etiqueta="Categoría">
              <Selector
                value={categoria}
                onChange={(e) => {
                  setCategoria(e.target.value)
                  setPagina(1)
                }}
              >
                <option value="">Todas</option>
                {categorias.data?.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.nombre}
                  </option>
                ))}
              </Selector>
            </Campo>
            <Casilla etiqueta="Ver inactivos" checked={verInactivos} onChange={(e) => setVerInactivos(e.target.checked)} />
          </div>
          {productos.isError && <Aviso>{mensajeError(productos.error)}</Aviso>}
          <Tabla>
            <thead className={CABECERA_TABLA}>
              <tr>
                <th>Producto</th>
                <th className="hidden md:table-cell">Categoría</th>
                <th className="hidden sm:table-cell">Presentaciones</th>
                <th>Estado</th>
                <th />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {productos.data?.items.map((p) => (
                <tr key={p.id}>
                  <td>
                    <div className="font-medium">{p.nombre}</div>
                    <div className="text-xs text-slate-500">
                      {p.sku} · {p.unidad_base}
                      {p.controla_vencimiento && <span className="ml-2 text-amber-700">· vence</span>}
                    </div>
                  </td>
                  <td className="hidden text-slate-600 md:table-cell">{p.categoria.nombre}</td>
                  <td className="hidden text-slate-600 sm:table-cell">
                    {p.presentaciones
                      .filter((x) => x.activo)
                      .map((x) => `${x.nombre} ${formatearCantidad(x.factor)}`)
                      .join(' · ') || '—'}
                  </td>
                  <td>{p.activo ? <Insignia tono="verde">Activo</Insignia> : <Insignia tono="rojo">Inactivo</Insignia>}</td>
                  <td className="text-right whitespace-nowrap">
                    <Link to={`/inventario/kardex/${p.id}`} className="mr-2 text-sm text-marca-700 hover:underline">
                      Kardex
                    </Link>
                    {puede('catalogo.gestionar') && (
                      <Boton variante="fantasma" onClick={() => setEditando(p.id)}>
                        Editar
                      </Boton>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </Tabla>
          <Paginador pagina={pagina} total={productos.data?.total ?? 0} tamano={TAMANO} onCambio={setPagina} />
        </>
      )}
      {editando && <FormularioProducto productoId={editando === 'nuevo' ? null : editando} onCerrar={() => setEditando(null)} />}
    </>
  )
}

interface FilaPresentacion {
  id?: string
  nombre: string
  factor: string
  activo: boolean
}

function FormularioProducto({ productoId, onCerrar }: { productoId: string | null; onCerrar: () => void }) {
  const detalle = useQuery({
    queryKey: ['producto', productoId],
    queryFn: () => api<ProductoDetalle>(`/productos/${productoId}`),
    enabled: !!productoId,
  })
  if (productoId && !detalle.data) {
    return (
      <Modal abierto titulo="Editar producto" onCerrar={onCerrar}>
        {detalle.isError ? <Aviso>{mensajeError(detalle.error)}</Aviso> : <p className="text-sm text-slate-500">Cargando…</p>}
      </Modal>
    )
  }
  return <EditorProducto producto={detalle.data ?? null} onCerrar={onCerrar} />
}

function EditorProducto({ producto, onCerrar }: { producto: ProductoDetalle | null; onCerrar: () => void }) {
  const queryClient = useQueryClient()
  const categorias = useCategorias()
  const marcas = useMarcas()
  const ubicaciones = useUbicaciones()
  const [datos, setDatos] = useState({
    sku: producto?.sku ?? '',
    nombre: producto?.nombre ?? '',
    descripcion: producto?.descripcion ?? '',
    categoria_id: producto?.categoria.id ?? '',
    marca_id: producto?.marca?.id ?? '',
    unidad_base: producto?.unidad_base ?? 'unidad',
    codigo_barras: producto?.codigo_barras ?? '',
    controla_vencimiento: producto?.controla_vencimiento ?? false,
    activo: producto?.activo ?? true,
  })
  const [presentaciones, setPresentaciones] = useState<FilaPresentacion[]>(
    producto?.presentaciones.map((p) => ({ id: p.id, nombre: p.nombre, factor: p.factor, activo: p.activo })) ?? [],
  )
  const [limites, setLimites] = useState<Record<string, { minimo: string; maximo: string }>>(() =>
    Object.fromEntries(producto?.limites.map((l) => [l.ubicacion_id, { minimo: l.minimo ?? '', maximo: l.maximo ?? '' }]) ?? []),
  )
  const cambiar = (campo: keyof typeof datos, valor: string | boolean) => setDatos((d) => ({ ...d, [campo]: valor }))

  const guardar = useMutation({
    mutationFn: async () => {
      const comun = {
        ...datos,
        descripcion: datos.descripcion || null,
        marca_id: datos.marca_id || null,
        codigo_barras: datos.codigo_barras || null,
      }
      const validas = presentaciones.filter((p) => p.nombre.trim() && Number(p.factor) > 0)
      if (!producto) {
        const { activo: _activo, ...alta } = comun
        return api<ProductoDetalle>('/productos', {
          metodo: 'POST',
          cuerpo: { ...alta, presentaciones: validas.map((p) => ({ nombre: p.nombre, factor: p.factor })) },
        })
      }
      await api(`/productos/${producto.id}`, { metodo: 'PATCH', cuerpo: comun })
      for (const p of validas) {
        const original = producto.presentaciones.find((x) => x.id === p.id)
        if (!p.id) {
          await api(`/productos/${producto.id}/presentaciones`, { metodo: 'POST', cuerpo: { nombre: p.nombre, factor: p.factor } })
        } else if (original && (original.nombre !== p.nombre || Number(original.factor) !== Number(p.factor) || original.activo !== p.activo)) {
          await api(`/presentaciones/${p.id}`, { metodo: 'PATCH', cuerpo: { nombre: p.nombre, factor: p.factor, activo: p.activo } })
        }
      }
      await api(`/productos/${producto.id}/limites`, {
        metodo: 'PUT',
        cuerpo: Object.entries(limites).map(([ubicacion_id, l]) => ({
          ubicacion_id,
          minimo: l.minimo === '' ? null : l.minimo,
          maximo: l.maximo === '' ? null : l.maximo,
        })),
      })
      return null
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['productos'] })
      queryClient.invalidateQueries({ queryKey: ['producto'] })
      queryClient.invalidateQueries({ queryKey: ['stock'] })
      onCerrar()
    },
  })

  return (
    <Modal abierto titulo={producto ? `Editar ${producto.nombre}` : 'Nuevo producto'} onCerrar={onCerrar}>
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault()
          guardar.mutate()
        }}
      >
        {guardar.isError && <Aviso>{mensajeError(guardar.error)}</Aviso>}
        <div className="grid gap-4 sm:grid-cols-[8rem_1fr]">
          <Campo etiqueta="SKU">
            <Entrada required value={datos.sku} onChange={(e) => cambiar('sku', e.target.value)} />
          </Campo>
          <Campo etiqueta="Nombre">
            <Entrada required value={datos.nombre} onChange={(e) => cambiar('nombre', e.target.value)} />
          </Campo>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Campo etiqueta="Categoría">
            <Selector required value={datos.categoria_id} onChange={(e) => cambiar('categoria_id', e.target.value)}>
              <option value="">Elegir…</option>
              {categorias.data?.filter((c) => c.activo || c.id === datos.categoria_id).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.nombre}
                </option>
              ))}
            </Selector>
          </Campo>
          <Campo etiqueta="Marca">
            <Selector value={datos.marca_id} onChange={(e) => cambiar('marca_id', e.target.value)}>
              <option value="">Sin marca</option>
              {marcas.data?.filter((m) => m.activo || m.id === datos.marca_id).map((m) => (
                <option key={m.id} value={m.id}>
                  {m.nombre}
                </option>
              ))}
            </Selector>
          </Campo>
          <Campo etiqueta="Unidad base (de venta)" ayuda="Ej.: unidad, paño, par, kg">
            <Entrada required value={datos.unidad_base} onChange={(e) => cambiar('unidad_base', e.target.value)} />
          </Campo>
          <Campo etiqueta="Código de barras">
            <Entrada value={datos.codigo_barras} onChange={(e) => cambiar('codigo_barras', e.target.value)} />
          </Campo>
        </div>
        <Casilla
          etiqueta="Controla fecha de vencimiento"
          descripcion="Exige lote y vencimiento al comprar; sugiere despachar primero lo que vence antes."
          checked={datos.controla_vencimiento}
          onChange={(e) => cambiar('controla_vencimiento', e.target.checked)}
        />
        {producto && <Casilla etiqueta="Producto activo" checked={datos.activo} onChange={(e) => cambiar('activo', e.target.checked)} />}

        <fieldset className="space-y-2">
          <legend className="text-sm font-medium text-slate-700">Presentaciones de compra</legend>
          <p className="text-xs text-slate-500">Cuántas unidades base trae cada presentación (ej.: Fardo = 100 {datos.unidad_base}).</p>
          {presentaciones.map((p, i) => (
            <div key={p.id ?? i} className="flex items-center gap-2">
              <Entrada
                placeholder="Nombre (Fardo, Caja…)"
                value={p.nombre}
                onChange={(e) => setPresentaciones((l) => l.map((x, j) => (j === i ? { ...x, nombre: e.target.value } : x)))}
              />
              <Entrada
                className="w-28"
                inputMode="decimal"
                placeholder="Factor"
                value={p.factor}
                onChange={(e) => setPresentaciones((l) => l.map((x, j) => (j === i ? { ...x, factor: e.target.value.replace(',', '.') } : x)))}
              />
              {p.id ? (
                <label className="flex items-center gap-1 text-xs text-slate-600">
                  <input
                    type="checkbox"
                    checked={p.activo}
                    onChange={(e) => setPresentaciones((l) => l.map((x, j) => (j === i ? { ...x, activo: e.target.checked } : x)))}
                  />
                  activa
                </label>
              ) : (
                <Boton variante="fantasma" className="px-2" onClick={() => setPresentaciones((l) => l.filter((_, j) => j !== i))}>
                  Quitar
                </Boton>
              )}
            </div>
          ))}
          <Boton variante="secundario" onClick={() => setPresentaciones((l) => [...l, { nombre: '', factor: '', activo: true }])}>
            <Plus size={16} /> Agregar presentación
          </Boton>
        </fieldset>

        {producto && (
          <fieldset className="space-y-2">
            <legend className="text-sm font-medium text-slate-700">Stock mínimo y máximo ({datos.unidad_base})</legend>
            {ubicaciones.data?.map((u) => (
              <div key={u.id} className="grid grid-cols-[1fr_6rem_6rem] items-center gap-2 text-sm">
                <span>{u.nombre}</span>
                {(['minimo', 'maximo'] as const).map((campo) => (
                  <Entrada
                    key={campo}
                    placeholder={campo === 'minimo' ? 'Mín.' : 'Máx.'}
                    inputMode="decimal"
                    value={limites[u.id]?.[campo] ?? ''}
                    onChange={(e) =>
                      setLimites((l) => ({
                        ...l,
                        [u.id]: { minimo: l[u.id]?.minimo ?? '', maximo: l[u.id]?.maximo ?? '', [campo]: e.target.value.replace(',', '.') },
                      }))
                    }
                  />
                ))}
              </div>
            ))}
          </fieldset>
        )}
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
