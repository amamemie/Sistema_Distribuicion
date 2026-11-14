import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import Base, ConId, DeEmpresa


class Archivo(ConId, DeEmpresa, Base):
    """Archivo subido (página de una OC, constancia de entrega…). El contenido vive en disco;
    aquí quedan sus datos y su huella SHA-256. Nunca se borra."""

    __tablename__ = "archivo"

    nombre_original: Mapped[str] = mapped_column(String(255))
    tipo_mime: Mapped[str] = mapped_column(String(100))
    tamano: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    ruta: Mapped[str] = mapped_column(String(500))  # relativa a ARCHIVOS_DIR
    subido_por_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
