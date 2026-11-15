"""Lógica pura de pronóstico, reposición y anomalías (sin base de datos).

Pronóstico (spec 4.3): se prueban métodos simples y robustos —promedio, promedio móvil y
suavizado exponencial— y se elige el de menor error en el historial reciente (backtesting de un
paso). Con poco historial se usa el promedio y se marca la confianza como baja.
"""

import math
from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal
from statistics import median

from app.modules.alertas.models import Confianza

Z_SERVICIO = 1.65  # ~95 % de probabilidad de no quedarse sin stock durante la reposición
SEMANAS_MINIMAS = 4  # menos que esto: promedio simple y confianza baja
SEMANAS_ALTA = 12
ALFAS = (0.2, 0.4, 0.6, 0.8)


@dataclass(frozen=True)
class ResultadoPronostico:
    metodo: str
    demanda_semanal: float
    desviacion_semanal: float
    error_medio: float | None
    confianza: Confianza


def _suavizado(serie: list[float], alfa: float) -> list[float]:
    """Posición i = pronóstico para la semana i + 1 (con los datos hasta la semana i)."""
    nivel = serie[0]
    pronosticos = [nivel]
    for valor in serie[1:]:
        nivel = alfa * valor + (1 - alfa) * nivel
        pronosticos.append(nivel)
    return pronosticos  # el último es el pronóstico de la semana siguiente


def _movil(serie: list[float], ventana: int = 4) -> list[float]:
    """Misma convención que `_suavizado`: posición i = pronóstico para la semana i + 1."""
    pronosticos = [serie[0]]
    for i in range(1, len(serie) + 1):
        tramo = serie[max(0, i - ventana) : i]
        pronosticos.append(sum(tramo) / len(tramo))
    return pronosticos[1:]


def pronosticar(serie: list[float]) -> ResultadoPronostico:
    """`serie`: unidades vendidas por semana, de la más antigua a la más reciente."""
    n = len(serie)
    if n == 0 or not any(serie):
        return ResultadoPronostico("sin ventas", 0.0, 0.0, None, Confianza.BAJA)
    promedio = sum(serie) / n
    if n < SEMANAS_MINIMAS:
        desviacion = _desvio(serie)
        # Con tan pocos datos la variación es incierta: se supone al menos la mitad del promedio.
        return ResultadoPronostico(
            "promedio", promedio, max(desviacion, promedio * 0.5), None, Confianza.BAJA
        )

    candidatos: dict[str, list[float]] = {
        "promedio móvil (4 semanas)": _movil(serie),
        **{f"suavizado exponencial (alfa={a})": _suavizado(serie, a) for a in ALFAS},
    }
    # Se evalúan las últimas semanas (al menos 3 de arranque): pronóstico hecho antes vs. real.
    prueba = range(max(1, n - 8), n)
    mejor: tuple[float, str, list[float]] | None = None
    for nombre, pronosticos in candidatos.items():
        # pronosticos[i - 1] es lo que se pronosticaba para la semana i con los datos hasta i - 1.
        errores = [serie[i] - pronosticos[i - 1] for i in prueba]
        mae = sum(abs(e) for e in errores) / len(errores)
        if mejor is None or mae < mejor[0]:
            mejor = (mae, nombre, errores)
    assert mejor is not None
    mae, nombre, errores = mejor
    siguiente = candidatos[nombre][-1]
    rmse = math.sqrt(sum(e * e for e in errores) / len(errores))
    relativo = mae / promedio if promedio else 1.0
    confianza = Confianza.ALTA if n >= SEMANAS_ALTA and relativo <= 0.5 else Confianza.MEDIA
    return ResultadoPronostico(nombre, max(siguiente, 0.0), rmse, mae, confianza)


def _desvio(serie: list[float]) -> float:
    if len(serie) < 2:
        return 0.0
    m = sum(serie) / len(serie)
    return math.sqrt(sum((x - m) ** 2 for x in serie) / (len(serie) - 1))


@dataclass(frozen=True)
class Plan:
    demanda_diaria: Decimal
    stock_seguridad: Decimal
    punto_reorden: Decimal
    objetivo: Decimal  # stock al que conviene llegar al reponer
    cobertura_dias: Decimal | None  # para cuántos días alcanza lo disponible


def planificar(
    *,
    demanda_semanal: Decimal,
    desviacion_semanal: Decimal,
    disponible: Decimal,
    dias_reposicion: int,
    dias_cobertura: int,
    minimo: Decimal | None = None,
    maximo: Decimal | None = None,
) -> Plan:
    """Punto de reorden = demanda durante la reposición + stock de seguridad; objetivo = demanda de
    los días de cobertura + seguridad. Los mínimos/máximos cargados por producto mandan."""
    diaria = demanda_semanal / 7
    desvio_diario = float(desviacion_semanal) / math.sqrt(7)
    seguridad = Decimal(Z_SERVICIO * desvio_diario * math.sqrt(max(dias_reposicion, 1)))
    reorden = diaria * dias_reposicion + seguridad
    objetivo = diaria * dias_cobertura + seguridad
    if minimo is not None:
        reorden = minimo
    if maximo is not None:
        objetivo = maximo
    objetivo = max(objetivo, reorden)
    q = Decimal("0.001")
    return Plan(
        demanda_diaria=diaria.quantize(q),
        stock_seguridad=seguridad.quantize(q),
        punto_reorden=reorden.quantize(q),
        objetivo=objetivo.quantize(q),
        cobertura_dias=(disponible / diaria).quantize(Decimal("0.1")) if diaria > 0 else None,
    )


def redondear_a_presentacion(
    cantidad: Decimal, presentaciones: list[tuple[str, Decimal]]
) -> tuple[Decimal, str, Decimal]:
    """Lleva la cantidad sugerida (en unidad base) a presentaciones enteras, hacia arriba.

    Usa la presentación más grande que no supere la cantidad (fardo, caja…); si ninguna cabe,
    queda en unidades. Devuelve (cantidad en unidad base, presentación, cantidad de presentaciones).
    """
    if cantidad <= 0:
        return Decimal(0), "unidad", Decimal(0)
    usables = sorted((p for p in presentaciones if 0 < p[1] <= cantidad), key=lambda p: -p[1])
    if not usables:
        enteras = cantidad.to_integral_value(rounding=ROUND_CEILING)
        return enteras, "unidad", enteras
    nombre, factor = usables[0]
    cuantas = (cantidad / factor).to_integral_value(rounding=ROUND_CEILING)
    return cuantas * factor, nombre, cuantas


def atipico(valor: float, historia: list[float], *, minimo_historia: int = 5) -> bool:
    """Valor fuera de lo habitual (z robusto con la mediana y la desviación absoluta mediana)."""
    if len(historia) < minimo_historia:
        return False
    centro = median(historia)
    mad = median(abs(x - centro) for x in historia)
    if mad == 0:
        # Historia constante: atípico si se aparta más de un 50 % del valor de siempre.
        return centro != 0 and abs(valor - centro) / abs(centro) > 0.5
    return abs(valor - centro) / (1.4826 * mad) > 3.5
