import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import CANTIDAD, Base, ConId, DeEmpresa


class Severidad(StrEnum):
    INFO = "INFO"
    AVISO = "AVISO"
    CRITICA = "CRITICA"


class EstadoAlerta(StrEnum):
    ACTIVA = "ACTIVA"
    RESUELTA = "RESUELTA"


class Alerta(ConId, DeEmpresa, Base):
    """Aviso generado por las reglas. Las de estado (stock bajo, lotes por vencer…) se resuelven
    solas cuando la condición desaparece; las de evento (margen bajo, anomalías…) las marca
    como atendidas un usuario. Nunca se borran."""

    __tablename__ = "alerta"
    __table_args__ = (
        # Una sola alerta activa por condición (p. ej. "stock_bajo:<ubicación>:<producto>").
        Index(
            "uq_alerta_activa",
            "empresa_id",
            "clave",
            unique=True,
            postgresql_where=text("estado = 'ACTIVA'"),
        ),
        Index("ix_alerta_estado_creada", "empresa_id", "estado", "creada_at"),
    )

    tipo: Mapped[str] = mapped_column(String(40))
    severidad: Mapped[Severidad] = mapped_column(String(10))
    clave: Mapped[str] = mapped_column(String(200))
    titulo: Mapped[str] = mapped_column(String(200))
    mensaje: Mapped[str] = mapped_column(String(1000))
    permiso: Mapped[str] = mapped_column(String(60))  # quién puede verla
    enlace: Mapped[str | None] = mapped_column(String(200))  # pantalla donde se atiende
    ubicacion_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ubicacion.id"))
    producto_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("producto.id"))
    datos: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    auto_resolver: Mapped[bool] = mapped_column(default=True)
    estado: Mapped[EstadoAlerta] = mapped_column(String(10), default=EstadoAlerta.ACTIVA)
    creada_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    vista_at: Mapped[datetime] = mapped_column(  # última vez que la regla la confirmó
        DateTime(timezone=True), server_default=func.now()
    )
    resuelta_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resuelta_por_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuario.id"))


class AlertaLeida(Base):
    __tablename__ = "alerta_leida"

    alerta_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("alerta.id"), primary_key=True)
    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"), primary_key=True)
    leida_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Confianza(StrEnum):
    BAJA = "BAJA"
    MEDIA = "MEDIA"
    ALTA = "ALTA"


class Pronostico(ConId, DeEmpresa, Base):
    """Último pronóstico de demanda por ubicación y producto (se recalcula cada semana)."""

    __tablename__ = "pronostico"
    __table_args__ = (UniqueConstraint("empresa_id", "ubicacion_id", "producto_id"),)

    ubicacion_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ubicacion.id"))
    producto_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("producto.id"), index=True)
    calculado_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    metodo: Mapped[str] = mapped_column(String(40))
    semanas: Mapped[int]  # semanas de historial usadas
    demanda_semanal: Mapped[Decimal] = mapped_column(CANTIDAD)
    desviacion_semanal: Mapped[Decimal] = mapped_column(CANTIDAD)
    error_medio: Mapped[Decimal | None] = mapped_column(CANTIDAD)  # MAE del backtesting
    confianza: Mapped[Confianza] = mapped_column(String(10))
    historial: Mapped[list[Any]] = mapped_column(JSONB, default=list)  # unidades por semana
