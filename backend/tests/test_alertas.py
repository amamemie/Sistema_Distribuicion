"""Fase 4: pronóstico, reposición en dos niveles, alertas (estado y evento), permisos y API."""

from datetime import timedelta
from decimal import Decimal as D

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.tiempo import ahora, hoy
from app.modules.alertas import dominio, pronostico, reglas, reposicion, servicios
from app.modules.alertas.models import Alerta, Confianza, EstadoAlerta, Severidad
from app.modules.alertas.parametros import Parametros
from app.modules.compras.schemas import CompraLineaEntrada
from app.modules.identidad.contexto import Contexto
from app.modules.inventario import servicios as inventario
from app.modules.inventario.schemas import TransferenciaEntrada, TransferenciaLineaEntrada
from app.modules.pedidos import servicios as pedidos
from tests.fabrica import comprar, presentacion
from tests.test_pedidos import Escenario, Login, _alistar, _borrador
from tests.test_pedidos import esc as esc

# ---------------------------------------------------------------- lógica pura


def test_pronostico_elige_el_metodo_y_marca_la_confianza() -> None:
    assert dominio.pronosticar([]).metodo == "sin ventas"
    pocos = dominio.pronosticar([10, 20])
    assert (pocos.metodo, pocos.demanda_semanal, pocos.confianza) == (
        "promedio",
        15,
        Confianza.BAJA,
    )
    assert pocos.desviacion_semanal >= 7.5  # con pocos datos se supone variación alta

    estable = dominio.pronosticar([100.0] * 12)
    assert estable.demanda_semanal == pytest.approx(100)
    assert estable.error_medio == 0 and estable.confianza == Confianza.ALTA

    # Demanda que sube: el suavizado que más pesa lo reciente acierta mejor.
    creciente = dominio.pronosticar([10, 20, 30, 40, 50, 60, 70, 80])
    assert "alfa=0.8" in creciente.metodo
    assert creciente.demanda_semanal > 70 and creciente.confianza == Confianza.MEDIA


def test_plan_de_reposicion_y_presentaciones() -> None:
    plan = dominio.planificar(
        demanda_semanal=D(70),
        desviacion_semanal=D(0),
        disponible=D(25),
        dias_reposicion=3,
        dias_cobertura=7,
    )
    assert (plan.demanda_diaria, plan.punto_reorden, plan.objetivo) == (D(10), D(30), D(70))
    assert plan.cobertura_dias == D("2.5")
    con_limites = dominio.planificar(
        demanda_semanal=D(70),
        desviacion_semanal=D(14),
        disponible=D(25),
        dias_reposicion=3,
        dias_cobertura=7,
        minimo=D(40),
        maximo=D(200),
    )
    assert (con_limites.punto_reorden, con_limites.objetivo) == (D(40), D(200))
    assert con_limites.stock_seguridad > 0

    cajas = [("Caja", D(12)), ("Fardo", D(300))]
    assert dominio.redondear_a_presentacion(D(50), cajas) == (D(60), "Caja", D(5))
    assert dominio.redondear_a_presentacion(D(301), cajas) == (D(600), "Fardo", D(2))
    assert dominio.redondear_a_presentacion(D("7.2"), cajas) == (D(8), "unidad", D(8))


def test_valores_atipicos() -> None:
    historia = [10.0, 12, 11, 9, 10, 11]
    assert dominio.atipico(60, historia) and not dominio.atipico(12, historia)
    assert not dominio.atipico(60, historia[:3])  # poca historia: no se juzga
    assert dominio.atipico(20, [10.0] * 5) and not dominio.atipico(12, [10.0] * 5)


# ---------------------------------------------------------------- integración


def _vender(
    db: Session, esc: Escenario, cantidad: int, hace_dias: int, precio: str = "1.5"
) -> None:
    p = _borrador(db, esc, cantidad=D(cantidad), precio=D(precio), numero_oc=None, documento=False)
    pedidos.confirmar(db, esc.ctx, p.id)
    p = _alistar(db, esc, p, D(cantidad))
    p.alistado_at = ahora() - timedelta(days=hace_dias)
    db.flush()


@pytest.fixture
def cadena(db: Session, esc: Escenario) -> Escenario:
    """Depósito con 300 guantes que abastece a la sucursal (600 + 10 transferidos)."""
    comprar(
        db,
        esc.ctx,
        esc.cat,
        esc.datos.deposito.id,
        [
            CompraLineaEntrada(
                producto_id=esc.cat.guantes.id,
                presentacion_id=presentacion(esc.cat.guantes, "Fardo"),
                cantidad=D(1),
                precio_presentacion=D(300),
            )
        ],
    )
    inventario.transferir(
        db,
        esc.ctx,
        TransferenciaEntrada(
            origen_id=esc.datos.deposito.id,
            destino_id=esc.datos.sucursal.id,
            lineas=[TransferenciaLineaEntrada(producto_id=esc.cat.guantes.id, cantidad=D(10))],
        ),
    )
    return esc


def _activas(db: Session, esc: Escenario, tipo: str) -> list[Alerta]:
    return list(
        db.scalars(
            select(Alerta).where(
                Alerta.empresa_id == esc.ctx.empresa_id,
                Alerta.tipo == tipo,
                Alerta.estado == EstadoAlerta.ACTIVA,
            )
        )
    )


def test_pronostico_desde_las_ventas(db: Session, cadena: Escenario) -> None:
    for semana in range(5):
        _vender(db, cadena, 100, hace_dias=7 * semana + 1)
    series = pronostico.series_semanales(db, cadena.ctx.empresa_id)
    serie = series[(cadena.datos.sucursal.id, cadena.cat.guantes.id)]
    assert sum(serie) == 500 and serie[-5:] == [100.0] * 5
    assert pronostico.recalcular(db, cadena.ctx.empresa_id) >= 1
    [f] = [
        x
        for x in reposicion.planificar(db, cadena.ctx.empresa_id, Parametros()).sucursales
        if x.producto.id == cadena.cat.guantes.id
    ]
    assert (
        f.demanda_semanal == D(100)
        and f.origen is not None
        and f.origen.id == cadena.datos.deposito.id
    )


def test_stock_bajo_sugiere_transferir_y_luego_quiebre(db: Session, cadena: Escenario) -> None:
    for semana in range(5):
        _vender(db, cadena, 120, hace_dias=7 * semana + 1)  # quedan 10 en la sucursal
    pronostico.recalcular(db, cadena.ctx.empresa_id)
    reglas.evaluar(db, cadena.ctx.empresa_id)
    [bajo] = _activas(db, cadena, "stock_bajo")
    assert (
        bajo.ubicacion_id == cadena.datos.sucursal.id and "Reponer desde Depósito A" in bajo.mensaje
    )

    # Objetivo: 7 días de venta (120) menos los 10 que hay; 110 no llega a un fardo (300).
    [sug] = servicios.transferencias(db, cadena.ctx)
    assert sug.origen.id == cadena.datos.deposito.id
    assert (sug.cantidad, sug.presentacion, sug.insuficiente) == (D(110), "unidad", False)

    # El depósito (290) vende lo de su sucursal (120/semana): comprar en 13 días, 2 fardos.
    [compra] = servicios.compras(db, cadena.ctx)
    assert compra.proveedor is not None and compra.proveedor.id == cadena.cat.proveedor.id
    assert compra.fecha == hoy() + timedelta(days=13) and compra.dias_entrega == 3
    assert (compra.cantidad, compra.presentacion, compra.cantidad_presentacion) == (
        D(600),
        "Fardo",
        D(2),
    )
    assert compra.costo_estimado == D("600.00")

    _vender(db, cadena, 10, hace_dias=0)  # se agota la sucursal
    r = reglas.evaluar(db, cadena.ctx.empresa_id)
    assert r["resueltas"] >= 1
    [quiebre] = _activas(db, cadena, "quiebre")
    assert quiebre.severidad == Severidad.CRITICA
    assert _activas(db, cadena, "stock_bajo") == []  # la anterior se cerró sola

    # Al reponer, el quiebre se resuelve solo.
    inventario.transferir(
        db,
        cadena.ctx,
        TransferenciaEntrada(
            origen_id=cadena.datos.deposito.id,
            destino_id=cadena.datos.sucursal.id,
            lineas=[TransferenciaLineaEntrada(producto_id=cadena.cat.guantes.id, cantidad=D(200))],
        ),
    )
    reglas.evaluar(db, cadena.ctx.empresa_id)
    assert _activas(db, cadena, "quiebre") == []


def test_margen_negativo_se_atiende_y_no_se_repite(db: Session, esc: Escenario) -> None:
    _vender(db, esc, 10, hace_dias=0, precio="0.9")  # costo Bs 1: pérdida
    reglas.evaluar(db, esc.ctx.empresa_id)
    [alerta] = _activas(db, esc, "margen_negativo")
    assert alerta.severidad == Severidad.CRITICA and alerta.permiso == "costos.ver"

    admin = Contexto(usuario=esc.datos.admin, ip=None, user_agent=None)
    assert all(
        a.tipo != "margen_negativo"
        for a in servicios.listar(
            db,
            admin,
            estado=None,
            severidad=None,
            tipo=None,
            solo_no_leidas=False,
            pagina=1,
            tamano=50,
        ).items
    )  # el administrador no ve costos

    assert servicios.resumen(db, esc.ctx).criticas >= 1
    servicios.atender(db, esc.ctx, alerta.id)
    reglas.evaluar(db, esc.ctx.empresa_id)
    assert _activas(db, esc, "margen_negativo") == []  # atendida: no se vuelve a crear


def test_lote_por_vencer_y_lectura(db: Session, esc: Escenario) -> None:
    comprar(
        db,
        esc.ctx,
        esc.cat,
        esc.datos.sucursal.id,
        [
            CompraLineaEntrada(
                producto_id=esc.cat.leche.id,
                cantidad=D(12),
                precio_presentacion=D(5),
                lote_codigo="L-1",
                lote_vencimiento=hoy() + timedelta(days=5),
            )
        ],
    )
    reglas.evaluar(db, esc.ctx.empresa_id)
    [lote] = _activas(db, esc, "lote_por_vencer")
    assert "en 5 días" in lote.mensaje and lote.severidad == Severidad.AVISO

    antes = servicios.resumen(db, esc.ctx).no_leidas
    assert antes >= 1
    servicios.marcar_leidas(db, esc.ctx, [lote.id])
    assert servicios.resumen(db, esc.ctx).no_leidas == antes - 1
    with pytest.raises(Exception, match="se cierra sola"):
        servicios.atender(db, esc.ctx, lote.id)

    # El encargado sin esa sucursal asignada no la ve.
    encargado = Contexto(usuario=esc.datos.encargado, ip=None, user_agent=None)
    assert servicios.resumen(db, encargado).no_leidas == 0


def test_parametros_y_api(db: Session, esc: Escenario, iniciar_sesion: Login) -> None:
    db.commit()
    dueno = iniciar_sesion("dueno@prueba.bo")
    r = dueno.get("/api/alertas/parametros")
    assert r.status_code == 200 and r.json()["cobertura_sucursal_dias"] == 7
    assert r.json()["dias_entrega_proveedor"] == 3 and r.json()["margen_minimo"] == 10
    r = dueno.put("/api/alertas/parametros", json={**r.json(), "margen_minimo": 15})
    assert r.status_code == 200 and r.json()["margen_minimo"] == 15
    assert dueno.post("/api/alertas/evaluar").status_code == 200
    assert dueno.get("/api/alertas").status_code == 200
    assert dueno.get("/api/alertas/resumen").json().keys() == {"no_leidas", "criticas"}
    assert dueno.get("/api/reposicion/transferencias").status_code == 200
    assert dueno.get("/api/reposicion/compras").status_code == 200
    assert dueno.get(f"/api/reposicion/pronostico/{esc.cat.guantes.id}").status_code == 200

    admin = iniciar_sesion("admin@prueba.bo")
    assert admin.put("/api/alertas/parametros", json=r.json()).status_code == 403
    encargado = iniciar_sesion("encargado@prueba.bo")
    assert encargado.get("/api/reposicion/compras").status_code == 403
    assert encargado.get("/api/alertas/resumen").status_code == 200
