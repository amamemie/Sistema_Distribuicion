from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.identidad.models import Auditoria
from tests.conftest import PASSWORD, Datos


def test_salud(cliente_anonimo: TestClient) -> None:
    assert cliente_anonimo.get("/api/salud").json() == {"estado": "ok"}


def test_login_exitoso_entrega_cookies_y_permisos(
    cliente_anonimo: TestClient, datos: Datos, db: Session
) -> None:
    r = cliente_anonimo.post(
        "/api/auth/login", json={"correo": "  DUENO@prueba.bo ", "password": PASSWORD}
    )
    assert r.status_code == 200
    assert "sesion" in r.cookies and "csrf_token" in r.cookies
    cuerpo = r.json()
    assert cuerpo["correo"] == "dueno@prueba.bo"
    assert "usuarios.gestionar" in cuerpo["permisos"]
    assert "password_hash" not in cuerpo

    yo = cliente_anonimo.get("/api/auth/yo")
    assert yo.status_code == 200
    assert db.scalar(select(Auditoria).where(Auditoria.accion == "sesion.iniciar")) is not None


def test_password_se_guarda_con_hash(datos: Datos) -> None:
    assert datos.dueno.password_hash.startswith("$argon2")
    assert PASSWORD not in datos.dueno.password_hash


def test_credenciales_incorrectas(cliente_anonimo: TestClient, datos: Datos) -> None:
    r = cliente_anonimo.post(
        "/api/auth/login", json={"correo": "dueno@prueba.bo", "password": "incorrecta"}
    )
    assert r.status_code == 401
    assert r.json()["detalle"] == "Correo o contraseña incorrectos."


def test_correo_inexistente_da_el_mismo_mensaje(cliente_anonimo: TestClient, datos: Datos) -> None:
    r = cliente_anonimo.post(
        "/api/auth/login", json={"correo": "nadie@prueba.bo", "password": PASSWORD}
    )
    assert r.status_code == 401
    assert r.json()["detalle"] == "Correo o contraseña incorrectos."


def test_usuario_inactivo_no_ingresa(
    cliente_anonimo: TestClient, datos: Datos, db: Session
) -> None:
    datos.encargado.activo = False
    db.commit()
    r = cliente_anonimo.post(
        "/api/auth/login", json={"correo": "encargado@prueba.bo", "password": PASSWORD}
    )
    assert r.status_code == 401
    assert "desactivada" in r.json()["detalle"]


def test_bloqueo_tras_intentos_fallidos(cliente_anonimo: TestClient, datos: Datos) -> None:
    for _ in range(5):
        cliente_anonimo.post(
            "/api/auth/login", json={"correo": "dueno@prueba.bo", "password": "mala"}
        )
    r = cliente_anonimo.post(
        "/api/auth/login", json={"correo": "dueno@prueba.bo", "password": PASSWORD}
    )
    assert r.status_code == 429


def test_sin_sesion_responde_401(cliente_anonimo: TestClient) -> None:
    r = cliente_anonimo.get("/api/auth/yo")
    assert r.status_code == 401
    assert r.json()["codigo"] == "no_autenticado"


def test_peticion_sin_csrf_es_rechazada(
    iniciar_sesion: Callable[[str], TestClient],
) -> None:
    cliente = iniciar_sesion("dueno@prueba.bo")
    del cliente.headers["X-CSRF-Token"]
    r = cliente.post("/api/auth/logout")
    assert r.status_code == 403


def test_logout_invalida_la_sesion(iniciar_sesion: Callable[[str], TestClient]) -> None:
    cliente = iniciar_sesion("dueno@prueba.bo")
    sesion = cliente.cookies["sesion"]
    assert cliente.post("/api/auth/logout").status_code == 204
    cliente.cookies.set("sesion", sesion)  # reutilizar la cookie robada no sirve
    assert cliente.get("/api/auth/yo").status_code == 401


def test_cambiar_password(iniciar_sesion: Callable[[str], TestClient]) -> None:
    cliente = iniciar_sesion("encargado@prueba.bo")
    r = cliente.post(
        "/api/auth/cambiar-password",
        json={"password_actual": "otra", "password_nueva": "Nueva-clave-456"},
    )
    assert r.status_code == 422
    r = cliente.post(
        "/api/auth/cambiar-password",
        json={"password_actual": PASSWORD, "password_nueva": "Nueva-clave-456"},
    )
    assert r.status_code == 204
    assert cliente.get("/api/auth/yo").status_code == 200  # la sesión actual sigue viva


def test_errores_de_validacion_en_espanol(cliente_anonimo: TestClient) -> None:
    r = cliente_anonimo.post("/api/auth/login", json={"correo": "no-es-correo"})
    assert r.status_code == 422
    cuerpo = r.json()
    assert cuerpo["detalle"] == "Los datos enviados no son válidos."
    campos = {e["campo"]: e["mensaje"] for e in cuerpo["errores"]}
    assert campos["password"] == "Este campo es obligatorio."
    assert campos["correo"] == "Correo electrónico inválido."
