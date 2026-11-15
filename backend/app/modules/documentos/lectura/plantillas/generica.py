"""Lectura genérica para formatos sin plantilla (Ketal, Fidalga… hasta tener muestras).

No conoce las columnas: reconoce como línea de producto todo renglón donde tres números cumplan
cantidad x precio = total. Es menos precisa que una plantilla, pero suele rescatar la mayor parte.
"""

import re
from decimal import Decimal

from app.modules.documentos.lectura import numeros
from app.modules.documentos.lectura.modelos import LineaLeida, OCLeida, Palabra, Renglon
from app.modules.documentos.lectura.plantillas.base import (
    TOLERANCIA,
    buscar,
    confianza_de,
    linea_con_confianza,
    numeros_de,
)


class PlantillaGenerica:
    nombre = "generica"

    def detectar(self, texto: str) -> float:
        return 0.1

    def interpretar(self, renglones: list[Renglon]) -> OCLeida:
        oc = OCLeida(plantilla=self.nombre)
        if r := buscar(
            renglones,
            r"(?:O\s*/\s*C|orden\s+de\s+compra|n[°ºo]\.?\s*(?:de\s+)?(?:orden|pedido))\D{0,20}(\d{4,})",
        ):
            oc.numero_oc = r[0].group(1)
            oc.confianza["numero_oc"] = confianza_de(r[1].palabras) * 0.8
        fecha_doc = (
            r"fecha\s*(?:de\s*)?(?:la\s*)?(?:orden|emisi|pedido|o\s*/\s*c|compra)\D{0,25}"
            r"(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})"
        )
        if r := buscar(renglones, fecha_doc) or buscar(
            renglones,
            r"fecha(?!\s*de\s*(?:entrega|impresi|vencim)).*?(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})",
        ):
            oc.fecha_oc = numeros.fecha(r[0].group(1))
            oc.confianza["fecha_oc"] = confianza_de(r[1].palabras) * 0.7
        if r := buscar(
            renglones, r"(?:enviar\s+a|entregar\s+en|lugar\s+de\s+entrega|destino)\W+(.+)$"
        ):
            oc.destino_texto = r[0].group(1).strip()
            oc.confianza["destino"] = 0.6
        for fila in reversed(renglones):
            if re.search(r"(?<!sub)total", fila.texto, re.IGNORECASE) and (
                valores := numeros_de(fila.palabras)
            ):
                oc.total = valores[-1][0]
                oc.confianza["total"] = confianza_de([valores[-1][1]]) * 0.8
                break

        anterior: tuple[LineaLeida, float] | None = None
        for fila in renglones:
            linea = self._linea(fila)
            if linea:
                oc.lineas.append(linea)
                anterior = (linea, fila.palabras[0].x1)
            elif anterior and not numeros_de(fila.palabras) and len(fila.texto) < 40 and oc.lineas:
                # Posible segunda línea de la descripción.
                if fila.palabras[0].x0 > anterior[1]:
                    anterior[0].descripcion += " " + fila.texto
            else:
                anterior = None
        if not oc.lineas:
            oc.avisos.append("No se reconocieron líneas de productos: cárguelas a mano.")
        return oc

    @staticmethod
    def _linea(r: Renglon) -> LineaLeida | None:
        valores = numeros_de(r.palabras)
        if len(valores) < 3:
            return None
        ultimos = valores[-4:]
        for i_t in range(len(ultimos) - 1, 1, -1):
            total = ultimos[i_t][0]
            for i_p in range(i_t - 1, 0, -1):
                for i_q in range(i_p - 1, -1, -1):
                    cantidad, precio = ultimos[i_q][0], ultimos[i_p][0]
                    if (
                        cantidad > 0
                        and precio > 0
                        and abs(cantidad * precio - total) <= TOLERANCIA
                        and total > 0
                    ):
                        return PlantillaGenerica._armar(
                            r, valores, ultimos[i_q], ultimos[i_p], ultimos[i_t]
                        )
        return None

    @staticmethod
    def _armar(
        r: Renglon,
        valores: list[tuple[Decimal, Palabra]],
        cantidad: tuple[Decimal, Palabra],
        precio: tuple[Decimal, Palabra],
        total: tuple[Decimal, Palabra],
    ) -> LineaLeida:
        elegidas = {id(cantidad[1]), id(precio[1]), id(total[1])}
        numericas = {id(v[1]) for v in valores}
        resto = [p for p in r.palabras if id(p) not in elegidas]
        # Códigos: 5+ dígitos (pueden ser solo números, como los códigos de barra).
        codigos = [
            p
            for p in resto
            if numeros.es_codigo(p.texto.replace(" ", ""))
            and sum(c.isdigit() for c in p.texto) >= 5
        ]
        descripcion = [p for p in resto if p not in codigos and id(p) not in numericas]
        return linea_con_confianza(
            codigo=codigos[0].texto if codigos else None,
            codigo_alterno=codigos[1].texto if len(codigos) > 1 else None,
            descripcion=" ".join(p.texto for p in descripcion).strip() or "Sin descripción",
            cantidad=(cantidad[0], cantidad[1].confianza),
            precio=(precio[0], precio[1].confianza),
            total=(total[0], total[1].confianza),
            factor=0.85,
            conf_descripcion=confianza_de(descripcion) * 0.9,
            conf_codigo=confianza_de(codigos),
        )
