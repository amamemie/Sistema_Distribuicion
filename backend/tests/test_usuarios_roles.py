from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.modules.identidad.models import Auditoria
from app.modules.identidad.permisos import CODIGOS, ROL_DUENO, ROL_ENCARGADO
from tests.conftest import PASSWORD, Datos

Login = Callable[[str], TestClient]


def _nuevo_usuario(datos: Datos, **extra: object) -> dict[str, object]:
    cuerpo: dict[str, object] = {
        "nombre": "Juan",
        "apellido": "Pérez",
        "correo": "juan@prueba.bo",
        "password": "Clave-larga-789",
        "rol_ids": [str(datos.roles[ROL_ENCARGADO].id)],
        "ubicacion_ids": [str(datos.sucursal.id)],
        "ubicacion_predeterminada_id": str(datos.sucursal.id),
    }
    cuerpo.update(extra)
    return cuerpo


def test_dueno_tiene_todos_los_permisos(datos: Datos) -> None:
    assert datos.dueno.permisos == set(CODIGOS)


def test_encargado_no_ve_costos(datos: Datos) -> None:
    assert "costos.ver" not in datos.encargado.permisos
    assert "reportes.rentabilidad" not in datos.encargado.permisos


def test_crear_usuario_queda_auditado(iniciar_sesion: Login, datos: Datos, db: Session) -> None:
    cliente = iniciar_sesion("dueno@prueba.bo")
    r = cliente.post("/api/usuarios", json=_nuevo_usuario(datos))
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert cuerpo["roles"][0]["nombre"] == ROL_ENCARGADO
    assert cuerpo["ubicaciones"][0]["nombre"] == "Sucursal A"

    registro = db.scalar(select(Auditoria).where(Auditoria.accion == "usuario.crear"))
    assert registro is not None
    assert registro.usuario_id == datos.dueno.id
    assert registro.despues is not None and "password" not in str(registro.despues)

    nuevo = TestClient(cliente.app)
    r = nuevo.post(
        "/api/auth/login", json={"correo": "juan@prueba.bo", "password": "Clave-larga-789"}
    )
    assert r.status_code == 200


def test_encargado_no_puede_gestionar_usuarios(iniciar_sesion: Login, datos: Datos) -> None:
    cliente = iniciar_sesion("encargado@prueba.bo")
    assert cliente.get("/api/usuarios").status_code == 403
    assert cliente.post("/api/usuarios", json=_nuevo_usuario(datos)).status_code == 403


def test_admin_ve_usuarios_pero_no_los_gestiona(iniciar_sesion: Login, datos: Datos) -> None:
    cliente = iniciar_sesion("admin@prueba.bo")
    assert cliente.get("/api/usuarios").status_code == 200
    assert cliente.post("/api/usuarios", json=_nuevo_usuario(datos)).status_code == 403


def test_correo_duplicado(iniciar_sesion: Login, datos: Datos) -> None:
    cliente = iniciar_sesion("dueno@prueba.bo")
    r = cliente.post("/api/usuarios", json=_nuevo_usuario(datos, correo="ADMIN@prueba.bo"))
    assert r.status_code == 409


def test_predeterminada_debe_estar_asignada(iniciar_sesion: Login, datos: Datos) -> None:
    cliente = iniciar_sesion("dueno@prueba.bo")
    r = cliente.post(
        "/api/usuarios",
        json=_nuevo_usuario(datos, ubicacion_predeterminada_id=str(datos.deposito.id)),
    )
    assert r.status_code == 422


def test_no_puede_desactivarse_a_si_mismo(iniciar_sesion: Login, datos: Datos) -> None:
    cliente = iniciar_sesion("dueno@prueba.bo")
    r = cliente.patch(f"/api/usuarios/{datos.dueno.id}", json={"activo": False})
    assert r.status_code == 422


def test_debe_quedar_un_dueno(iniciar_sesion: Login, datos: Datos) -> None:
    cliente = iniciar_sesion("dueno@prueba.bo")
    r = cliente.patch(
        f"/api/usuarios/{datos.dueno.id}",
        json={"rol_ids": [str(datos.roles[ROL_ENCARGADO].id)]},
    )
    assert r.status_code == 422
    # El cambio fallido no debe haberse aplicado.
    yo = cliente.get("/api/auth/yo").json()
    assert [r["nombre"] for r in yo["roles"]] == [ROL_DUENO]


def test_desactivar_cierra_sesiones(iniciar_sesion: Login, datos: Datos) -> None:
    encargado = iniciar_sesion("encargado@prueba.bo")
    dueno = iniciar_sesion("dueno@prueba.bo")
    r = dueno.patch(f"/api/usuarios/{datos.encargado.id}", json={"activo": False})
    assert r.status_code == 200
    assert encargado.get("/api/auth/yo").status_code == 401


def test_restablecer_password(iniciar_sesion: Login, datos: Datos) -> None:
    dueno = iniciar_sesion("dueno@prueba.bo")
    r = dueno.post(
        f"/api/usuarios/{datos.encargado.id}/restablecer-password",
        json={"password": "Restablecida-001"},
    )
    assert r.status_code == 204
    anon = TestClient(dueno.app)
    login = {"correo": "encargado@prueba.bo", "password": PASSWORD}
    assert anon.post("/api/auth/login", json=login).status_code == 401


def test_crear_rol_personalizado(iniciar_sesion: Login, datos: Datos) -> None:
    cliente = iniciar_sesion("dueno@prueba.bo")
    r = cliente.post(
        "/api/roles",
        json={"nombre": "Contador", "permisos": ["reportes.rentabilidad", "costos.ver"]},
    )
    assert r.status_code == 201
    assert r.json()["permisos"] == ["costos.ver", "reportes.rentabilidad"]


def test_permiso_desconocido(iniciar_sesion: Login, datos: Datos) -> None:
    cliente = iniciar_sesion("dueno@prueba.bo")
    r = cliente.post("/api/roles", json={"nombre": "Raro", "permisos": ["no.existe"]})
    assert r.status_code == 422


def test_rol_dueno_no_se_modifica(iniciar_sesion: Login, datos: Datos) -> None:
    cliente = iniciar_sesion("dueno@prueba.bo")
    r = cliente.patch(f"/api/roles/{datos.roles[ROL_DUENO].id}", json={"permisos": []})
    assert r.status_code == 422


def test_auditoria_es_inmutable(datos: Datos, db: Session) -> None:
    db.add(Auditoria(accion="prueba", entidad="prueba"))
    db.flush()
    with pytest.raises(DBAPIError, match="inmutable"), db.begin_nested():
        db.execute(text("UPDATE auditoria SET accion = 'alterada'"))
    with pytest.raises(DBAPIError, match="inmutable"), db.begin_nested():
        db.execute(text("DELETE FROM auditoria"))


def test_consultar_auditoria(iniciar_sesion: Login, datos: Datos) -> None:
    dueno = iniciar_sesion("dueno@prueba.bo")
    dueno.post("/api/usuarios", json=_nuevo_usuario(datos))
    r = dueno.get("/api/auditoria", params={"entidad": "usuario", "accion": "usuario."})
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["total"] >= 1
    assert cuerpo["items"][0]["usuario_nombre"] == "Dueño Prueba"

    admin = iniciar_sesion("admin@prueba.bo")
    assert admin.get("/api/auditoria").status_code == 403


def test_ubicaciones(iniciar_sesion: Login, datos: Datos) -> None:
    dueno = iniciar_sesion("dueno@prueba.bo")
    r = dueno.post("/api/ubicaciones", json={"nombre": "Sucursal B", "tipo": "SUCURSAL"})
    assert r.status_code == 201
    assert (
        dueno.post(
            "/api/ubicaciones", json={"nombre": "sucursal b", "tipo": "DEPOSITO"}
        ).status_code
        == 409
    )
    assert (
        dueno.post("/api/ubicaciones", json={"nombre": "Otra", "tipo": "OFICINA"}).status_code
        == 422
    )

    encargado = iniciar_sesion("encargado@prueba.bo")
    assert encargado.get("/api/ubicaciones").status_code == 200
    assert (
        encargado.post("/api/ubicaciones", json={"nombre": "X", "tipo": "SUCURSAL"}).status_code
        == 403
    )
