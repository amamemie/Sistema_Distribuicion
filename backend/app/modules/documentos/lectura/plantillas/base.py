import re
from decimal import Decimal
from typing import Protocol

from app.modules.documentos.lectura import numeros
from app.modules.documentos.lectura.modelos import LineaLeida, OCLeida, Palabra, Renglon

TOLERANCIA = Decimal("0.02")


class Plantilla(Protocol):
    nombre: str

    def detectar(self, texto: str) -> float:
        """Qué tan seguro es que el documento tiene este formato (0-1)."""
        ...

    def interpretar(self, renglones: list[Renglon]) -> OCLeida: ...


def buscar(renglones: list[Renglon], patron: str) -> tuple[re.Match[str], Renglon] | None:
    expresion = re.compile(patron, re.IGNORECASE)
    for r in renglones:
        if m := expresion.search(r.texto):
            return m, r
    return None


def confianza_de(palabras: list[Palabra]) -> float:
    return round(min((p.confianza for p in palabras), default=0.0), 3)


def numeros_de(palabras: list[Palabra]) -> list[tuple[Decimal, Palabra]]:
    """Números de una serie de palabras (una caja del OCR puede traer varios: '40 PCE')."""
    resultado = []
    for p in palabras:
        for parte in p.texto.split():
            if (n := numeros.numero(parte)) is not None:
                resultado.append((n, p))
    return resultado


def conciliar(
    cantidades: list[Decimal],
    precio: Decimal,
    total: Decimal | None,
    *,
    conf_precio: float = 1.0,
    conf_total: float = 1.0,
) -> tuple[Decimal, Decimal, Decimal | None, float]:
    """Elige cantidad, precio y total que cumplan cantidad x precio = total.

    Devuelve (cantidad, precio, total, factor de confianza): 1.0 si cuadra tal cual; menos si
    hubo que corregir la lectura más dudosa según el OCR; 0.4 si no cuadra de ninguna forma.
    """
    if total is None:
        return cantidades[0], precio, None, 0.6
    for i, cantidad in enumerate(cantidades):
        if abs(cantidad * precio - total) <= TOLERANCIA:
            return cantidad, precio, total, 1.0 if i == 0 else 0.8
    cantidad = cantidades[0]
    if cantidad <= 0:
        return cantidad, precio, total, 0.4
    if conf_total < conf_precio:
        # El total es la lectura más dudosa: se recalcula.
        return cantidad, precio, (cantidad * precio).quantize(Decimal("0.01")), 0.6
    deducido = (total / cantidad).quantize(Decimal("0.0001"))
    if abs(deducido * cantidad - total) <= TOLERANCIA and deducido == deducido.quantize(
        Decimal("0.01")
    ):
        return cantidad, deducido.normalize(), total, 0.6
    return cantidad, precio, total, 0.4


def linea_con_confianza(
    *,
    codigo: str | None,
    codigo_alterno: str | None,
    descripcion: str,
    cantidad: tuple[Decimal, float],
    precio: tuple[Decimal, float],
    total: tuple[Decimal | None, float],
    factor: float,
    conf_descripcion: float,
    conf_codigo: float,
) -> LineaLeida:
    return LineaLeida(
        codigo=codigo,
        codigo_alterno=codigo_alterno,
        descripcion=descripcion,
        cantidad=cantidad[0],
        precio=precio[0],
        total=total[0],
        confianza={
            "codigo": round(conf_codigo, 3),
            "descripcion": round(conf_descripcion, 3),
            "cantidad": round(cantidad[1] * factor, 3),
            "precio": round(precio[1] * factor, 3),
            "total": round(total[1] * factor, 3),
        },
    )
