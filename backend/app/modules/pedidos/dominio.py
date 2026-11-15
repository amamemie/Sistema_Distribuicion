"""Lógica pura de pedidos (sin base de datos): validación aritmética de la OC,
rentabilidad y normalización de textos para el emparejamiento."""

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal

from app.modules.inventario.dominio import Q_DINERO, formatear_cantidad, redondear

CERO = Decimal(0)
# Diferencia tolerada entre lo calculado y lo impreso (redondeo de la OC).
TOLERANCIA = Decimal("0.01")
Q_PORCENTAJE = Decimal("0.01")


def normalizar_codigo(codigo: str | None) -> str | None:
    if codigo is None:
        return None
    limpio = re.sub(r"\s+", "", codigo).upper()
    return limpio or None


def normalizar_descripcion(texto: str | None) -> str | None:
    """Minúsculas, sin tildes y espacios simples: 'Detergente  ÁLA 1kg' → 'detergente ala 1kg'."""
    if texto is None:
        return None
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)
    )
    limpio = re.sub(r"\s+", " ", sin_tildes).strip().lower()
    return limpio or None


def claves_equivalencia(codigo: str | None, descripcion: str | None) -> list[str]:
    """Claves con las que se guarda/busca una equivalencia; el código tiene prioridad."""
    claves = []
    if c := normalizar_codigo(codigo):
        claves.append(f"C:{c}"[:320])
    if d := normalizar_descripcion(descripcion):
        claves.append(f"D:{d}"[:320])
    return claves


def total_calculado(cantidad: Decimal, precio: Decimal) -> Decimal:
    return redondear(cantidad * precio, Q_DINERO)


@dataclass(frozen=True)
class LineaOC:
    numero: int
    cantidad: Decimal
    precio: Decimal
    total_impreso: Decimal | None


def validar_aritmetica(
    lineas: list[LineaOC], total_oc: Decimal | None
) -> list[tuple[int | None, str]]:
    """`cantidad x precio = total de línea` y `suma de líneas = total del pedido`.

    Devuelve (número de línea o None, mensaje) por cada diferencia: suelen ser errores de lectura.
    """
    avisos: list[tuple[int | None, str]] = []
    suma = CERO
    for linea in lineas:
        calculado = total_calculado(linea.cantidad, linea.precio)
        if linea.total_impreso is not None and abs(calculado - linea.total_impreso) > TOLERANCIA:
            avisos.append(
                (
                    linea.numero,
                    f"Línea {linea.numero}: {formatear_cantidad(linea.cantidad)} x "
                    f"Bs {linea.precio.normalize():f} = Bs {calculado:.2f}, pero el documento dice "
                    f"Bs {linea.total_impreso:.2f}.",
                )
            )
        suma += linea.total_impreso if linea.total_impreso is not None else calculado
    if total_oc is not None and lineas and abs(suma - total_oc) > TOLERANCIA:
        # El total puede ser menor por un descuento (subtotal - descuento = total, D-21).
        avisos.append(
            (
                None,
                f"Descuento de Bs {suma - total_oc:.2f}: subtotal Bs {suma:.2f}, total "
                f"Bs {total_oc:.2f}. Verifique que coincida con el documento."
                if total_oc < suma
                else f"La suma de las líneas es Bs {suma:.2f}, pero el total es Bs {total_oc:.2f}.",
            )
        )
    return avisos


@dataclass(frozen=True)
class Rentabilidad:
    ingreso: Decimal
    costo: Decimal
    ganancia: Decimal
    margen: Decimal | None  # % sobre el ingreso; None si no hay ingreso


def rentabilidad(ingreso: Decimal, costo: Decimal) -> Rentabilidad:
    ingreso = redondear(ingreso, Q_DINERO)
    costo = redondear(costo, Q_DINERO)
    ganancia = ingreso - costo
    margen = redondear(ganancia * 100 / ingreso, Q_PORCENTAJE) if ingreso > 0 else None
    return Rentabilidad(ingreso, costo, ganancia, margen)
