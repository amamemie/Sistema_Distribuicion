"""Comandos de administración.

python -m app.cli inicializar   # permisos, roles base, empresa y usuario dueño (idempotente)
python -m app.cli demo          # ubicaciones y usuarios de prueba (solo desarrollo)
"""

import argparse
import os
import sys

from sqlalchemy import select

from app import demo
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.security import hash_password
from app.modules.identidad.contexto import Contexto
from app.modules.identidad.models import Rol, Usuario
from app.modules.identidad.permisos import ROL_ADMINISTRADOR, ROL_DUENO, ROL_ENCARGADO
from app.modules.identidad.semilla import inicializar
from app.modules.organizacion.models import Empresa, TipoUbicacion, Ubicacion

PASSWORD_DEMO = "Demo-12345"


def _requerida(nombre: str) -> str:
    valor = os.environ.get(nombre)
    if not valor:
        sys.exit(f"Falta la variable de entorno {nombre}.")
    return valor


def cmd_inicializar() -> None:
    with SessionLocal() as db:
        empresa = inicializar(
            db,
            nombre_empresa=os.environ.get("EMPRESA_NOMBRE", "Mi Distribuidora"),
            correo_dueno=_requerida("DUENO_CORREO"),
            password_dueno=_requerida("DUENO_PASSWORD"),
            nombre_dueno=os.environ.get("DUENO_NOMBRE", "Dueño"),
            apellido_dueno=os.environ.get("DUENO_APELLIDO", ""),
        )
        print(f"Inicialización completa para la empresa «{empresa.nombre}».")


def cmd_demo() -> None:
    if get_settings().entorno == "produccion":
        sys.exit("Los datos de demostración no se pueden cargar en producción.")
    with SessionLocal() as db:
        empresa = db.scalar(select(Empresa).order_by(Empresa.created_at))
        if empresa is None:
            sys.exit("Primero ejecute: python -m app.cli inicializar")
        ubicaciones = {
            "Depósito Central": TipoUbicacion.DEPOSITO,
            "Depósito El Alto": TipoUbicacion.DEPOSITO,
            "Sucursal Centro": TipoUbicacion.SUCURSAL,
            "Sucursal Sur": TipoUbicacion.SUCURSAL,
        }
        existentes = {
            u.nombre: u
            for u in db.scalars(select(Ubicacion).where(Ubicacion.empresa_id == empresa.id))
        }
        for nombre, tipo in ubicaciones.items():
            if nombre not in existentes:
                existentes[nombre] = Ubicacion(empresa_id=empresa.id, nombre=nombre, tipo=tipo)
                db.add(existentes[nombre])
        db.flush()

        roles = {r.nombre: r for r in db.scalars(select(Rol).where(Rol.empresa_id == empresa.id))}
        usuarios = [
            ("admin@example.com", "Ana", "Administradora", ROL_ADMINISTRADOR, list(existentes)),
            ("encargado@example.com", "Elías", "Encargado", ROL_ENCARGADO, ["Sucursal Centro"]),
        ]
        for correo, nombre, apellido, rol, ubics in usuarios:
            if db.scalar(select(Usuario).where(Usuario.correo == correo)) is None:
                db.add(
                    Usuario(
                        empresa_id=empresa.id,
                        nombre=nombre,
                        apellido=apellido,
                        correo=correo,
                        password_hash=hash_password(PASSWORD_DEMO),
                        roles=[roles[rol]],
                        ubicaciones=[existentes[u] for u in ubics],
                        ubicacion_predeterminada_id=existentes[ubics[0]].id,
                    )
                )
        db.commit()

        dueno = db.scalar(
            select(Usuario)
            .join(Usuario.roles)
            .where(Usuario.empresa_id == empresa.id, Rol.nombre == ROL_DUENO)
            .limit(1)
        )
        if dueno is not None:
            ctx = Contexto(usuario=dueno, ip=None, user_agent="cli demo")
            if demo.cargar(db, ctx):
                print(
                    "Catálogo, proveedores, cadenas, compras y transferencias de ejemplo cargados."
                )
            else:
                print("El catálogo ya tenía productos: no se cargó inventario de ejemplo.")
    print(f"Datos de demostración cargados. Contraseña de los usuarios demo: {PASSWORD_DEMO}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    parser.add_argument("comando", choices=["inicializar", "demo"])
    args = parser.parse_args()
    {"inicializar": cmd_inicializar, "demo": cmd_demo}[args.comando]()


if __name__ == "__main__":
    main()
