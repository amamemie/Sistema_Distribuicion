"""Exportación de cualquier `Reporte` a Excel (una hoja por tabla) y a PDF (indicadores y
tablas)."""

import io
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fpdf import FPDF
from fpdf.fonts import FontFace
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from app.modules.reportes.schemas import Kpi, Reporte, Tabla, TipoDato

FORMATO_EXCEL: dict[str, str] = {
    "entero": "#,##0",
    "cantidad": "#,##0.###",
    "dinero": "#,##0.00",
    "porcentaje": '0.00" %"',
    "fecha": "dd/mm/yyyy",
}
_NO_HOJA = re.compile(r"[\[\]:*?/\\]")


def nombre_archivo(reporte: Reporte, extension: str, hoy: date) -> str:
    return f"reporte-{reporte.clave.replace('_', '-')}-{hoy:%Y-%m-%d}.{extension}"


# ---------------------------------------------------------------- texto (PDF y vista)


def _miles(texto: str) -> str:
    """'1234567.80' → '1.234.567,80' (formato boliviano)."""
    entero, _, decimales = texto.partition(".")
    signo = "-" if entero.startswith("-") else ""
    entero = entero.lstrip("-")
    grupos: list[str] = []
    while len(entero) > 3:
        grupos.insert(0, entero[-3:])
        entero = entero[:-3]
    grupos.insert(0, entero)
    return signo + ".".join(grupos) + ("," + decimales if decimales else "")


def formatear(valor: Any, tipo: TipoDato) -> str:
    if valor is None or valor == "":
        return "—"
    if tipo == "fecha" and isinstance(valor, date):
        return f"{valor:%d/%m/%Y}"
    if tipo in ("dinero", "porcentaje", "cantidad", "entero"):
        numero = Decimal(str(valor))
        if tipo == "dinero":
            return "Bs " + _miles(f"{numero:.2f}")
        if tipo == "porcentaje":
            return _miles(f"{numero:.1f}") + " %"
        if tipo == "entero":
            return _miles(f"{numero:.0f}")
        texto = f"{numero.normalize():f}" if numero == numero.to_integral() else f"{numero:.3f}"
        return _miles(texto.rstrip("0").rstrip(".") if "." in texto else texto)
    return str(valor)


def _texto_kpi(k: Kpi) -> str:
    texto = formatear(k.valor, k.tipo)
    if k.anterior is not None:
        texto += f"  (anterior: {formatear(k.anterior, k.tipo)}"
        if k.variacion is not None:
            texto += f", {'+' if k.variacion > 0 else ''}{formatear(k.variacion, 'porcentaje')}"
        texto += ")"
    return texto


# ---------------------------------------------------------------- Excel


def _valor_excel(valor: Any, tipo: TipoDato) -> Any:
    if valor is None:
        return None
    if tipo in ("dinero", "cantidad", "porcentaje"):
        return float(valor) if isinstance(valor, Decimal) else valor
    if tipo == "fecha" and isinstance(valor, datetime):
        return valor.date()
    return valor


def excel(reporte: Reporte) -> bytes:
    libro = Workbook()
    resumen = libro.active
    assert resumen is not None
    resumen.title = "Resumen"
    negrita = Font(bold=True)
    resumen.append([reporte.titulo])
    resumen["A1"].font = Font(bold=True, size=14)
    resumen.append([reporte.descripcion])
    for texto in reporte.filtros_texto:
        resumen.append([texto])
    if reporte.kpis:
        resumen.append([])
        resumen.append(["Indicador", "Valor", "Período anterior", "Variación %"])
        for celda in resumen[resumen.max_row]:
            celda.font = negrita
        for k in reporte.kpis:
            resumen.append(
                [
                    k.titulo,
                    _valor_excel(k.valor, k.tipo),
                    _valor_excel(k.anterior, k.tipo),
                    float(k.variacion) if k.variacion is not None else None,
                ]
            )
            fila = resumen.max_row
            for columna_kpi in (2, 3):
                resumen.cell(fila, columna_kpi).number_format = FORMATO_EXCEL.get(k.tipo, "General")
            resumen.cell(fila, 4).number_format = "0.0"
    resumen.column_dimensions["A"].width = 42
    for col in "BCD":
        resumen.column_dimensions[col].width = 18

    usados: set[str] = {"Resumen"}
    for tabla in reporte.tablas:
        hoja = libro.create_sheet(_nombre_hoja(tabla.titulo, usados))
        _hoja_tabla(hoja, tabla)
    salida = io.BytesIO()
    libro.save(salida)
    return salida.getvalue()


def _nombre_hoja(titulo: str, usados: set[str]) -> str:
    base = _NO_HOJA.sub("", titulo)[:28] or "Tabla"
    nombre, n = base, 2
    while nombre in usados:
        nombre = f"{base[:25]} ({n})"
        n += 1
    usados.add(nombre)
    return nombre


def _hoja_tabla(hoja: Any, tabla: Tabla) -> None:
    hoja.append([c.titulo for c in tabla.columnas])
    relleno = PatternFill("solid", fgColor="E2E8F0")
    for celda in hoja[1]:
        celda.font = Font(bold=True)
        celda.fill = relleno
        celda.alignment = Alignment(wrap_text=True, vertical="center")
    for fila in tabla.filas:
        hoja.append([_valor_excel(fila.get(c.clave), c.tipo) for c in tabla.columnas])
    for i, columna in enumerate(tabla.columnas, start=1):
        letra = get_column_letter(i)
        formato = FORMATO_EXCEL.get(columna.tipo)
        if formato:
            for (celda,) in hoja.iter_rows(min_row=2, min_col=i, max_col=i):
                celda.number_format = formato
        largo = max(
            [len(columna.titulo)]
            + [len(str(f.get(columna.clave) or "")) for f in tabla.filas[:200]]
        )
        hoja.column_dimensions[letra].width = min(max(largo + 2, 10), 50)
    hoja.freeze_panes = "A2"
    if tabla.filas:
        hoja.auto_filter.ref = hoja.dimensions


# ---------------------------------------------------------------- PDF

# Las fuentes base del PDF solo cubren Latin-1: se reemplazan los pocos signos que no entran.
_REEMPLAZOS = str.maketrans(
    {"\u2212": "-", "\u2013": "-", "\u2014": "-", "\u2026": "...", "\u2248": "~", "\u00bd": "1/2"}
)


def _latin1(texto: str) -> str:
    return texto.translate(_REEMPLAZOS).encode("latin-1", "replace").decode("latin-1")


class _Pdf(FPDF):
    def __init__(self, titulo: str, generado: str) -> None:
        super().__init__(orientation="L", unit="mm", format="A4")
        self.titulo_reporte = titulo
        self.generado = generado
        self.set_auto_page_break(auto=True, margin=14)
        self.set_margins(12, 12, 12)

    def footer(self) -> None:
        self.set_y(-10)
        self.set_font("Helvetica", size=7)
        self.set_text_color(100, 116, 139)
        self.cell(0, 5, _latin1(f"{self.titulo_reporte} · {self.generado}"), align="L")
        self.cell(0, 5, f"Página {self.page_no()}/{{nb}}", align="R")


def pdf(reporte: Reporte, generado: str) -> bytes:
    documento = _Pdf(reporte.titulo, generado)
    documento.alias_nb_pages()
    documento.add_page()
    documento.set_font("Helvetica", "B", 16)
    documento.cell(0, 9, _latin1(reporte.titulo), new_x="LMARGIN", new_y="NEXT")
    documento.set_font("Helvetica", size=8)
    documento.set_text_color(71, 85, 105)
    documento.multi_cell(0, 4, _latin1(reporte.descripcion), new_x="LMARGIN", new_y="NEXT")
    documento.multi_cell(
        0, 4, _latin1(" · ".join(reporte.filtros_texto)), new_x="LMARGIN", new_y="NEXT"
    )
    documento.set_text_color(15, 23, 42)
    documento.ln(2)
    if reporte.kpis:
        documento.set_font("Helvetica", size=9)
        with documento.table(
            col_widths=(70, 130),
            width=200,
            align="LEFT",
            first_row_as_headings=False,
            line_height=5.5,
            borders_layout="HORIZONTAL_LINES",
        ) as t:
            for k in reporte.kpis:
                fila = t.row()
                fila.cell(_latin1(k.titulo))
                fila.cell(_latin1(_texto_kpi(k)))
        documento.ln(3)
    for tabla in reporte.tablas:
        _tabla_pdf(documento, tabla)
    return bytes(documento.output())


def _tabla_pdf(documento: _Pdf, tabla: Tabla) -> None:
    if documento.will_page_break(25):
        documento.add_page()
    documento.set_font("Helvetica", "B", 11)
    documento.cell(0, 7, _latin1(tabla.titulo), new_x="LMARGIN", new_y="NEXT")
    if tabla.descripcion:
        documento.set_font("Helvetica", size=7)
        documento.set_text_color(71, 85, 105)
        documento.multi_cell(0, 3.5, _latin1(tabla.descripcion), new_x="LMARGIN", new_y="NEXT")
        documento.set_text_color(15, 23, 42)
    if not tabla.filas:
        documento.set_font("Helvetica", "I", 8)
        documento.cell(0, 6, "Sin datos en el período.", new_x="LMARGIN", new_y="NEXT")
        documento.ln(2)
        return
    # Ancho proporcional: los textos ocupan más que los números.
    pesos = [
        3.0 if c.tipo == "texto" else 1.6 if c.tipo == "dinero" else 1.2 for c in tabla.columnas
    ]
    ancho = documento.epw
    anchos = tuple(ancho * p / sum(pesos) for p in pesos)
    alineacion = tuple("LEFT" if c.tipo in ("texto", "fecha") else "RIGHT" for c in tabla.columnas)
    documento.set_font("Helvetica", size=7.5)
    with documento.table(
        col_widths=anchos,
        text_align=alineacion,
        line_height=4.6,
        headings_style=FontFace(emphasis="BOLD", fill_color=(226, 232, 240)),
        borders_layout="SINGLE_TOP_LINE",
        repeat_headings=1,
    ) as t:
        encabezado = t.row()
        for c in tabla.columnas:
            encabezado.cell(_latin1(c.titulo))
        for fila in tabla.filas:
            r = t.row()
            for c in tabla.columnas:
                r.cell(_latin1(formatear(fila.get(c.clave), c.tipo)))
    documento.ln(4)
