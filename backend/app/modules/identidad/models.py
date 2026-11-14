import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    String,
    Table,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.models import Base, ConFechas, ConId, DeEmpresa
from app.modules.organizacion.models import Ubicacion

usuario_rol = Table(
    "usuario_rol",
    Base.metadata,
    Column("usuario_id", ForeignKey("usuario.id", ondelete="CASCADE"), primary_key=True),
    Column("rol_id", ForeignKey("rol.id", ondelete="CASCADE"), primary_key=True),
)

rol_permiso = Table(
    "rol_permiso",
    Base.metadata,
    Column("rol_id", ForeignKey("rol.id", ondelete="CASCADE"), primary_key=True),
    Column("permiso_codigo", ForeignKey("permiso.codigo", ondelete="CASCADE"), primary_key=True),
)

usuario_ubicacion = Table(
    "usuario_ubicacion",
    Base.metadata,
    Column("usuario_id", ForeignKey("usuario.id", ondelete="CASCADE"), primary_key=True),
    Column("ubicacion_id", ForeignKey("ubicacion.id", ondelete="CASCADE"), primary_key=True),
)


class Permiso(Base):
    """Catálogo global de permisos. Se sincroniza desde app/modules/identidad/permisos.py."""

    __tablename__ = "permiso"

    codigo: Mapped[str] = mapped_column(String(60), primary_key=True)
    modulo: Mapped[str] = mapped_column(String(40))
    descripcion: Mapped[str] = mapped_column(String(200))


class Rol(ConId, ConFechas, DeEmpresa, Base):
    __tablename__ = "rol"
    __table_args__ = (UniqueConstraint("empresa_id", "nombre"),)

    nombre: Mapped[str] = mapped_column(String(60))
    descripcion: Mapped[str | None] = mapped_column(String(250))
    # Los roles del sistema (Dueño) no se pueden renombrar ni quitarles permisos.
    es_sistema: Mapped[bool] = mapped_column(default=False)

    permisos: Mapped[list[Permiso]] = relationship(secondary=rol_permiso, lazy="selectin")


class Usuario(ConId, ConFechas, DeEmpresa, Base):
    __tablename__ = "usuario"

    nombre: Mapped[str] = mapped_column(String(80))
    apellido: Mapped[str] = mapped_column(String(80))
    correo: Mapped[str] = mapped_column(String(254), unique=True)
    telefono: Mapped[str | None] = mapped_column(String(30))
    password_hash: Mapped[str] = mapped_column(String(255))
    activo: Mapped[bool] = mapped_column(default=True)
    ultimo_acceso: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ubicacion_predeterminada_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ubicacion.id")
    )

    roles: Mapped[list[Rol]] = relationship(secondary=usuario_rol, lazy="selectin")
    ubicaciones: Mapped[list[Ubicacion]] = relationship(
        secondary=usuario_ubicacion, lazy="selectin"
    )

    @property
    def permisos(self) -> set[str]:
        return {p.codigo for rol in self.roles for p in rol.permisos}

    @property
    def nombre_completo(self) -> str:
        return f"{self.nombre} {self.apellido}"


class Sesion(ConId, Base):
    """Sesión de navegador. Solo se guarda el hash del token, nunca el token."""

    __tablename__ = "sesion"

    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_token: Mapped[str] = mapped_column(String(64))
    creada_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expira_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revocada_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ip: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(300))

    usuario: Mapped[Usuario] = relationship(lazy="joined")


class IntentoLogin(Base):
    __tablename__ = "intento_login"
    __table_args__ = (
        Index("ix_intento_login_correo_fecha", "correo", "fecha"),
        Index("ix_intento_login_ip_fecha", "ip", "fecha"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    correo: Mapped[str] = mapped_column(String(254))
    ip: Mapped[str | None] = mapped_column(String(45))
    exitoso: Mapped[bool]
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Auditoria(Base):
    """Bitácora inmutable: un trigger en la base de datos impide UPDATE, DELETE y TRUNCATE."""

    __tablename__ = "auditoria"
    __table_args__ = (
        Index("ix_auditoria_entidad", "entidad", "entidad_id"),
        Index("ix_auditoria_fecha", "fecha"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    empresa_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("empresa.id"), index=True)
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuario.id"), index=True)
    accion: Mapped[str] = mapped_column(String(60))
    entidad: Mapped[str] = mapped_column(String(60))
    entidad_id: Mapped[str | None] = mapped_column(String(64))
    antes: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    despues: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    ip: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(300))
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    usuario: Mapped[Usuario | None] = relationship(lazy="joined")
