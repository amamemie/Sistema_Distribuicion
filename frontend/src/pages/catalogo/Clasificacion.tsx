import { useMutation, useQueryClient, type UseQueryResult } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { useState } from 'react'
import { Aviso, Boton, Entrada, Insignia, Tarjeta } from '../../components/ui'
import { api, mensajeError } from '../../lib/api'
import { useCategorias, useMarcas } from '../../lib/consultas'
import { usePuede } from '../../lib/sesion'
import type { Categoria } from '../../lib/tipos'
import { useTranslation } from 'react-i18next'

export function Clasificacion() {
  const { t } = useTranslation()
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <ListaSimple titulo={t("Categorías")} ruta="/categorias" clave="categorias" consulta={useCategorias()} />
      <ListaSimple titulo={t("Marcas")} ruta="/marcas" clave="marcas" consulta={useMarcas()} />
    </div>
  )
}

function ListaSimple({
  titulo,
  ruta,
  clave,
  consulta,
}: {
  titulo: string
  ruta: string
  clave: string
  consulta: UseQueryResult<Categoria[]>
}) {
  const { t } = useTranslation()
  const puede = usePuede()
  const editable = puede('catalogo.gestionar')
  const queryClient = useQueryClient()
  const [nuevo, setNuevo] = useState('')
  const refrescar = () => queryClient.invalidateQueries({ queryKey: [clave] })

  const crear = useMutation({
    mutationFn: (nombre: string) => api(ruta, { metodo: 'POST', cuerpo: { nombre } }),
    onSuccess: () => {
      setNuevo('')
      refrescar()
    },
  })
  const actualizar = useMutation({
    mutationFn: ({ id, ...cuerpo }: { id: string; nombre?: string; activo?: boolean }) =>
      api(`${ruta}/${id}`, { metodo: 'PATCH', cuerpo }),
    onSuccess: refrescar,
  })

  return (
    <Tarjeta className="p-4">
      <h2 className="mb-3 font-semibold">{titulo}</h2>
      {(crear.isError || actualizar.isError) && <Aviso>{mensajeError(crear.error ?? actualizar.error)}</Aviso>}
      <ul className="divide-y divide-slate-100">
        {consulta.data?.map((c) => (
          <li key={c.id} className="flex items-center justify-between gap-2 py-2 text-sm">
            <span className={c.activo ? '' : 'text-slate-400 line-through'}>{c.nombre}</span>
            {editable ? (
              <span className="flex gap-1">
                <Boton
                  variante="fantasma"
                  className="min-h-8 px-2"
                  onClick={() => {
                    const nombre = window.prompt('Nuevo nombre', c.nombre)
                    if (nombre && nombre.trim() !== c.nombre) actualizar.mutate({ id: c.id, nombre: nombre.trim() })
                  }}
                >
                  {t("Renombrar")}
                </Boton>
                <Boton variante="fantasma" className="min-h-8 px-2" onClick={() => actualizar.mutate({ id: c.id, activo: !c.activo })}>
                  {c.activo ? t("Desactivar") : t("Activar")}
                </Boton>
              </span>
            ) : (
              !c.activo && <Insignia tono="rojo">{t("Inactiva")}</Insignia>
            )}
          </li>
        ))}
      </ul>
      {editable && (
        <form
          className="mt-3 flex gap-2"
          onSubmit={(e) => {
            e.preventDefault()
            if (nuevo.trim()) crear.mutate(nuevo.trim())
          }}
        >
          <Entrada placeholder={t("Nueva {{v0}}", { v0: titulo.toLowerCase().slice(0, -1) })} value={nuevo} onChange={(e) => setNuevo(e.target.value)} />
          <Boton type="submit" className="px-3" aria-label={t("Agregar")} disabled={crear.isPending}>
            <Plus size={16} />
          </Boton>
        </form>
      )}
    </Tarjeta>
  )
}
