"""Interpretación de números, fechas y códigos tal como los devuelve el OCR."""

import re
from datetime import date
from decimal import Decimal, InvalidOperation

_NUMERO = re.compile(r"^-?[\d.,]*\d$")
_FECHA = re.compile(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4}|\d{2})")
# Confusiones típicas del OCR dentro de un número.
_CONFUSIONES = str.maketrans(
    {"O": "0", "o": "0", "D": "0", "l": "1", "I": "1", "|": "1", "S": "5", "B": "8"}
)


def numero(texto: str) -> Decimal | None:
    """'1,324.80' / '1.324,80' / '780' / '13,8' → Decimal. None si no es un número."""
    t = texto.strip().replace(" ", "")
    if t and not t[0].isdigit() and t[0] != "-":
        return None
    if not _NUMERO.match(t):
        t = t.translate(_CONFUSIONES)
        if not _NUMERO.match(t):
            return None
    if "," in t and "." in t:
        decimal = "," if t.rfind(",") > t.rfind(".") else "."
        miles = "." if decimal == "," else ","
        t = t.replace(miles, "").replace(decimal, ".")
    elif "," in t:
        enteros, _, fraccion = t.rpartition(",")
        t = (
            t.replace(",", "")
            if len(fraccion) == 3 and t.count(",") >= 1 and len(enteros) <= 3
            else t.replace(",", ".")
        )
    elif t.count(".") > 1:
        enteros, _, fraccion = t.rpartition(".")
        t = enteros.replace(".", "") + "." + fraccion
    try:
        return Decimal(t)
    except InvalidOperation:
        return None


def fecha(texto: str) -> date | None:
    """Primera fecha dd/mm/aaaa del texto."""
    m = _FECHA.search(texto)
    if not m:
        return None
    dia, mes, anio = (int(x) for x in m.groups())
    if anio < 100:
        anio += 2000
    try:
        return date(anio, mes, dia)
    except ValueError:
        return None


def es_codigo(texto: str) -> bool:
    """Códigos de producto: 5+ dígitos o letras+dígitos sin espacios (p. ej. HIPER2012…)."""
    t = texto.strip()
    return (
        len(t) >= 5
        and any(c.isdigit() for c in t)
        and re.fullmatch(r"[A-Za-z0-9\-]+", t) is not None
    )
