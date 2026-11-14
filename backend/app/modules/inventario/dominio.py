"""Lógica pura de inventario (sin base de datos): conversiones, costeo y presentación."""

from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal

CERO = Decimal(0)
Q_CANTIDAD = Decimal("0.001")
Q_COSTO = Decimal("0.000001")
Q_DINERO = Decimal("0.01")
Q_VALOR = Decimal("0.0001")


def redondear(valor: Decimal, cuanto: Decimal) -> Decimal:
    return valor.quantize(cuanto, rounding=ROUND_HALF_UP)


def a_base(cantidad: Decimal, factor: Decimal) -> Decimal:
    """Convierte una cantidad expresada en una presentación a unidades base."""
    return redondear(cantidad * factor, Q_CANTIDAD)


def cpp_al_ingresar(
    saldo: Decimal, cpp: Decimal, cantidad: Decimal, costo_unitario: Decimal
) -> Decimal:
    """Costo promedio ponderado tras un ingreso."""
    total = saldo + cantidad
    if total <= 0:
        return redondear(costo_unitario, Q_COSTO)
    return redondear((saldo * cpp + cantidad * costo_unitario) / total, Q_COSTO)


def cpp_al_retirar_a_costo(
    saldo: Decimal, cpp: Decimal, cantidad: Decimal, costo_unitario: Decimal
) -> Decimal:
    """CPP tras retirar unidades a un costo distinto del promedio (anulación de un ingreso).

    Deshace el efecto del ingreso original. Si el saldo queda en cero se conserva el último CPP.
    """
    resto = saldo - cantidad
    if resto <= 0:
        return cpp
    valor = (saldo * cpp - cantidad * costo_unitario) / resto
    return redondear(max(valor, CERO), Q_COSTO)


def prorratear(subtotales: Sequence[Decimal], monto: Decimal) -> list[Decimal]:
    """Reparte un costo adicional (flete, carga) en proporción al subtotal de cada línea.

    Devuelve montos con 2 decimales cuya suma es exactamente `monto`.
    """
    if not subtotales:
        return []
    monto = redondear(monto, Q_DINERO)
    total = sum(subtotales, CERO)
    if monto == 0:
        return [CERO for _ in subtotales]
    if total <= 0:
        pesos = [Decimal(1) for _ in subtotales]
        total = Decimal(len(subtotales))
    else:
        pesos = list(subtotales)
    partes = [redondear(monto * p / total, Q_DINERO) for p in pesos]
    # El residuo de redondeo va a la línea de mayor peso.
    diferencia = monto - sum(partes, CERO)
    if diferencia:
        mayor = max(range(len(pesos)), key=lambda i: pesos[i])
        partes[mayor] += diferencia
    return partes


def formatear_cantidad(valor: Decimal) -> str:
    """1200.000 → '1200'; 2.500 → '2.5'."""
    texto = format(valor.normalize(), "f")
    return texto.rstrip("0").rstrip(".") if "." in texto else texto


def desglose(
    cantidad: Decimal, presentaciones: Sequence[tuple[str, Decimal]], unidad_base: str
) -> str:
    """Expresa una cantidad en presentaciones completas más el resto en unidades base.

    320 con [("Fardo", 100)] → "3 Fardo + 20 unidad".
    """
    if cantidad <= 0:
        return f"0 {unidad_base}"
    partes: list[str] = []
    resto = cantidad
    for nombre, factor in sorted(presentaciones, key=lambda p: p[1], reverse=True):
        if factor <= 1:
            continue
        enteras = int(resto // factor)
        if enteras > 0:
            partes.append(f"{enteras} {nombre}")
            resto -= factor * enteras
    if resto > 0 or not partes:
        partes.append(f"{formatear_cantidad(resto)} {unidad_base}")
    return " + ".join(partes)
