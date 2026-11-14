from collections.abc import Callable
from datetime import date, timedelta
from decimal import Decimal as D

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.modules.compras.schemas import CompraCostoEntrada, CompraLineaEntrada
from app.modules.identidad.contexto import Contexto
from app.modules.identidad.models import Rol, Usuario
from app.modules.inventario.models import StockUbicacion
from app.modules.organizacion.models import Empresa
from tests.conftest import _HASH, PASSWORD, Datos
from tests.fabrica import Catalogo, comprar, crear_catalogo, presentacion

Login = Callable[[str], TestClient]


@pytest.fixture
def ctx(datos: Datos) -> Contexto:
    return Contexto(usuario=datos.dueno, ip=None, user_agent=None)


@pytest.fixture
def cat(db: Session, ctx: Contexto) -> Catalogo:
    return crear_catalogo(db, ctx)


def _saldo(db: Session, ubicacion_id: object, producto_id: object) -> StockUbicacion | None:
    db.expire_all()
    return db.scalar(
        select(StockUbicacion).where(
            StockUbicacion.ubicacion_id == ubicacion_id, StockUbicacion.producto_id == producto_id
        )
    )


def _fardos(cat: Catalogo, cantidad: str, precio: str) -> CompraLineaEntrada:
    return CompraLineaEntrada(
        producto_id=cat.guantes.id,
        presentacion_id=presentacion(cat.guantes, "Fardo"),
        cantidad=D(cantidad),
        precio_presentacion=D(precio),
    )


def _verificar(cliente: TestClient) -> None:
    r = cliente.get("/api/inventario/verificacion")
    assert r.status_code == 200
    assert r.json()["correcto"], r.json()["diferencias"]


# ---------------------------------------------------------------- compras


def test_compra_ingresa_stock_y_calcula_costo_por_unidad(
    iniciar_sesion: Login, datos: Datos, cat: Catalogo, db: Session
) -> None:
    dueno = iniciar_sesion("dueno@prueba.bo")
    r = dueno.post(
        "/api/compras",
        json={
            "proveedor_id": str(cat.proveedor.id),
            "ubicacion_id": str(datos.deposito.id),
            "fecha": "2026-11-01",
            "numero_documento": "F-123",
            "lineas": [
                {
                    "producto_id": str(cat.guantes.id),
                    "presentacion_id": presentacion(cat.guantes, "Fardo"),
                    "cantidad": "4",
                    "precio_presentacion": "150",
                }
            ],
            "costos": [{"concepto": "Flete", "monto": "60"}],
        },
    )
    assert r.status_code == 201, r.text
    compra = r.json()
    linea = compra["lineas"][0]
    assert D(linea["cantidad_base"]) == 1200
    assert D(compra["total"]) == D("660")
    # (600 + 60 de flete) / 1200 unidades = Bs 0,55 por guante
    assert D(linea["costo_unitario_base"]) == D("0.55")

    saldo = _saldo(db, datos.deposito.id, cat.guantes.id)
    assert saldo is not None and saldo.fisico == 1200 and saldo.cpp == D("0.55")
    _verificar(dueno)


def test_segunda_compra_actualiza_el_costo_promedio(
    db: Session, ctx: Contexto, datos: Datos, cat: Catalogo
) -> None:
    comprar(db, ctx, cat, datos.deposito.id, [_fardos(cat, "4", "150")])  # 1200 u a 0.50
    comprar(db, ctx, cat, datos.deposito.id, [_fardos(cat, "2", "240")])  # 600 u a 0.80
    saldo = _saldo(db, datos.deposito.id, cat.guantes.id)
    assert saldo is not None and saldo.fisico == 1800 and saldo.cpp == D("0.6")


def test_flete_se_prorratea_entre_lineas(
    db: Session, ctx: Contexto, datos: Datos, cat: Catalogo
) -> None:
    compra = comprar(
        db,
        ctx,
        cat,
        datos.deposito.id,
        [
            _fardos(cat, "1", "300"),
            CompraLineaEntrada(
                producto_id=cat.leche.id,
                cantidad=D("100"),
                precio_presentacion=D("1"),
                lote_codigo="L1",
                lote_vencimiento=date(2027, 1, 1),
            ),
        ],
        costos=[CompraCostoEntrada(concepto="Flete", monto=D("40"))],
    )
    assert [linea.prorrateo for linea in compra.lineas] == [D("30.00"), D("10.00")]
    assert compra.total == D("440")


def test_producto_con_vencimiento_exige_lote(
    iniciar_sesion: Login, datos: Datos, cat: Catalogo
) -> None:
    dueno = iniciar_sesion("dueno@prueba.bo")
    r = dueno.post(
        "/api/compras",
        json={
            "proveedor_id": str(cat.proveedor.id),
            "ubicacion_id": str(datos.deposito.id),
            "fecha": "2026-11-01",
            "lineas": [
                {"producto_id": str(cat.leche.id), "cantidad": "12", "precio_presentacion": "6"}
            ],
        },
    )
    assert r.status_code == 422
    assert "vencimiento" in r.json()["detalle"]


def test_anular_compra(
    iniciar_sesion: Login, db: Session, ctx: Contexto, datos: Datos, cat: Catalogo
) -> None:
    comprar(db, ctx, cat, datos.deposito.id, [_fardos(cat, "4", "150")])
    segunda = comprar(db, ctx, cat, datos.deposito.id, [_fardos(cat, "2", "240")])
    dueno = iniciar_sesion("dueno@prueba.bo")
    r = dueno.post(f"/api/compras/{segunda.id}/anular", json={"motivo": "Factura duplicada"})
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "ANULADA"
    saldo = _saldo(db, datos.deposito.id, cat.guantes.id)
    assert saldo is not None and saldo.fisico == 1200 and saldo.cpp == D("0.5")
    assert (
        dueno.post(f"/api/compras/{segunda.id}/anular", json={"motivo": "otra vez"}).status_code
        == 422
    )
    _verificar(dueno)


# ---------------------------------------------------------------- transferencias


def test_transferencia_mueve_stock_y_costo(
    iniciar_sesion: Login, db: Session, ctx: Contexto, datos: Datos, cat: Catalogo
) -> None:
    comprar(db, ctx, cat, datos.deposito.id, [_fardos(cat, "4", "150")])
    dueno = iniciar_sesion("dueno@prueba.bo")
    r = dueno.post(
        "/api/transferencias",
        json={
            "origen_id": str(datos.deposito.id),
            "destino_id": str(datos.sucursal.id),
            "lineas": [
                {
                    "producto_id": str(cat.guantes.id),
                    "presentacion_id": presentacion(cat.guantes, "Fardo"),
                    "cantidad": "1",
                }
            ],
        },
    )
    assert r.status_code == 201, r.text
    origen = _saldo(db, datos.deposito.id, cat.guantes.id)
    destino = _saldo(db, datos.sucursal.id, cat.guantes.id)
    assert origen is not None and origen.fisico == 900
    assert destino is not None and destino.fisico == 300 and destino.cpp == D("0.5")

    # Anular la devuelve al origen.
    t_id = r.json()["id"]
    assert (
        dueno.post(
            f"/api/transferencias/{t_id}/anular", json={"motivo": "Error de carga"}
        ).status_code
        == 200
    )
    assert _saldo(db, datos.sucursal.id, cat.guantes.id).fisico == 0  # type: ignore[union-attr]
    assert _saldo(db, datos.deposito.id, cat.guantes.id).fisico == 1200  # type: ignore[union-attr]
    _verificar(dueno)


def test_no_se_puede_transferir_mas_de_lo_disponible(
    iniciar_sesion: Login, db: Session, ctx: Contexto, datos: Datos, cat: Catalogo
) -> None:
    comprar(db, ctx, cat, datos.deposito.id, [_fardos(cat, "1", "150")])
    dueno = iniciar_sesion("dueno@prueba.bo")
    r = dueno.post(
        "/api/transferencias",
        json={
            "origen_id": str(datos.deposito.id),
            "destino_id": str(datos.sucursal.id),
            "lineas": [{"producto_id": str(cat.guantes.id), "cantidad": "301"}],
        },
    )
    assert r.status_code == 422
    assert "Stock insuficiente" in r.json()["detalle"]
    assert _saldo(db, datos.sucursal.id, cat.guantes.id) is None or (
        _saldo(db, datos.sucursal.id, cat.guantes.id).fisico == 0  # type: ignore[union-attr]
    )


def test_fefo_y_lotes_vencidos(
    iniciar_sesion: Login, db: Session, ctx: Contexto, datos: Datos, cat: Catalogo
) -> None:
    def lote(codigo: str, vence: date) -> CompraLineaEntrada:
        return CompraLineaEntrada(
            producto_id=cat.leche.id,
            cantidad=D("10"),
            precio_presentacion=D("6"),
            lote_codigo=codigo,
            lote_vencimiento=vence,
        )

    ayer = date.today() - timedelta(days=1)
    comprar(
        db,
        ctx,
        cat,
        datos.deposito.id,
        [lote("TARDE", date(2027, 6, 1)), lote("PRONTO", date(2027, 1, 1)), lote("VENCIDO", ayer)],
    )
    dueno = iniciar_sesion("dueno@prueba.bo")
    r = dueno.post(
        "/api/transferencias",
        json={
            "origen_id": str(datos.deposito.id),
            "destino_id": str(datos.sucursal.id),
            "lineas": [{"producto_id": str(cat.leche.id), "cantidad": "15"}],
        },
    )
    assert r.status_code == 201, r.text
    lotes = dueno.get(
        "/api/inventario/lotes",
        params={"producto_id": str(cat.leche.id), "ubicacion_id": str(datos.sucursal.id)},
    ).json()
    # Se salta el lote vencido y toma primero el que vence antes (FEFO).
    assert {lt["codigo"]: D(lt["cantidad"]) for lt in lotes} == {"PRONTO": 10, "TARDE": 5}

    # Solo quedan 5 vigentes en el depósito (+10 vencidas): pedir 6 falla.
    r = dueno.post(
        "/api/transferencias",
        json={
            "origen_id": str(datos.deposito.id),
            "destino_id": str(datos.sucursal.id),
            "lineas": [{"producto_id": str(cat.leche.id), "cantidad": "6"}],
        },
    )
    assert r.status_code == 422
    assert "vencidas" in r.json()["detalle"]


# ---------------------------------------------------------------- ajustes


def _ajuste(
    cat: Catalogo, ubicacion_id: object, sentido: str, cantidad: str, motivo: str = "MERMA"
) -> dict[str, object]:
    return {
        "ubicacion_id": str(ubicacion_id),
        "motivo": motivo,
        "observacion": "Prueba de ajuste",
        "lineas": [{"producto_id": str(cat.guantes.id), "cantidad": cantidad, "sentido": sentido}],
    }


def test_ajuste_de_admin_requiere_aprobacion_del_dueno(
    iniciar_sesion: Login, db: Session, ctx: Contexto, datos: Datos, cat: Catalogo
) -> None:
    comprar(db, ctx, cat, datos.deposito.id, [_fardos(cat, "1", "150")])  # 300 u a 0.50
    admin = iniciar_sesion("admin@prueba.bo")
    r = admin.post("/api/ajustes", json=_ajuste(cat, datos.deposito.id, "DISMINUCION", "10"))
    assert r.status_code == 201, r.text
    ajuste = r.json()
    assert ajuste["estado"] == "PENDIENTE"
    assert ajuste["valor_total"] is None  # el administrador no ve costos por defecto
    assert _saldo(db, datos.deposito.id, cat.guantes.id).fisico == 300  # type: ignore[union-attr]
    assert admin.post(f"/api/ajustes/{ajuste['id']}/aprobar", json={}).status_code == 403

    dueno = iniciar_sesion("dueno@prueba.bo")
    r = dueno.post(f"/api/ajustes/{ajuste['id']}/aprobar", json={"nota": "Revisado"})
    assert r.status_code == 200
    assert r.json()["estado"] == "APLICADO"
    assert D(r.json()["valor_total"]) == D("-5.00")
    assert _saldo(db, datos.deposito.id, cat.guantes.id).fisico == 290  # type: ignore[union-attr]
    _verificar(dueno)


def test_umbral_permite_ajustes_menores_sin_aprobacion(
    iniciar_sesion: Login, db: Session, ctx: Contexto, datos: Datos, cat: Catalogo
) -> None:
    comprar(db, ctx, cat, datos.deposito.id, [_fardos(cat, "1", "150")])
    empresa = db.get(Empresa, datos.empresa.id)
    assert empresa is not None
    empresa.configuracion = {"umbral_ajuste_bs": 10}
    db.commit()
    admin = iniciar_sesion("admin@prueba.bo")
    r = admin.post("/api/ajustes", json=_ajuste(cat, datos.deposito.id, "DISMINUCION", "4"))
    assert r.json()["estado"] == "APLICADO"  # Bs 2 ≤ umbral de Bs 10


def test_reglas_de_ajuste(
    iniciar_sesion: Login, db: Session, ctx: Contexto, datos: Datos, cat: Catalogo
) -> None:
    dueno = iniciar_sesion("dueno@prueba.bo")
    # Sin costo registrado, un aumento exige indicar el costo.
    r = dueno.post(
        "/api/ajustes", json=_ajuste(cat, datos.deposito.id, "AUMENTO", "5", "CORRECCION")
    )
    assert r.status_code == 422 and "costo" in r.json()["detalle"]
    # Una rotura no puede aumentar stock.
    comprar(db, ctx, cat, datos.deposito.id, [_fardos(cat, "1", "150")])
    r = dueno.post("/api/ajustes", json=_ajuste(cat, datos.deposito.id, "AUMENTO", "5", "ROTURA"))
    assert r.status_code == 422
    # No se puede disminuir más de lo disponible.
    r = dueno.post("/api/ajustes", json=_ajuste(cat, datos.deposito.id, "DISMINUCION", "301"))
    assert r.status_code == 422
    # El dueño aplica directamente.
    r = dueno.post(
        "/api/ajustes", json=_ajuste(cat, datos.deposito.id, "AUMENTO", "5", "CORRECCION")
    )
    assert r.json()["estado"] == "APLICADO"
    assert _saldo(db, datos.deposito.id, cat.guantes.id).fisico == 305  # type: ignore[union-attr]


# ---------------------------------------------------------------- conteo físico


def test_conteo_fisico_genera_ajuste_por_diferencias(
    iniciar_sesion: Login, db: Session, ctx: Contexto, datos: Datos, cat: Catalogo
) -> None:
    comprar(db, ctx, cat, datos.deposito.id, [_fardos(cat, "1", "150")])
    admin = iniciar_sesion("admin@prueba.bo")
    r = admin.post("/api/conteos", json={"ubicacion_id": str(datos.deposito.id)})
    assert r.status_code == 201
    conteo = r.json()
    assert [linea["producto_sku"] for linea in conteo["lineas"]] == ["GUA-001"]
    r = admin.put(
        f"/api/conteos/{conteo['id']}/lineas",
        json=[{"producto_id": str(cat.guantes.id), "cantidad_contada": "290"}],
    )
    assert D(r.json()["lineas"][0]["diferencia"]) == -10
    assert admin.post(f"/api/conteos/{conteo['id']}/aprobar").status_code == 403

    dueno = iniciar_sesion("dueno@prueba.bo")
    r = dueno.post(f"/api/conteos/{conteo['id']}/aprobar")
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "APROBADO" and r.json()["ajuste_id"]
    assert _saldo(db, datos.deposito.id, cat.guantes.id).fisico == 290  # type: ignore[union-attr]
    _verificar(dueno)


# ---------------------------------------------------------------- consultas y permisos


def test_stock_y_kardex(
    iniciar_sesion: Login, db: Session, ctx: Contexto, datos: Datos, cat: Catalogo
) -> None:
    comprar(db, ctx, cat, datos.deposito.id, [_fardos(cat, "3", "150")])
    dueno = iniciar_sesion("dueno@prueba.bo")
    dueno.post(
        "/api/transferencias",
        json={
            "origen_id": str(datos.deposito.id),
            "destino_id": str(datos.sucursal.id),
            "lineas": [{"producto_id": str(cat.guantes.id), "cantidad": "20"}],
        },
    )
    fila = dueno.get("/api/inventario/stock", params={"buscar": "GUA"}).json()["items"][0]
    por_ubic = {u["ubicacion_nombre"]: u for u in fila["ubicaciones"]}
    assert por_ubic["Depósito A"]["desglose"] == "1 Caja + 280 unidad"
    assert D(fila["total_fisico"]) == 900
    assert D(fila["valor_total"]) == D("450")

    kardex = dueno.get("/api/inventario/kardex", params={"producto_id": str(cat.guantes.id)}).json()
    tipos = [m["tipo"] for m in kardex["items"]]
    assert tipos == ["TRANSFERENCIA_ENTRADA", "TRANSFERENCIA_SALIDA", "COMPRA"]
    assert kardex["items"][2]["documento"].startswith("Compra #")

    # El encargado ve stock y kardex, pero sin costos; no ve compras.
    encargado = iniciar_sesion("encargado@prueba.bo")
    fila = encargado.get("/api/inventario/stock", params={"buscar": "GUA"}).json()["items"][0]
    assert fila["valor_total"] is None
    k = encargado.get("/api/inventario/kardex", params={"producto_id": str(cat.guantes.id)}).json()
    assert k["items"][0]["costo_unitario"] is None
    assert encargado.get("/api/compras").status_code == 403


def test_acceso_restringido_a_ubicaciones_asignadas(
    cliente_anonimo: TestClient, db: Session, ctx: Contexto, datos: Datos, cat: Catalogo
) -> None:
    rol = Rol(
        empresa_id=datos.empresa.id,
        nombre="Almacenero",
        permisos=[
            p for p in datos.roles["Administrador"].permisos if p.codigo != "ubicaciones.todas"
        ],
    )
    usuario = Usuario(
        empresa_id=datos.empresa.id,
        nombre="Al",
        apellido="Macén",
        correo="almacen@prueba.bo",
        password_hash=_HASH,
        roles=[rol],
        ubicaciones=[datos.sucursal],
    )
    db.add_all([rol, usuario])
    db.commit()
    comprar(db, ctx, cat, datos.deposito.id, [_fardos(cat, "1", "150")])

    r = cliente_anonimo.post(
        "/api/auth/login", json={"correo": "almacen@prueba.bo", "password": PASSWORD}
    )
    cliente_anonimo.headers["X-CSRF-Token"] = r.cookies["csrf_token"]
    r = cliente_anonimo.post(
        "/api/ajustes", json=_ajuste(cat, datos.deposito.id, "DISMINUCION", "1")
    )
    assert r.status_code == 403
    assert "Depósito A" in r.json()["detalle"]


def test_libro_de_movimientos_inmutable(
    db: Session, ctx: Contexto, datos: Datos, cat: Catalogo
) -> None:
    comprar(db, ctx, cat, datos.deposito.id, [_fardos(cat, "1", "150")])
    with pytest.raises(DBAPIError, match="inmutable"), db.begin_nested():
        db.execute(text("UPDATE movimiento SET cantidad = 1"))
    with pytest.raises(DBAPIError, match="inmutable"), db.begin_nested():
        db.execute(text("DELETE FROM movimiento"))


def test_catalogo_sku_unico_y_presentaciones(
    iniciar_sesion: Login, datos: Datos, cat: Catalogo
) -> None:
    dueno = iniciar_sesion("dueno@prueba.bo")
    r = dueno.post(
        "/api/productos",
        json={"sku": "gua-001", "nombre": "Otro", "categoria_id": str(cat.categoria.id)},
    )
    assert r.status_code == 409
    r = dueno.post(
        f"/api/productos/{cat.guantes.id}/presentaciones", json={"nombre": "fardo", "factor": "10"}
    )
    assert r.status_code == 422
    r = dueno.post(
        f"/api/productos/{cat.guantes.id}/presentaciones",
        json={"nombre": "Paquete", "factor": "50"},
    )
    assert r.status_code == 201
    encargado = iniciar_sesion("encargado@prueba.bo")
    assert encargado.get("/api/productos").status_code == 200
    assert encargado.post("/api/productos", json={}).status_code in (403, 422)
