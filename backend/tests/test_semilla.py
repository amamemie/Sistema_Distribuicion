import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.identidad.models import Rol, Usuario
from app.modules.identidad.permisos import CODIGOS, ROL_DUENO
from app.modules.identidad.semilla import inicializar


def test_inicializar_es_idempotente(db: Session) -> None:
    for _ in range(2):
        empresa = inicializar(
            db,
            nombre_empresa="Distribuidora",
            correo_dueno="Dueno@Example.com",
            password_dueno="Clave-segura-123",
        )
    assert db.scalar(select(func.count()).select_from(Usuario)) == 1
    assert db.scalar(select(func.count()).select_from(Rol)) == 3
    dueno = db.scalar(select(Usuario).where(Usuario.correo == "dueno@example.com"))
    assert dueno is not None and dueno.empresa_id == empresa.id
    assert [r.nombre for r in dueno.roles] == [ROL_DUENO]
    assert dueno.permisos == set(CODIGOS)


def test_inicializar_rechaza_correo_inutilizable(db: Session) -> None:
    with pytest.raises(ValueError, match="Correo del dueño inválido"):
        inicializar(
            db,
            nombre_empresa="Distribuidora",
            correo_dueno="dueno@empresa.local",
            password_dueno="Clave-segura-123",
        )
