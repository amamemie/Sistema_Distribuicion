"""Formato "Nota de Recepción" de Hipermaxi S.A. (documento del pedido desde D-19).

Cabecera: No. Rec., Fecha, No. O/C., U/N (unidad de negocio que recibe = sucursal del
supermercado). Columnas: Cod. Articulo | Cod. Fabrica | Descripcion | U/M | Cantidad |
Precio U. | Total. Pie: SubTotal, Descuento y Total Bs.

El número del pedido es el de la O/C; el de la nota va en observaciones (D-19).
"""

import re
from decimal import Decimal

from app.modules.documentos.lectura import numeros
from app.modules.documentos.lectura.modelos import LineaLeida, OCLeida, Palabra, Renglon
from app.modules.documentos.lectura.plantillas.base import (
    buscar,
    conciliar,
    confianza_de,
    linea_con_confianza,
    numeros_de,
)

_FIN_TABLA = re.compile(r"Almac[eé]n|Sub\s*Total|Paq\.?\s*:", re.IGNORECASE)
_FECHA = r"(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})"


class PlantillaHipermaxiRecepcion:
    nombre = "hipermaxi_recepcion"

    def detectar(self, texto: str) -> float:
        t = re.sub(r"\s+", " ", texto.upper())
        # La OC también tiene una columna "Recepción": se exige el título del documento.
        if re.search(r"NOTA\s*DE\s*RECEPCI[OÓ]N", t) and "HIPERMAXI" in t:
            return 1.0
        return 0.0

    def interpretar(self, renglones: list[Renglon]) -> OCLeida:
        oc = OCLeida(plantilla=self.nombre, cadena_texto="Hipermaxi")
        self._cabecera(renglones, oc)
        oc.lineas = self._lineas(renglones, oc)
        return oc

    # ------------------------------------------------------------ cabecera

    @staticmethod
    def _valor(r: tuple[re.Match[str], Renglon]) -> float:
        valor = r[0].group(1)
        return confianza_de([p for p in r[1].palabras if valor in p.texto] or r[1].palabras)

    def _cabecera(self, renglones: list[Renglon], oc: OCLeida) -> None:
        if r := buscar(renglones, r"O\s*/\s*C\.?\s*:?\s*(\d{5,})"):
            oc.numero_oc = r[0].group(1)
            oc.confianza["numero_oc"] = self._valor(r)
        if r := buscar(renglones, r"No\.?\s*Rec\.?\s*:?\s*(\d{4,})"):
            oc.numero_documento = r[0].group(1)
        # "Fecha : 22/10/2026" (no "Fecha Vcto.", que viene después).
        if r := buscar(renglones, r"Fecha\s*:?\s*" + _FECHA):
            oc.fecha_oc = numeros.fecha(r[0].group(1))
            oc.confianza["fecha_oc"] = self._valor(r)
        if r := buscar(renglones, r"U\s*/\s*N\s*:?\s*(?:\d+\s*)?(?:U\.?\s*N\.?\s*)?(.+)$"):
            oc.destino_texto = r[0].group(1).strip() or None
            oc.confianza["destino"] = confianza_de(r[1].palabras)
        subtotal = buscar(renglones, r"Sub\s*Total\s*:?\s*([\d.,]+)")
        total = buscar(renglones, r"Total\s*Bs\.?\s*:?\s*([\d.,]+)")
        if r := buscar(renglones, r"Descuento\s*:?\s*([\d.,]+)"):
            oc.descuento = numeros.numero(r[0].group(1))
        if total or subtotal:
            elegido = total or subtotal
            assert elegido is not None
            oc.total = numeros.numero(elegido[0].group(1))
            if oc.total is not None and not total and oc.descuento:
                oc.total -= oc.descuento
            oc.confianza["total"] = self._valor(elegido)

    # ------------------------------------------------------------ líneas

    def _lineas(self, renglones: list[Renglon], oc: OCLeida) -> list[LineaLeida]:
        indice, columnas = self._encabezado(renglones)
        if indice is None:
            oc.avisos.append("No se encontró el encabezado de la tabla de productos.")
            return []
        x_fabrica, x_desc, x_um = columnas
        lineas: list[LineaLeida] = []
        actual: dict[str, list[Palabra]] | None = None
        for r in renglones[indice + 1 :]:
            if _FIN_TABLA.search(r.texto):
                break
            izquierda = [p for p in r.palabras if p.x0 < x_desc]
            # Lo que está a la izquierda pero no tiene dígitos ya es la descripción.
            codigos = [p for p in izquierda if any(c.isdigit() for c in p.texto)]
            descripcion = [p for p in izquierda if p not in codigos] + [
                p for p in r.palabras if x_desc <= p.x0 < x_um - 6
            ]
            derecha = [p for p in r.palabras if p.x0 >= x_um - 6]
            if len(numeros_de(derecha)) >= 2:
                if actual:
                    lineas.append(self._cerrar(actual, x_fabrica))
                actual = {"codigos": codigos, "descripcion": descripcion, "derecha": derecha}
            elif actual is not None and descripcion and not codigos:
                actual["descripcion"] = [*actual["descripcion"], *descripcion]
        if actual:
            lineas.append(self._cerrar(actual, x_fabrica))
        return lineas

    @staticmethod
    def _encabezado(renglones: list[Renglon]) -> tuple[int | None, tuple[float, float, float]]:
        for i, r in enumerate(renglones):
            desc = next((p for p in r.palabras if p.texto.lower().startswith("descrip")), None)
            cant = next((p for p in r.palabras if p.texto.lower().startswith("cant")), None)
            if not (desc and cant):
                continue
            i_fab = next((k for k, p in enumerate(r.palabras) if "fabric" in p.texto.lower()), None)
            um = next((p for p in r.palabras if re.match(r"U\s*/?\s*M", p.texto)), None)
            if i_fab is None:
                x_fabrica = (r.palabras[0].x0 + desc.x0) / 2
            else:
                # La columna empieza en "Cod." (en la misma caja si el OCR juntó "Cod. Fabrica").
                fabrica = r.palabras[i_fab]
                previa = r.palabras[i_fab - 1] if i_fab > 0 else None
                if fabrica.texto.lower().startswith("cod"):
                    x_fabrica = fabrica.x0 - 8
                elif previa and previa.texto.lower().startswith("cod"):
                    x_fabrica = previa.x0 - 8
                else:
                    x_fabrica = fabrica.x0 - 25
            x_um = um.x0 if um else cant.x0 - (cant.x1 - cant.x0)
            # La descripción empieza algo antes que su título (columna alineada a la izquierda).
            x_desc = desc.x0 - max(desc.x0 - x_fabrica, 0) * 0.25
            return i, (x_fabrica, x_desc, x_um)
        return None, (0.0, 0.0, 0.0)

    @staticmethod
    def _cerrar(actual: dict[str, list[Palabra]], x_fabrica: float) -> LineaLeida:
        valores = numeros_de(actual["derecha"])
        nums: list[Decimal] = [v for v, _ in valores]
        if len(nums) >= 3:
            cantidad, precio, total = nums[-3], nums[-2], nums[-1]
            conf = (valores[-3][1].confianza, valores[-2][1].confianza, valores[-1][1].confianza)
        else:  # falta una columna: se supone que es el total
            cantidad, precio, total = nums[0], nums[1], None
            conf = (valores[0][1].confianza, valores[1][1].confianza, 0.0)
        cantidad, precio, total, factor = conciliar(
            [cantidad], precio, total, conf_precio=conf[1], conf_total=conf[2]
        )

        articulo: list[str] = []
        fabrica: list[str] = []
        for p in actual["codigos"]:
            trozos = [t for t in p.texto.split() if numeros.es_codigo(t)]
            if len(trozos) >= 2:
                # El OCR juntó los dos códigos en una caja: artículo y luego fábrica.
                articulo.append(trozos[0])
                fabrica.append(trozos[1])
            elif trozos:
                (articulo if p.x0 < x_fabrica else fabrica).append(trozos[0])
        if not articulo and len(fabrica) >= 2:
            articulo, fabrica = fabrica[:1], fabrica[1:]
        desc = actual["descripcion"]
        return linea_con_confianza(
            codigo=articulo[0] if articulo else None,
            codigo_alterno=fabrica[0] if fabrica else None,
            descripcion=" ".join(p.texto for p in desc).strip() or "Sin descripción",
            cantidad=(cantidad, conf[0]),
            precio=(precio, conf[1]),
            total=(total, conf[2] if total is not None else 0.6),
            factor=factor,
            conf_descripcion=confianza_de(desc),
            conf_codigo=confianza_de(actual["codigos"]),
        )
