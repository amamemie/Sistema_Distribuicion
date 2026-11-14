"""Base declarativa y mixins comunes a todas las tablas."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, MetaData, Numeric, func
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column

CONVENCION_NOMBRES = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


# Tipos numéricos exactos usados en todo el sistema (nunca float).
CANTIDAD = Numeric(14, 3)  # cantidades en unidad base
COSTO_UNITARIO = Numeric(18, 6)  # costo por unidad base
DINERO = Numeric(14, 2)  # importes en bolivianos
VALOR = Numeric(16, 4)  # valoraciones internas (cantidad x costo) antes de redondear


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=CONVENCION_NOMBRES)


class ConId:
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)


class ConFechas:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DeEmpresa:
    """Toda tabla de negocio pertenece a una empresa (preparado para multiempresa)."""

    @declared_attr
    def empresa_id(cls) -> Mapped[uuid.UUID]:
        return mapped_column(ForeignKey("empresa.id"), index=True)
