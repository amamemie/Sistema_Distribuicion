import { ExternalLink, FileText, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { urlArchivo } from '../../lib/api'
import { formatearTamano } from '../../lib/formato'
import type { DocumentoPedido } from '../../lib/tipos'
import { Boton, Tarjeta } from '../ui'
import { useTranslation } from 'react-i18next'

/** Muestra las páginas del documento (fotos y PDF) para revisarlas junto a los datos. */
export function VisorDocumentos({
  pedidoId,
  documentos,
  onQuitar,
}: {
  pedidoId: string
  documentos: DocumentoPedido[]
  onQuitar?: (archivoId: string) => void
}) {
  const { t } = useTranslation()
  const [actual, setActual] = useState(0)
  const doc = documentos[Math.min(actual, documentos.length - 1)]
  if (!doc) {
    return (
      <Tarjeta className="flex h-40 items-center justify-center p-4 text-sm text-slate-500">
        {t("Sin documento adjunto (pedido cargado a mano).")}
      </Tarjeta>
    )
  }
  const url = urlArchivo(pedidoId, doc.id)
  const esPdf = doc.tipo_mime === 'application/pdf'
  return (
    <Tarjeta className="overflow-hidden">
      {documentos.length > 1 && (
        <div className="flex gap-1 overflow-x-auto border-b border-slate-200 p-2">
          {documentos.map((d, i) => (
            <button
              key={d.id}
              type="button"
              onClick={() => setActual(i)}
              className={`shrink-0 rounded px-2.5 py-1 text-xs font-medium ${
                i === actual ? 'bg-marca-700 text-white' : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
              }`}
            >
              {d.tipo_mime === 'application/pdf' ? 'PDF' : t("Pág.")} {i + 1}
            </button>
          ))}
        </div>
      )}
      <div className="bg-slate-100">
        {esPdf ? (
          <>
            {/* En celulares muchos navegadores no muestran PDF incrustados: se ofrece abrirlo. */}
            <iframe src={url} title={doc.nombre} className="hidden h-[75dvh] w-full lg:block" />
            <a
              href={url}
              target="_blank"
              rel="noreferrer"
              className="flex h-40 flex-col items-center justify-center gap-2 text-sm text-marca-800 lg:hidden"
            >
              <FileText size={32} /> {t("Abrir el PDF")}
            </a>
          </>
        ) : (
          <a href={url} target="_blank" rel="noreferrer" title={t("Abrir en tamaño completo")}>
            <img src={url} alt={doc.nombre} className="mx-auto max-h-[75dvh] w-full object-contain" loading="lazy" />
          </a>
        )}
      </div>
      <div className="flex items-center justify-between gap-2 border-t border-slate-200 px-3 py-2 text-xs text-slate-600">
        <span className="truncate">
          {doc.nombre} · {formatearTamano(doc.tamano)}
        </span>
        <span className="flex shrink-0 items-center gap-1">
          <a href={url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 rounded px-2 py-1 hover:bg-slate-100">
            <ExternalLink size={14} /> {t("Abrir")}
          </a>
          {onQuitar && (
            <Boton
              variante="fantasma"
              className="min-h-7 px-2 text-red-600"
              onClick={() => {
                if (confirm(`¿Quitar «${doc.nombre}» del pedido?`)) onQuitar(doc.id)
              }}
              aria-label={t("Quitar archivo")}
            >
              <Trash2 size={14} />
            </Boton>
          )}
        </span>
      </div>
    </Tarjeta>
  )
}
