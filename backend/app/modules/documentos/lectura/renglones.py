"""Agrupa las palabras del OCR en renglones, tolerando fotos un poco inclinadas."""

import statistics

from app.modules.documentos.lectura.modelos import Palabra, Renglon


def _pendiente(palabras: list[Palabra]) -> float:
    """Inclinación típica del texto: se estima con pares de palabras vecinas en la misma línea."""
    pendientes = []
    ordenadas = sorted(palabras, key=lambda p: (p.cy, p.x0))
    for a in ordenadas:
        for b in ordenadas:
            dx = b.cx - a.cx
            if dx > 3 * a.alto and abs(b.cy - a.cy) < a.alto * 0.8:
                pendientes.append((b.cy - a.cy) / dx)
                break
    return statistics.median(pendientes) if len(pendientes) >= 5 else 0.0


def agrupar(palabras: list[Palabra]) -> list[Renglon]:
    """Renglones de arriba hacia abajo (por página); cada uno de izquierda a derecha."""
    renglones: list[Renglon] = []
    for pagina in sorted({p.pagina for p in palabras}):
        de_pagina = [p for p in palabras if p.pagina == pagina and p.texto.strip()]
        if not de_pagina:
            continue
        pendiente = _pendiente(de_pagina)
        alto = statistics.median(p.alto for p in de_pagina) or 1.0

        def y_corregida(p: Palabra, pendiente: float = pendiente) -> float:
            return p.cy - pendiente * p.cx

        actuales: list[list[Palabra]] = []
        for p in sorted(de_pagina, key=y_corregida):
            if (
                actuales
                and abs(y_corregida(p) - statistics.fmean(y_corregida(q) for q in actuales[-1]))
                < alto * 0.55
            ):
                actuales[-1].append(p)
            else:
                actuales.append([p])
        renglones += [Renglon(sorted(grupo, key=lambda p: p.x0), pagina) for grupo in actuales]
    return renglones
