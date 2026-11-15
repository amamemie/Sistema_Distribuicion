"""Extracción de texto con posiciones, 100 % local (ADR 0003).

- PDF con capa de texto: se lee directamente con pdfplumber (exacto, sin OCR).
- Foto o PDF escaneado: RapidOCR (modelos PaddleOCR en ONNX, CPU). Antes se detecta la
  orientación de la hoja (fotos de costado o de cabeza) y se mejora el contraste.

Las librerías pesadas se importan solo al leer, para no demorar el arranque de la API.
"""

import io
import logging
import threading
from functools import lru_cache
from typing import Any, Protocol

from app.modules.documentos.lectura.modelos import Palabra

logger = logging.getLogger(__name__)
MOTOR = "local:rapidocr"
_MIN_PALABRAS_PDF = 25  # menos que esto: el PDF es un escaneo y se pasa por OCR
_LADO_OCR = 2400
_candado = threading.Lock()


class ExtractorDocumento(Protocol):
    """Interfaz para poder cambiar de motor (otro OCR, o un servicio en la nube opcional)."""

    nombre: str

    def extraer(self, archivos: list[tuple[bytes, str]]) -> list[Palabra]: ...


@lru_cache(maxsize=1)
def _motor() -> Any:
    import onnxruntime
    from rapidocr import RapidOCR

    # Ningún dato sale del equipo: se apaga la telemetría de ONNX Runtime.
    onnxruntime.disable_telemetry_events()

    return RapidOCR(params={"Global.log_level": "error", "Global.max_side_len": _LADO_OCR})


def _ocr(imagen: Any, *, clasificar: bool = True) -> list[tuple[list[list[float]], str, float]]:
    with _candado:  # el motor ONNX no es seguro entre hilos
        r = _motor()(imagen, use_cls=clasificar)
    if r.boxes is None or r.txts is None:
        return []
    return [
        (caja.tolist(), txt, float(sc))
        for caja, txt, sc in zip(r.boxes, r.txts, r.scores, strict=True)
    ]


def _rotar(imagen: Any, grados: int) -> Any:
    import cv2

    codigos = {
        90: cv2.ROTATE_90_CLOCKWISE,
        180: cv2.ROTATE_180,
        270: cv2.ROTATE_90_COUNTERCLOCKWISE,
    }
    return imagen if grados == 0 else cv2.rotate(imagen, codigos[grados])


def _reducida(imagen: Any, lado: int) -> Any:
    import cv2

    alto, ancho = imagen.shape[:2]
    escala = lado / max(alto, ancho)
    return imagen if escala >= 1 else cv2.resize(imagen, (int(ancho * escala), int(alto * escala)))


def _puntaje(resultado: list[tuple[list[list[float]], str, float]]) -> float:
    """Texto legible: muchas cajas con buena confianza y más anchas que altas."""
    total = 0.0
    for caja, txt, sc in resultado:
        ancho = abs(caja[1][0] - caja[0][0])
        alto = abs(caja[3][1] - caja[0][1])
        if sc > 0.8 and ancho > alto:
            total += sc * min(len(txt), 30)
    return total


_LEGIBLE = 1500  # puntaje con el que una orientación se acepta sin probar las demás


def orientar(imagen: Any) -> tuple[Any, int]:
    """Prueba las orientaciones en una versión reducida y se queda con la más legible.
    Si la foto ya viene derecha (lo habitual) no prueba las demás."""
    chica = _reducida(imagen, 1000)
    puntajes: dict[int, float] = {}
    for grados in (0, 90, 270, 180):
        puntajes[grados] = _puntaje(_ocr(_rotar(chica, grados), clasificar=False))
        if puntajes[grados] >= _LEGIBLE:
            break
    mejor = max(puntajes, key=lambda g: puntajes[g])
    return _rotar(imagen, mejor), mejor


def _mejorar(imagen: Any) -> Any:
    """Contraste local (CLAHE) en escala de grises: ayuda con sombras y papel arrugado."""
    import cv2

    gris = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY) if imagen.ndim == 3 else imagen
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return cv2.cvtColor(clahe.apply(gris), cv2.COLOR_GRAY2BGR)


def _palabras_de_imagen(imagen: Any, pagina: int) -> list[Palabra]:
    imagen, grados = orientar(_reducida(imagen, _LADO_OCR))
    logger.info("lectura: página %s rotada %s°", pagina, grados)
    palabras = []
    for caja, txt, sc in _ocr(_mejorar(imagen)):
        xs = [p[0] for p in caja]
        ys = [p[1] for p in caja]
        palabras.append(Palabra(txt, min(xs), min(ys), max(xs), max(ys), sc, pagina))
    return palabras


def leer_imagen(contenido: bytes, pagina: int = 1) -> list[Palabra]:
    import cv2
    import numpy as np

    imagen = cv2.imdecode(np.frombuffer(contenido, np.uint8), cv2.IMREAD_COLOR)
    if imagen is None:
        raise ValueError("No se pudo abrir la imagen.")
    return _palabras_de_imagen(imagen, pagina)


def leer_pdf(contenido: bytes, primera_pagina: int = 1) -> list[Palabra]:
    import numpy as np
    import pdfplumber

    palabras: list[Palabra] = []
    with pdfplumber.open(io.BytesIO(contenido)) as pdf:
        for i, pagina in enumerate(pdf.pages):
            numero = primera_pagina + i
            texto = pagina.extract_words(keep_blank_chars=False, use_text_flow=False)
            if len(texto) >= _MIN_PALABRAS_PDF:
                palabras += [
                    Palabra(w["text"], w["x0"], w["top"], w["x1"], w["bottom"], 1.0, numero)
                    for w in texto
                ]
            else:
                imagen = pagina.to_image(resolution=200).original.convert("RGB")
                arreglo = np.array(imagen)[:, :, ::-1].copy()  # RGB → BGR (OpenCV)
                palabras += _palabras_de_imagen(arreglo, numero)
    return palabras


class ExtractorLocal:
    nombre = MOTOR

    def extraer(self, archivos: list[tuple[bytes, str]]) -> list[Palabra]:
        palabras: list[Palabra] = []
        pagina = 1
        for contenido, tipo in archivos:
            nuevas = (
                leer_pdf(contenido, pagina)
                if tipo == "application/pdf"
                else leer_imagen(contenido, pagina)
            )
            pagina = max((p.pagina for p in nuevas), default=pagina) + 1
            palabras += nuevas
        return palabras
