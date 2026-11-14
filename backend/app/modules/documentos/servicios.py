"""Almacenamiento de archivos en el disco del servidor (costo cero, incluido en el respaldo).

Solo se aceptan imágenes JPEG/PNG/WebP y PDF, reconocidos por su contenido (no por la
extensión que envía el navegador).
"""

import hashlib
import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import NoEncontrado, ReglaNegocio
from app.core.tiempo import hoy
from app.modules.documentos.models import Archivo
from app.modules.identidad.contexto import Contexto

TIPOS: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "application/pdf": ".pdf",
}
_BLOQUE = 1024 * 1024


def detectar_tipo(cabecera: bytes) -> str | None:
    if cabecera.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if cabecera.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if cabecera[:4] == b"RIFF" and cabecera[8:12] == b"WEBP":
        return "image/webp"
    if cabecera.startswith(b"%PDF-"):
        return "application/pdf"
    return None


def _raiz() -> Path:
    return Path(get_settings().archivos_dir)


def leer_subida(subida: UploadFile) -> bytes:
    maximo = get_settings().archivo_max_mb * _BLOQUE
    partes: list[bytes] = []
    total = 0
    while bloque := subida.file.read(_BLOQUE):
        total += len(bloque)
        if total > maximo:
            raise ReglaNegocio(
                f"«{subida.filename}» supera el tamaño máximo de "
                f"{get_settings().archivo_max_mb} MB."
            )
        partes.append(bloque)
    if total == 0:
        raise ReglaNegocio(f"«{subida.filename}» está vacío.")
    return b"".join(partes)


def guardar(
    db: Session,
    ctx: Contexto,
    contenido: bytes,
    nombre: str | None,
    *,
    solo_imagen: bool = False,
) -> Archivo:
    """Guarda el contenido en disco y registra el archivo (sin commit: lo hace el caso de uso)."""
    nombre = (nombre or "archivo").strip()[:255] or "archivo"
    tipo = detectar_tipo(contenido[:16])
    if tipo is None:
        raise ReglaNegocio(f"«{nombre}» no es una imagen (JPG, PNG, WebP) ni un PDF.")
    if solo_imagen and not tipo.startswith("image/"):
        raise ReglaNegocio(f"«{nombre}» debe ser una imagen.")
    archivo_id = uuid.uuid4()
    fecha = hoy()
    relativa = Path(str(ctx.empresa_id), f"{fecha:%Y}", f"{fecha:%m}", f"{archivo_id}{TIPOS[tipo]}")
    destino = _raiz() / relativa
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_suffix(destino.suffix + ".tmp")
    temporal.write_bytes(contenido)
    temporal.replace(destino)
    archivo = Archivo(
        id=archivo_id,
        empresa_id=ctx.empresa_id,
        nombre_original=nombre,
        tipo_mime=tipo,
        tamano=len(contenido),
        sha256=hashlib.sha256(contenido).hexdigest(),
        ruta=str(relativa),
        subido_por_id=ctx.usuario.id,
    )
    db.add(archivo)
    db.flush()
    return archivo


def obtener(db: Session, ctx: Contexto, archivo_id: uuid.UUID) -> Archivo:
    archivo = db.get(Archivo, archivo_id)
    if archivo is None or archivo.empresa_id != ctx.empresa_id:
        raise NoEncontrado("El archivo no existe.")
    return archivo


def ruta_absoluta(archivo: Archivo) -> Path:
    ruta = (_raiz() / archivo.ruta).resolve()
    if not ruta.is_relative_to(_raiz().resolve()) or not ruta.is_file():
        raise NoEncontrado("El contenido del archivo no está disponible en el servidor.")
    return ruta
