"""Lógica pura de finanzas (sin base de datos)."""

from collections.abc import Hashable, Sequence
from decimal import Decimal


def repartir[K: Hashable](
    monto: Decimal, saldos: Sequence[tuple[K, Decimal]]
) -> list[tuple[K, Decimal]]:
    """Reparte un pago entre deudas en el orden dado (del pedido más antiguo al más reciente,
    T-31): cada deuda se cubre completa antes de pasar a la siguiente. Devuelve solo las deudas
    que reciben algo. El llamador valida antes que `monto` no supere la suma de los saldos."""
    resultado: list[tuple[K, Decimal]] = []
    resto = monto
    for clave, saldo in saldos:
        if resto <= 0:
            break
        if saldo <= 0:
            continue
        aplicado = min(saldo, resto)
        resultado.append((clave, aplicado))
        resto -= aplicado
    return resultado
