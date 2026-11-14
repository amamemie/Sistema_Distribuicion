"""Fixtures de pruebas.

Usa una base PostgreSQL real (TEST_DATABASE_URL). Al iniciar la sesión de pruebas se recrea
el esquema con las migraciones de Alembic; cada prueba corre dentro de una transacción que
se revierte al final.
"""

import os

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://inventario:inventario@localhost:5432/inventario_test",
)
os.environ["ENTORNO"] = "pruebas"
os.environ["COOKIE_SEGURA"] = "false"

import tempfile

# Los archivos subidos en las pruebas van a una carpeta temporal.
os.environ["ARCHIVOS_DIR"] = tempfile.mkdtemp(prefix="inventario-archivos-")

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import modelos as _modelos  # noqa: F401
from app.core.db import engine, get_db
from app.core.security import hash_password
from app.main import app
from app.modules.identidad.models import Rol, Usuario
from app.modules.identidad.permisos import ROL_ADMINISTRADOR, ROL_DUENO, ROL_ENCARGADO
from app.modules.identidad.semilla import asegurar_roles, sincronizar_permisos
from app.modules.organizacion.models import Empresa, TipoUbicacion, Ubicacion

PASSWORD = "Clave-segura-123"
_HASH = hash_password(PASSWORD)


@pytest.fixture(scope="session", autouse=True)
def esquema() -> None:
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    cfg = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
    command.upgrade(cfg, "head")


@pytest.fixture
def db() -> Iterator[Session]:
    conexion = engine.connect()
    transaccion = conexion.begin()
    sesion = Session(
        bind=conexion,
        join_transaction_mode="create_savepoint",
        autoflush=False,
        expire_on_commit=False,
    )
    try:
        yield sesion
    finally:
        sesion.close()
        transaccion.rollback()
        conexion.close()


@pytest.fixture
def cliente_anonimo(db: Session) -> Iterator[TestClient]:
    def _get_db() -> Iterator[Session]:
        try:
            yield db
        except Exception:
            db.rollback()
            raise

    app.dependency_overrides[get_db] = _get_db
    with TestClient(app) as cliente:
        yield cliente
    app.dependency_overrides.clear()


@dataclass
class Datos:
    empresa: Empresa
    roles: dict[str, Rol]
    dueno: Usuario
    admin: Usuario
    encargado: Usuario
    sucursal: Ubicacion
    deposito: Ubicacion


@pytest.fixture
def datos(db: Session) -> Datos:
    sincronizar_permisos(db)
    empresa = Empresa(nombre="Distribuidora de Prueba")
    db.add(empresa)
    db.flush()
    roles = asegurar_roles(db, empresa)
    sucursal = Ubicacion(empresa_id=empresa.id, nombre="Sucursal A", tipo=TipoUbicacion.SUCURSAL)
    deposito = Ubicacion(empresa_id=empresa.id, nombre="Depósito A", tipo=TipoUbicacion.DEPOSITO)
    db.add_all([sucursal, deposito])

    def _usuario(correo: str, rol: str) -> Usuario:
        u = Usuario(
            empresa_id=empresa.id,
            nombre=rol,
            apellido="Prueba",
            correo=correo,
            password_hash=_HASH,
            roles=[roles[rol]],
        )
        db.add(u)
        return u

    dueno = _usuario("dueno@prueba.bo", ROL_DUENO)
    admin = _usuario("admin@prueba.bo", ROL_ADMINISTRADOR)
    encargado = _usuario("encargado@prueba.bo", ROL_ENCARGADO)
    db.commit()
    return Datos(empresa, roles, dueno, admin, encargado, sucursal, deposito)


@pytest.fixture
def iniciar_sesion(
    cliente_anonimo: TestClient, datos: Datos
) -> Iterator[Callable[[str], TestClient]]:
    """Devuelve un cliente autenticado (con la cabecera CSRF lista) para el correo dado."""
    abiertos: list[TestClient] = []

    def _iniciar(correo: str) -> TestClient:
        cliente = TestClient(app)
        abiertos.append(cliente)
        r = cliente.post("/api/auth/login", json={"correo": correo, "password": PASSWORD})
        assert r.status_code == 200, r.text
        cliente.headers["X-CSRF-Token"] = r.cookies["csrf_token"]
        return cliente

    yield _iniciar
    for c in abiertos:
        c.close()
