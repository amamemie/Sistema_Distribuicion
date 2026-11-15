"""Reportes: cifras de ganancias, productos, clientes, inventario, ajustes, compras y usuarios;
permisos (costos solo con reportes.rentabilidad) y exportación a Excel y PDF."""

import io
from datetime import date, timedelta
from decimal import Decimal as D

import pytest
from openpyxl import load_workbook
from sqlalchemy.orm import Session

from app.core.errors import ReglaNegocio, SinPermiso
from app.core.tiempo import hoy
from app.modules.identidad.contexto import Contexto
from app.modules.inventario import servicios as inventario
from app.modules.inventario.schemas import TransferenciaEntrada, TransferenciaLineaEntrada
from app.modules.pedidos import servicios as pedidos
from app.modules.pedidos.models import Pedido
from app.modules.reportes import consultas, exportar
from app.modules.reportes.schemas import Agrupacion, Filtros, Reporte
from tests.test_pedidos import Escenario, Login, _alistar, _borrador
from tests.test_pedidos import esc as esc

HOY = hoy()
SEMANA = Filtros(desde=HOY - timedelta(days=6), hasta=HOY)


def _vendido(
    db: Session, esc: Escenario, cantidad: int, precio: str, numero_oc: str, fecha: date = HOY
) -> Pedido:
    p = _borrador(db, esc, cantidad=D(cantidad), precio=D(precio), numero_oc=numero_oc)
    pedidos.confirmar(db, esc.ctx, p.id)
    p = _alistar(db, esc, p, D(cantidad))
    p.fecha_oc = fecha
    db.flush()
    return p


@pytest.fixture
def ventas(db: Session, esc: Escenario) -> Escenario:
    """Guantes a Bs 1 de costo: dos ventas esta semana y una la semana anterior."""
    _vendido(db, esc, 100, "1.5", "R-1")  # ingreso 150, ganancia 50 (33,33 %)
    _vendido(db, esc, 40, "2", "R-2")  # ingreso 80, ganancia 40 (50 %)
    _vendido(db, esc, 50, "1.2", "R-3", HOY - timedelta(days=10))  # período anterior
    pedidos.confirmar(db, esc.ctx, _borrador(db, esc, numero_oc="R-4", cantidad=D(5)).id)
    _borrador(db, esc, numero_oc="R-5")  # ni el confirmado ni el borrador son ventas
    return esc


def _kpis(r: Reporte) -> dict[str, object]:
    return {k.clave: k.valor for k in r.kpis}


def _tabla(r: Reporte, clave: str) -> list[dict[str, object]]:
    return next(t for t in r.tablas if t.clave == clave).filas


def test_ganancias_con_periodo_anterior(db: Session, ventas: Escenario) -> None:
    r = consultas.ganancias(db, ventas.ctx, SEMANA)
    assert _kpis(r) == {
        "ingreso": D("230.00"),
        "costo": D("140.00"),
        "ganancia": D("90.00"),
        "margen": D("39.13"),
        "pedidos": 2,
    }
    ingreso = next(k for k in r.kpis if k.clave == "ingreso")
    assert (ingreso.anterior, ingreso.variacion) == (D("60.00"), D("283.3"))
    puntos = r.series[0].puntos
    assert len(puntos) == 7 and puntos[-1]["ingreso"] == D("230.00")
    assert [x["numero_oc"] for x in _tabla(r, "mas_caros")] == ["R-1", "R-2"]
    assert [x["numero_oc"] for x in _tabla(r, "menor_margen")] == ["R-1", "R-2"]

    por_mes = consultas.ganancias(
        db, ventas.ctx, SEMANA.model_copy(update={"agrupacion": Agrupacion.MES})
    )
    assert sum(p["ingreso"] for p in por_mes.series[0].puntos) == D("230.00")


def test_productos_y_clientes(db: Session, ventas: Escenario) -> None:
    r = consultas.productos(db, ventas.ctx, SEMANA)
    [fila] = _tabla(r, "productos")
    assert (fila["unidades"], fila["ingreso"], fila["ganancia"]) == (
        D(140),
        D("230.00"),
        D("90.00"),
    )

    c = consultas.clientes(db, ventas.ctx, SEMANA)
    [cadena] = _tabla(c, "cadenas")
    assert (cadena["cadena"], cadena["pedidos"], cadena["ingreso"]) == ("Hipermaxi", 2, D("230.00"))
    assert _tabla(c, "sucursales")[0]["sucursal"] == "Obrajes"

    with pytest.raises(ReglaNegocio, match="Cadena: no existe"):  # id de otra entidad
        consultas.productos(
            db, ventas.ctx, SEMANA.model_copy(update={"cadena_id": ventas.sucursal_cliente.id})
        )


def test_inventario_valor_rotacion_y_sin_movimiento(db: Session, ventas: Escenario) -> None:
    # 10 guantes al depósito: allí no salen nunca (stock inmovilizado).
    inventario.transferir(
        db,
        ventas.ctx,
        TransferenciaEntrada(
            origen_id=ventas.datos.sucursal.id,
            destino_id=ventas.datos.deposito.id,
            lineas=[TransferenciaLineaEntrada(producto_id=ventas.cat.guantes.id, cantidad=D(10))],
        ),
    )
    r = consultas.inventario(db, ventas.ctx, SEMANA)
    # 600 comprados - 190 vendidos (incluida la venta anterior) = 410 a Bs 1.
    assert _kpis(r)["valor"] == D("410.00")
    valor = {x["ubicacion"]: x["valor"] for x in _tabla(r, "valor_ubicacion")}
    assert valor == {"Depósito A": D("10.00"), "Sucursal A": D("400.00")}
    [rot] = [x for x in _tabla(r, "rotacion") if x["sku"] == "GUA-001"]
    assert (rot["stock"], rot["vendidas"], rot["rotacion"]) == (D(410), D(140), D("0.34"))
    # Lo recién ingresado no cuenta como inmovilizado (T-18).
    assert _tabla(r, "sin_movimiento") == []


def test_sin_movimiento_cuenta_desde_el_ingreso(
    db: Session, ventas: Escenario, monkeypatch: pytest.MonkeyPatch
) -> None:
    inventario.transferir(
        db,
        ventas.ctx,
        TransferenciaEntrada(
            origen_id=ventas.datos.sucursal.id,
            destino_id=ventas.datos.deposito.id,
            lineas=[TransferenciaLineaEntrada(producto_id=ventas.cat.guantes.id, cantidad=D(10))],
        ),
    )
    monkeypatch.setattr(consultas, "hoy", lambda: HOY + timedelta(days=40))
    r = consultas.inventario(db, ventas.ctx, SEMANA)
    quietos = {x["ubicacion"]: x for x in _tabla(r, "sin_movimiento")}
    assert quietos["Depósito A"]["stock"] == D(10)
    assert quietos["Depósito A"]["ultima_salida"] is None and quietos["Depósito A"]["dias"] == 40


def test_mermas_y_ajustes(db: Session, esc: Escenario) -> None:
    p = _borrador(db, esc, cantidad=D(20), numero_oc="M-1")
    pedidos.confirmar(db, esc.ctx, p.id)
    _alistar(db, esc, p, D(17), merma=D(3))  # rotura al alistar: 3 guantes a Bs 1
    r = consultas.ajustes(db, esc.ctx, SEMANA)
    assert _kpis(r)["perdidas"] == D("3.00")
    [motivo] = _tabla(r, "motivos")
    assert (motivo["motivo"], motivo["salidas"], motivo["valor"]) == ("Rotura", D(3), D("-3.00"))


def test_precios_de_compra(db: Session, esc: Escenario) -> None:
    f = Filtros(desde=date(2026, 10, 1), hasta=max(HOY, date(2026, 11, 30)))
    r = consultas.precios_compra(
        db, esc.ctx, f.model_copy(update={"producto_id": esc.cat.guantes.id})
    )
    [resumen] = _tabla(r, "resumen")
    assert (resumen["compras"], resumen["ultimo"]) == (1, D("1.0000"))
    assert r.series and r.series[0].claves[0].titulo == esc.cat.proveedor.nombre


def test_usuarios(db: Session, ventas: Escenario) -> None:
    r = consultas.usuarios(db, ventas.ctx, SEMANA)
    [fila] = _tabla(r, "usuarios")
    assert (fila["registrados"], fila["confirmados"], fila["alistados"]) == (5, 4, 3)


def test_sin_rentabilidad_no_hay_costos(db: Session, ventas: Escenario) -> None:
    admin = Contexto(usuario=ventas.datos.admin, ip=None, user_agent=None)
    r = consultas.productos(db, admin, SEMANA)
    assert not r.con_rentabilidad
    columnas = {c.clave for t in r.tablas for c in t.columnas}
    assert {"costo", "ganancia", "margen"}.isdisjoint(columnas)
    assert all("ganancia" not in fila for fila in _tabla(r, "productos"))
    assert "valor" not in _kpis(consultas.inventario(db, admin, SEMANA))
    with pytest.raises(SinPermiso):
        consultas.ganancias(db, admin, SEMANA)
    with pytest.raises(SinPermiso):
        consultas.precios_compra(db, admin, SEMANA)


def test_formato_de_numeros() -> None:
    assert exportar.formatear(D("1234567.8"), "dinero") == "Bs 1.234.567,80"
    assert exportar.formatear(D("39.13"), "porcentaje") == "39,1 %"
    assert exportar.formatear(D("140.000"), "cantidad") == "140"
    assert exportar.formatear(D("2.5"), "cantidad") == "2,5"
    assert exportar.formatear(None, "dinero") == "—"


def test_api_y_exportacion(db: Session, ventas: Escenario, iniciar_sesion: Login) -> None:
    db.commit()
    params = {"desde": str(SEMANA.desde), "hasta": str(SEMANA.hasta)}
    dueno = iniciar_sesion("dueno@prueba.bo")
    r = dueno.get("/api/reportes/ganancias", params=params)
    assert r.status_code == 200, r.text
    assert r.json()["kpis"][0]["valor"] == "230.00"

    r = dueno.get("/api/reportes/ganancias/exportar", params=params | {"formato": "xlsx"})
    assert r.status_code == 200
    assert "reporte-ganancias-" in r.headers["content-disposition"]
    libro = load_workbook(io.BytesIO(r.content))
    assert libro.sheetnames[0] == "Resumen" and "Pedidos más caros" in libro.sheetnames

    for clave in consultas.REPORTES:
        r = dueno.get(f"/api/reportes/{clave}/exportar", params=params | {"formato": "pdf"})
        assert r.status_code == 200, (clave, r.text)
        assert r.content.startswith(b"%PDF")

    assert dueno.get("/api/reportes/no-existe", params=params).status_code == 404
    malo = params | {"desde": str(HOY), "hasta": str(HOY - timedelta(days=1))}
    assert dueno.get("/api/reportes/productos", params=malo).status_code == 422

    admin = iniciar_sesion("admin@prueba.bo")
    assert admin.get("/api/reportes/productos", params=params).status_code == 200
    assert admin.get("/api/reportes/ganancias", params=params).status_code == 403
    encargado = iniciar_sesion("encargado@prueba.bo")
    assert encargado.get("/api/reportes/productos", params=params).status_code == 403
