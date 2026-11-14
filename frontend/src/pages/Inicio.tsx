import { Encabezado, Tarjeta } from '../components/ui'
import { useYo } from '../lib/sesion'

const FASES = [
  { nombre: 'Fase 0 · Base', detalle: 'Usuarios, roles, permisos, ubicaciones y auditoría.', lista: true },
  { nombre: 'Fase 1 · Inventario', detalle: 'Catálogo, compras, transferencias, ajustes, conteos y kardex.', lista: true },
  { nombre: 'Fase 2 · Pedidos', detalle: 'Órdenes de compra, reserva, alistado, entrega y ganancia.' },
  { nombre: 'Fase 3 · Reportes', detalle: 'Dashboard de ganancias y estadísticas.' },
  { nombre: 'Fase 4 · Alertas y ML', detalle: 'Alertas de stock, pronóstico y reposición.' },
]

export function Inicio() {
  const { data: yo } = useYo()
  return (
    <>
      <Encabezado titulo={`Hola, ${yo?.nombre ?? ''}`} descripcion="Estado de avance del sistema." />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {FASES.map((f) => (
          <Tarjeta key={f.nombre} className="p-4">
            <div className="flex items-center justify-between gap-2">
              <h2 className="font-medium">{f.nombre}</h2>
              <span
                className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                  f.lista ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-100 text-slate-600'
                }`}
              >
                {f.lista ? 'Disponible' : 'Pendiente'}
              </span>
            </div>
            <p className="mt-2 text-sm text-slate-600">{f.detalle}</p>
          </Tarjeta>
        ))}
      </div>
    </>
  )
}
