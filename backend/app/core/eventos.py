"""Eventos de dominio (patrón outbox).

Los servicios publican eventos en la misma transacción que el cambio. Módulos futuros
(alertas, ML, finanzas) los consumen sin acoplarse a quien los produjo.
"""

import uuid
from datetime import datetime
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.models import Base


class EventoDominio(Base):
    __tablename__ = "evento_dominio"
    __table_args__ = (Index("ix_evento_dominio_pendientes", "procesado_at", "id"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"))
    tipo: Mapped[str] = mapped_column(String(60))
    agregado: Mapped[str] = mapped_column(String(40))
    agregado_id: Mapped[str] = mapped_column(String(64))
    datos: Mapped[dict[str, Any]] = mapped_column(JSONB)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    procesado_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


def publicar(
    db: Session,
    *,
    empresa_id: uuid.UUID,
    tipo: str,
    agregado: str,
    agregado_id: uuid.UUID | str,
    datos: dict[str, Any],
) -> None:
    db.add(
        EventoDominio(
            empresa_id=empresa_id,
            tipo=tipo,
            agregado=agregado,
            agregado_id=str(agregado_id),
            datos=jsonable_encoder(datos),
        )
    )
