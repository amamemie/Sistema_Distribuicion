"""Formato "Documento de Aviso de Despacho" de Hipermaxi S.A.

Columnas: Barra Proveedor | Barra Hipermaxi | Descripción | Cant. OC | Cant. Dpcho. | U/M |
Precio U. | Total Bs | Recepción. La cantidad del pedido es Cant. OC (D-16); Cant. Dpcho. solo
sirve para verificar la lectura. La columna Recepción se ignora (D-18).
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

_PEGADO = re.compile(r"^(HIPER\d{8})(\d{5,7})$", re.IGNORECASE)


class PlantillaHipermaxi:
    nombre = "hipermaxi"

    def detectar(self, texto: str) -> float:
        t = texto.upper()
        return (
            1.0
            if "HIPERMAXI" in t and "AVISO DE DESPACHO" in t
            else (0.4 if "HIPERMAXI" in t else 0.0)
        )

    def interpretar(self, renglones: list[Renglon]) -> OCLeida:
        oc = OCLeida(plantilla=self.nombre, cadena_texto="Hipermaxi")
        self._cabecera(renglones, oc)
        oc.lineas = self._lineas(renglones, oc)
        return oc

    # ------------------------------------------------------------ cabecera

    def _cabecera(self, renglones: list[Renglon], oc: OCLeida) -> None:
        if r := buscar(renglones, r"Orden\s*de\s*Compra\s*:?\s*(\d{5,})") or buscar(
            renglones, r"O\s*/?\s*C\s*:?\s*(\d{5,})"
        ):
            oc.numero_oc = r[0].group(1)
            oc.confianza["numero_oc"] = confianza_de(
                [p for p in r[1].palabras if r[0].group(1) in p.texto]
            )
        if r := buscar(renglones, r"Fecha\s*de\s*Orden"):
            texto = r[1].texto[r[0].end() :] or r[1].texto
            oc.fecha_oc = numeros.fecha(texto) or numeros.fecha(r[1].texto)
            oc.confianza["fecha_oc"] = confianza_de(r[1].palabras[-2:])
        if r := buscar(renglones, r"Fecha\s*de\s*entrega"):
            oc.fecha_entrega = numeros.fecha(r[1].texto[r[0].end() :])
        if r := buscar(renglones, r"Enviar\s*a\.?\s*:?\s*(.+?)(?:\s+Direcci.*)?$"):
            oc.destino_texto = r[0].group(1).strip() or None
            oc.confianza["destino"] = confianza_de(r[1].palabras)
        if r := buscar(renglones, r"Responsable\s*:?\s*(?:\d+\s+)?(.+)$"):
            oc.emisor = r[0].group(1).strip().title() or None
        total = buscar(renglones, r"(?<!Sub)Total\s*:?\s*([\d.,]+)") or buscar(
            renglones, r"SubTotal\s*:?\s*([\d.,]+)"
        )
        if total:
            oc.total = numeros.numero(total[0].group(1))
            oc.confianza["total"] = confianza_de(
                [p for p in total[1].palabras if total[0].group(1) in p.texto] or total[1].palabras
            )

    # ------------------------------------------------------------ líneas

    def _lineas(self, renglones: list[Renglon], oc: OCLeida) -> list[LineaLeida]:
        indice, columnas = self._encabezado(renglones)
        if indice is None:
            oc.avisos.append("No se encontró el encabezado de la tabla de productos.")
            return []
        x_desc, x_cant, x_barra2, x_recepcion = columnas
        lineas: list[LineaLeida] = []
        actual: dict[str, object] | None = None
        for r in renglones[indice + 1 :]:
            if re.search(r"Sub\s*Total|Paq\.?\s*:|Nro\.\s*Doc", r.texto, re.IGNORECASE):
                break
            codigos = [p for p in r.palabras if p.x0 < x_desc - 8]
            descripcion = [p for p in r.palabras if x_desc - 8 <= p.x0 < x_cant - 8]
            # Hasta la columna Recepción (anotaciones a mano, D-18) y nada fuera de la hoja.
            derecha = [p for p in r.palabras if x_cant - 8 <= p.x0 < x_recepcion - 5]
            valores = numeros_de(derecha)
            if len(valores) >= 3:
                if actual:
                    lineas.append(self._cerrar(actual))
                actual = {
                    "codigos": codigos,
                    "descripcion": descripcion,
                    "valores": valores,
                    "x_barra2": x_barra2,
                }
            elif actual is not None:
                # Continuación: segunda línea de la descripción y resto del código del proveedor.
                actual["descripcion"] = [*actual["descripcion"], *descripcion]  # type: ignore[misc]
                actual["extra_codigos"] = [*actual.get("extra_codigos", []), *codigos]  # type: ignore[misc]
        if actual:
            lineas.append(self._cerrar(actual))
        return lineas

    @staticmethod
    def _encabezado(
        renglones: list[Renglon],
    ) -> tuple[int | None, tuple[float, float, float, float]]:
        for i, r in enumerate(renglones):
            desc = next((p for p in r.palabras if p.texto.lower().startswith("descrip")), None)
            cant = next((p for p in r.palabras if p.texto.lower().startswith("cant")), None)
            if desc and cant:
                barras = [p for p in r.palabras if p.texto.lower().startswith("barra")]
                x_barra2 = barras[1].x0 if len(barras) > 1 else (r.palabras[0].x0 + desc.x0) / 2
                x_recepcion = max(p.x1 for p in r.palabras) + 20
                for p in r.palabras:
                    if (i_rec := p.texto.find("Recep")) >= 0:
                        # Si el OCR juntó "Precio U. Total Bs Recepción", se estima por proporción.
                        x_recepcion = p.x0 + (p.x1 - p.x0) * i_rec / max(len(p.texto), 1)
                # El encabezado ocupa dos renglones ("Proveedor / Hipermaxi / Producto / Dpcho.").
                siguiente = (
                    i + 1 if i + 1 < len(renglones) and "Producto" in renglones[i + 1].texto else i
                )
                return siguiente, (desc.x0, cant.x0, x_barra2, x_recepcion)
        return None, (0.0, 0.0, 0.0, 0.0)

    @staticmethod
    def _cerrar(actual: dict[str, object]) -> LineaLeida:
        valores: list[tuple[object, Palabra]] = actual["valores"]  # type: ignore[assignment]
        x_barra2: float = actual["x_barra2"]  # type: ignore[assignment]
        nums: list[Decimal] = [v for v, _ in valores]  # type: ignore[misc]
        conf_total = valores[-1][1].confianza
        total: Decimal | None
        if len(nums) == 3 and nums[0] == nums[1] and nums[2] < nums[1] * 100:
            # Cant. OC = Cant. Dpcho. y el total no se pudo leer: se calcula (confianza baja).
            cantidades, precio, total = [nums[0]], nums[2], nums[0] * nums[2]
            conf_total = 0.6
        else:
            total, precio = nums[-1], nums[-2]
            cantidades = [nums[0], nums[1]] if len(nums) >= 4 else [nums[0]]
        cantidad, precio_final, total, factor = conciliar(
            cantidades, precio, total, conf_precio=valores[-2][1].confianza, conf_total=conf_total
        )

        codigo, alterno = None, []
        for p in actual["codigos"]:  # type: ignore[attr-defined]
            # "HIPER20120910350561": prefijo del proveedor (HIPER + 8 dígitos) pegado al código.
            if m := _PEGADO.match(p.texto.replace(" ", "")):
                alterno.append(m.group(1))
                codigo = m.group(2)
                continue
            partes = p.texto.split()
            if p.x0 >= x_barra2 - 10:
                codigo = partes[-1]
            elif len(partes) >= 2:
                alterno.append(partes[0])
                codigo = partes[-1]
            else:
                alterno.append(partes[0])
        alterno += [p.texto.replace(" ", "") for p in actual.get("extra_codigos", [])]  # type: ignore[attr-defined]
        desc_palabras: list[Palabra] = actual["descripcion"]  # type: ignore[assignment]
        cods: list[Palabra] = actual["codigos"]  # type: ignore[assignment]
        return linea_con_confianza(
            codigo=codigo if codigo and numeros.es_codigo(codigo) else None,
            codigo_alterno="".join(alterno) or None,
            descripcion=" ".join(p.texto for p in desc_palabras).strip() or "Sin descripción",
            cantidad=(cantidad, valores[0][1].confianza),
            precio=(precio_final, valores[-2][1].confianza),
            total=(total, conf_total),
            factor=factor,
            conf_descripcion=confianza_de(desc_palabras),
            conf_codigo=confianza_de(cods),
        )
