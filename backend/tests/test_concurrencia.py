"""Dos usuarios retiran el mismo stock al mismo tiempo: solo uno debe lograrlo.

A diferencia del resto, esta prueba usa transacciones reales confirmadas (cada hilo con su
propia conexión), así que limpia las tablas al terminar.
"""

import threading
import uuid
from collections.abc import Iterator
from decimal import Decimal as D

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.db import engine
from app.core.errors import ReglaNegocio
from app.core.models import Base
from app.modules.compras.schemas import CompraLineaEntrada
from app.modules.identidad.contexto import Contexto
from app.modules.identidad.models import Usuario
from app.modules.identidad.permisos import ROL_DUENO
from app.modules.identidad.semilla import asegurar_roles, sincronizar_permisos
from app.modules.inventario import consultas
from app.modules.inventario import servicios as inventario
from app.modules.inventario.models import StockUbicacion
from app.modules.inventario.schemas import TransferenciaEntrada, TransferenciaLineaEntrada
from app.modules.organizacion.models import Empresa, TipoUbicacion, Ubicacion
from tests.conftest import _HASH
from tests.fabrica import comprar, crear_catalogo


@pytest.fixture
def escenario() -> Iterator[dict[str, uuid.UUID]]:
    with Session(engine, expire_on_commit=False) as db:
        sincronizar_permisos(db)
        empresa = Empresa(nombre="Concurrencia")
        db.add(empresa)
        db.flush()
        roles = asegurar_roles(db, empresa)
        dueno = Usuario(
            empresa_id=empresa.id,
            nombre="D",
            apellido="C",
            correo="c@prueba.bo",
            password_hash=_HASH,
            roles=[roles[ROL_DUENO]],
        )
        deposito = Ubicacion(empresa_id=empresa.id, nombre="Dep", tipo=TipoUbicacion.DEPOSITO)
        sucursal = Ubicacion(empresa_id=empresa.id, nombre="Suc", tipo=TipoUbicacion.SUCURSAL)
        db.add_all([dueno, deposito, sucursal])
        db.commit()
        ctx = Contexto(usuario=dueno, ip=None, user_agent=None)
        cat = crear_catalogo(db, ctx)
        comprar(
            db,
            ctx,
            cat,
            deposito.id,
            [
                CompraLineaEntrada(
                    producto_id=cat.guantes.id, cantidad=D(300), precio_presentacion=D(1)
                )
            ],
        )
        ids = {
            "usuario": dueno.id,
            "deposito": deposito.id,
            "sucursal": sucursal.id,
            "producto": cat.guantes.id,
        }
    yield ids
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE auditoria DISABLE TRIGGER USER"))
        conn.execute(text("ALTER TABLE movimiento DISABLE TRIGGER USER"))
        tablas = ", ".join(t.name for t in Base.metadata.sorted_tables)
        conn.execute(text(f"TRUNCATE {tablas} RESTART IDENTITY CASCADE"))
        conn.execute(text("ALTER TABLE auditoria ENABLE TRIGGER USER"))
        conn.execute(text("ALTER TABLE movimiento ENABLE TRIGGER USER"))


def test_dos_salidas_simultaneas_no_dejan_stock_negativo(escenario: dict[str, uuid.UUID]) -> None:
    barrera = threading.Barrier(2)
    resultados: list[str] = []

    def transferir() -> None:
        with Session(engine, expire_on_commit=False) as db:
            usuario = db.get(Usuario, escenario["usuario"])
            assert usuario is not None
            ctx = Contexto(usuario=usuario, ip=None, user_agent=None)
            datos = TransferenciaEntrada(
                origen_id=escenario["deposito"],
                destino_id=escenario["sucursal"],
                lineas=[
                    TransferenciaLineaEntrada(producto_id=escenario["producto"], cantidad=D(200))
                ],
            )
            barrera.wait()
            try:
                inventario.transferir(db, ctx, datos)
                resultados.append("ok")
            except ReglaNegocio:
                db.rollback()
                resultados.append("rechazada")

    hilos = [threading.Thread(target=transferir) for _ in range(2)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join(timeout=30)

    assert sorted(resultados) == ["ok", "rechazada"]
    with Session(engine) as db:
        saldos = {
            s.ubicacion_id: s.fisico
            for s in db.scalars(
                select(StockUbicacion).where(StockUbicacion.producto_id == escenario["producto"])
            )
        }
        assert saldos == {escenario["deposito"]: 100, escenario["sucursal"]: 200}
        usuario = db.get(Usuario, escenario["usuario"])
        assert usuario is not None
        assert consultas.verificar(db, Contexto(usuario=usuario, ip=None, user_agent=None)).correcto
