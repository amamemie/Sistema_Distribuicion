"""Tipos de la lectura: palabras del OCR y el resultado estructurado de una OC."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


@dataclass(frozen=True)
class Palabra:
    """Fragmento de texto con su caja (en píxeles o puntos) y la confianza del OCR (0-1)."""

    texto: str
    x0: float
    y0: float
    x1: float
    y1: float
    confianza: float = 1.0
    pagina: int = 1

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2

    @property
    def alto(self) -> float:
        return self.y1 - self.y0


@dataclass
class Renglon:
    """Palabras que están a la misma altura, ordenadas de izquierda a derecha."""

    palabras: list[Palabra]
    pagina: int = 1

    @property
    def texto(self) -> str:
        return " ".join(p.texto for p in self.palabras)

    @property
    def y(self) -> float:
        return sum(p.cy for p in self.palabras) / len(self.palabras)


class LineaLeida(BaseModel):
    codigo: str | None = None  # código de la cadena
    codigo_alterno: str | None = None  # otro código impreso (p. ej. barra del proveedor)
    descripcion: str
    cantidad: Decimal
    precio: Decimal
    total: Decimal | None = None
    # Confianza por campo (0-1): baja si el OCR dudó o si las cuentas no cuadran.
    confianza: dict[str, float] = Field(default_factory=dict)


class OCLeida(BaseModel):
    plantilla: str  # "hipermaxi", "generica"…
    cadena_texto: str | None = None
    numero_oc: str | None = None
    fecha_oc: date | None = None
    fecha_entrega: date | None = None
    destino_texto: str | None = None  # sucursal del supermercado tal como figura
    emisor: str | None = None
    total: Decimal | None = None
    lineas: list[LineaLeida] = Field(default_factory=list)
    confianza: dict[str, float] = Field(default_factory=dict)
    avisos: list[str] = Field(default_factory=list)

    @property
    def aritmetica_ok(self) -> bool:
        if not self.lineas:
            return False
        lineas_ok = all(
            linea.total is None
            or abs(linea.cantidad * linea.precio - linea.total) <= Decimal("0.01")
            for linea in self.lineas
        )
        suma = sum(
            (linea.total or linea.cantidad * linea.precio for linea in self.lineas), Decimal(0)
        )
        total_ok = self.total is None or abs(suma - self.total) <= Decimal("0.01")
        return lineas_ok and total_ok

    @property
    def confianza_global(self) -> float:
        valores = list(self.confianza.values()) + [
            v for linea in self.lineas for v in linea.confianza.values()
        ]
        return round(sum(valores) / len(valores), 3) if valores else 0.0
