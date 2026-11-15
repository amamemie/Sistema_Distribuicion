"""Elige la plantilla según el texto y devuelve la OC estructurada."""

from app.modules.documentos.lectura.modelos import OCLeida, Palabra
from app.modules.documentos.lectura.plantillas import GENERICA, PLANTILLAS
from app.modules.documentos.lectura.renglones import agrupar


def interpretar(palabras: list[Palabra]) -> OCLeida:
    renglones = agrupar(palabras)
    texto = "\n".join(r.texto for r in renglones)
    candidatas = sorted(PLANTILLAS, key=lambda p: p.detectar(texto), reverse=True)
    if candidatas and candidatas[0].detectar(texto) >= 0.5:
        resultado = candidatas[0].interpretar(renglones)
        if resultado.lineas:
            return resultado
        # La plantilla no encontró la tabla (foto mala o formato cambiado): se prueba la genérica.
        generica = GENERICA.interpretar(renglones)
        generica.cadena_texto = resultado.cadena_texto
        generica.avisos.insert(
            0,
            f"El formato parece de {resultado.cadena_texto}, pero su plantilla no pudo leerlo.",
        )
        return generica
    return GENERICA.interpretar(renglones)
