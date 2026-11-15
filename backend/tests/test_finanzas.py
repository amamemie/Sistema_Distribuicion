"""Fase 5: cuentas por cobrar, cobros por transferencia, gastos, pagos, impuestos y reportes."""

from datetime import date, timedelta
from decimal import Decimal as D

import pytest
from sqlalchemy.orm import Session

from app.core.errors import Conflicto, ReglaNegocio
from app.core.tiempo import ahora, hoy
from app.modules.alertas import reglas
from app.modules.compras import servicios as compras
from app.modules.compras.models import CondicionPago
from app.modules.compras.schemas import CompraEntrada, CompraLineaEntrada
from app.modules.finanzas import cuentas, impuestos, parametros, servicios
from app.modules.finanzas import reportes as rep
from app.modules.finanzas.cuentas import EstadoCuenta
from app.modules.finanzas.models import EstadoRegistro
from app.modules.finanzas.schemas import (
    CategoriaGastoEntrada,
    CobroDetalleEntrada,
    CobroEntrada,
    GastoEntrada,
)
from app.modules.pedidos import servicios as pedidos
from app.modules.pedidos.models import Pedido
from app.modules.pedidos.schemas import DevolucionEntrada, DevolucionLineaEntrada
from app.modules.reportes.schemas import Agrupacion, Filtros, Reporte
from tests.test_alertas import _activas
from tests.test_pedidos import JPEG, Escenario, Login, _alistar, _borrador
from tests.test_pedidos import esc as esc


def _entregado(
    db: Session, esc: Escenario, cantidad: int, precio: str, oc: str, hace_dias: int = 0
) -> Pedido:
    p = _borrador(db, esc, cantidad=D(cantidad), precio=D(precio), numero_oc=oc)
    pedidos.confirmar(db, esc.ctx, p.id)
    _alistar(db, esc, p, D(cantidad))
    p = pedidos.entregar(
        db, esc.ctx, p.id, receptor_nombre=None, observacion=None, foto=None, firma=None
    )
    if hace_dias:
        p.entregado_at = ahora() - timedelta(days=hace_dias)
        db.flush()
    return p


def _cuenta(db: Session, esc: Escenario, pedido: Pedido) -> cuentas.Cuenta:
    db.expire_all()
    return cuentas.cuentas(db, esc.ctx.empresa_id, 40, pedido_ids=[pedido.id])[0]


def _cobro(
    esc: Escenario, monto: str, *detalles: CobroDetalleEntrada, **extra: object
) -> CobroEntrada:
    return CobroEntrada(
        cadena_id=esc.cadena.id,
        fecha=hoy(),
        monto=D(monto),
        detalles=list(detalles),
        **extra,
    )


def _det(pedido: Pedido, monto: str, motivo: str | None = None) -> CobroDetalleEntrada:
    return CobroDetalleEntrada(
        pedido_id=pedido.id,
        monto=D(monto),
        cerrar_diferencia=motivo is not None,
        motivo_diferencia=motivo,
    )


@pytest.fixture
def entregas(db: Session, esc: Escenario) -> tuple[Escenario, Pedido, Pedido]:
    """Dos entregas a Hipermaxi: Bs 150 (costo 100) y Bs 80 (costo 40)."""
    return esc, _entregado(db, esc, 100, "1.5", "R-1"), _entregado(db, esc, 40, "2", "R-2")


# ---------------------------------------------------------------- cobros


def test_cobro_mensual_salda_los_pedidos(
    db: Session, entregas: tuple[Escenario, Pedido, Pedido]
) -> None:
    esc, p1, p2 = entregas
    # Un pedido solo confirmado todavía no es una cuenta por cobrar.
    pendiente = pedidos.confirmar(
        db, esc.ctx, _borrador(db, esc, numero_oc="R-3", cantidad=D(5)).id
    )
    resumen = servicios.por_cobrar(db, esc.ctx, cadena_id=None, todas=False)
    assert resumen.total_pendiente == D("230.00")
    assert resumen.total_vencido == 0
    assert [c.numero for c in resumen.cuentas] == [p1.numero, p2.numero]
    assert resumen.cadenas[0].pedidos_pendientes == 2

    with pytest.raises(ReglaNegocio, match="no coincide con el monto"):
        servicios.registrar_cobro(db, esc.ctx, _cobro(esc, "200", _det(p1, "150"), _det(p2, "80")))
    with pytest.raises(ReglaNegocio, match="solo debe"):
        servicios.registrar_cobro(db, esc.ctx, _cobro(esc, "160", _det(p1, "160")))
    with pytest.raises(ReglaNegocio, match="no está entregado"):
        servicios.registrar_cobro(db, esc.ctx, _cobro(esc, "7.5", _det(pendiente, "7.5")))
    with pytest.raises(ReglaNegocio, match="futura"):
        servicios.registrar_cobro(
            db,
            esc.ctx,
            _cobro(esc, "150", _det(p1, "150")).model_copy(
                update={"fecha": hoy() + timedelta(days=1)}
            ),
        )

    cobro = servicios.registrar_cobro(
        db,
        esc.ctx,
        _cobro(esc, "230", _det(p1, "150"), _det(p2, "80"), banco="BNB", referencia="OP-778"),
    )
    assert cobro.numero > 0 and len(cobro.detalles) == 2
    assert _cuenta(db, esc, p1).estado == EstadoCuenta.SALDADA
    assert servicios.por_cobrar(db, esc.ctx, cadena_id=None, todas=False).cuentas == []
    with pytest.raises(ReglaNegocio, match="ya está cobrado"):
        servicios.registrar_cobro(db, esc.ctx, _cobro(esc, "150", _det(p1, "150")))

    # La misma transferencia (N.º de operación) no se registra dos veces.
    servicios.anular_cobro(db, esc.ctx, cobro.id, "Se registró con la fecha equivocada")
    assert _cuenta(db, esc, p1).estado == EstadoCuenta.PENDIENTE
    servicios.registrar_cobro(db, esc.ctx, _cobro(esc, "150", _det(p1, "150"), referencia="op-778"))
    with pytest.raises(Conflicto, match="OP-778"):
        servicios.registrar_cobro(
            db, esc.ctx, _cobro(esc, "80", _det(p2, "80"), referencia="OP-778")
        )


def test_pago_con_diferencia_y_cierre_de_saldo(
    db: Session, entregas: tuple[Escenario, Pedido, Pedido]
) -> None:
    esc, p1, p2 = entregas
    # Pagaron 10 Bs menos por un error de la factura: se cierra con motivo.
    with pytest.raises(ReglaNegocio, match="por qué se pagó menos"):
        servicios.registrar_cobro(db, esc.ctx, _cobro(esc, "140", _det(p1, "140", motivo=" ")))
    servicios.registrar_cobro(
        db, esc.ctx, _cobro(esc, "140", _det(p1, "140", motivo="Error en la factura"))
    )
    c1 = _cuenta(db, esc, p1)
    assert (c1.cobrado, c1.diferencia, c1.saldo, c1.estado) == (
        D("140.00"),
        D("10.00"),
        D(0),
        EstadoCuenta.SALDADA,
    )

    # Pago parcial sin cerrar: queda saldo pendiente; luego se cierra sin transferencia.
    servicios.registrar_cobro(db, esc.ctx, _cobro(esc, "70", _det(p2, "70")))
    assert (_cuenta(db, esc, p2).saldo, _cuenta(db, esc, p2).estado) == (
        D("10.00"),
        EstadoCuenta.PARCIAL,
    )
    cierre = servicios.cerrar_saldo(db, esc.ctx, p2.id, "El supermercado no reconoce el faltante")
    assert cierre.monto == 0 and cierre.detalles[0].diferencia == D("10.00")
    assert _cuenta(db, esc, p2).estado == EstadoCuenta.SALDADA
    with pytest.raises(ReglaNegocio, match="no tiene saldo"):
        servicios.cerrar_saldo(db, esc.ctx, p2.id, "Otra vez")


def test_descuento_de_la_nota_y_devolucion_posterior(db: Session, esc: Escenario) -> None:
    p = _entregado(db, esc, 100, "1.5", "R-9")
    p.total_oc = D("135.00")  # la nota trae Bs 15 de descuento sobre Bs 150
    db.flush()
    assert _cuenta(db, esc, p).monto == D("135.00")
    servicios.registrar_cobro(db, esc.ctx, _cobro(esc, "135", _det(p, "135")))

    # Devolución después de pagar: la cadena queda con saldo a favor.
    pedidos.devolver(
        db,
        esc.ctx,
        p.id,
        DevolucionEntrada(
            motivo="Producto dañado",
            lineas=[DevolucionLineaEntrada(linea_id=p.lineas[0].id, cantidad=D(10))],
        ),
    )
    cuenta = _cuenta(db, esc, p)
    assert (cuenta.monto, cuenta.saldo, cuenta.estado) == (
        D("121.50"),
        D("-13.50"),
        EstadoCuenta.A_FAVOR,
    )
    resumen = servicios.por_cobrar(db, esc.ctx, cadena_id=esc.cadena.id, todas=False)
    assert resumen.cadenas[0].a_favor == D("13.50") and resumen.total_pendiente == 0


def test_alerta_de_cobro_vencido(db: Session, esc: Escenario) -> None:
    viejo = _entregado(db, esc, 100, "1.5", "R-1", hace_dias=50)
    _entregado(db, esc, 40, "2", "R-2", hace_dias=5)
    assert servicios.por_cobrar(db, esc.ctx, cadena_id=None, todas=False).total_vencido == D(
        "150.00"
    )
    reglas.evaluar(db, esc.ctx.empresa_id)
    [alerta] = _activas(db, esc, "cobro_vencido")
    assert "Bs 150,00 vencidos" in alerta.titulo and alerta.permiso == "finanzas.ver"

    servicios.registrar_cobro(db, esc.ctx, _cobro(esc, "150", _det(viejo, "150")))
    reglas.evaluar(db, esc.ctx.empresa_id)
    assert _activas(db, esc, "cobro_vencido") == []


# ---------------------------------------------------------------- gastos


def test_gastos_y_categorias(db: Session, esc: Escenario) -> None:
    servicios.asegurar_categorias(db, esc.ctx.empresa_id)
    categorias = {c.nombre: c for c in servicios.listar_categorias(db, esc.ctx)}
    assert set(categorias) == {"Gasolina", "Taxis", "Sueldos", "Luz", "Agua", "Alquiler"}
    assert categorias["Gasolina"].factura_habitual and not categorias["Sueldos"].factura_habitual

    sueldo = servicios.registrar_gasto(
        db,
        esc.ctx,
        GastoEntrada(
            fecha=hoy(),
            categoria_id=categorias["Sueldos"].id,
            ubicacion_id=esc.datos.sucursal.id,
            beneficiario="  Juan Mamani ",
            monto=D("2500"),
        ),
    )
    assert sueldo.beneficiario == "Juan Mamani" and not sueldo.con_factura
    luz = servicios.registrar_gasto(
        db,
        esc.ctx,
        GastoEntrada(
            fecha=hoy(),
            categoria_id=categorias["Luz"].id,
            monto=D("180.50"),
            con_factura=True,
            numero_factura="F-1",
        ),
    )
    servicios.registrar_gasto(
        db,
        esc.ctx,
        GastoEntrada(fecha=hoy(), categoria_id=categorias["Taxis"].id, monto=D("25")),
    )
    servicios.anular_gasto(db, esc.ctx, luz.id, "Se cargó dos veces")
    pagina = servicios.listar_gastos(
        db,
        esc.ctx,
        desde=None,
        hasta=None,
        categoria_id=None,
        ubicacion_id=None,
        buscar=None,
        pagina=1,
        tamano=30,
    )
    assert pagina.total == 3  # el anulado se ve, pero no suma
    assert pagina.suma == D("2525.00")
    assert [x.categoria.nombre for x in pagina.por_categoria] == ["Sueldos", "Taxis"]
    buscado = servicios.listar_gastos(
        db,
        esc.ctx,
        desde=None,
        hasta=None,
        categoria_id=None,
        ubicacion_id=None,
        buscar="mamani",
        pagina=1,
        tamano=30,
    )
    assert [x.numero for x in buscado.items] == [sueldo.numero]

    with pytest.raises(Conflicto):
        servicios.crear_categoria(db, esc.ctx, CategoriaGastoEntrada(nombre="gasolina"))
    servicios.editar_categoria(
        db, esc.ctx, categorias["Agua"].id, CategoriaGastoEntrada(nombre="Agua", activo=False)
    )
    with pytest.raises(ReglaNegocio, match="inactiva"):
        servicios.registrar_gasto(
            db, esc.ctx, GastoEntrada(fecha=hoy(), categoria_id=categorias["Agua"].id, monto=D(1))
        )
    with pytest.raises(ReglaNegocio, match="futura"):
        servicios.registrar_gasto(
            db,
            esc.ctx,
            GastoEntrada(
                fecha=hoy() + timedelta(days=1), categoria_id=categorias["Taxis"].id, monto=D(1)
            ),
        )


# ---------------------------------------------------------------- compras y pagos


def _compra(esc: Escenario, **extra: object) -> CompraEntrada:
    return CompraEntrada(
        proveedor_id=esc.cat.proveedor.id,
        ubicacion_id=esc.datos.sucursal.id,
        fecha=hoy() - timedelta(days=2),
        lineas=[
            CompraLineaEntrada(
                producto_id=esc.cat.guantes.id, cantidad=D(10), precio_presentacion=D(1)
            )
        ],
        **extra,
    )


def test_compra_al_contado_y_a_credito(db: Session, esc: Escenario) -> None:
    contado = compras.registrar(db, esc.ctx, _compra(esc))
    assert contado.condicion_pago == CondicionPago.CONTADO
    assert contado.fecha_pago == contado.fecha and contado.con_factura

    with pytest.raises(ReglaNegocio, match="hasta cuándo"):
        compras.registrar(db, esc.ctx, _compra(esc, condicion_pago=CondicionPago.CREDITO))
    credito = compras.registrar(
        db,
        esc.ctx,
        _compra(
            esc,
            condicion_pago=CondicionPago.CREDITO,
            fecha_vencimiento=hoy() + timedelta(days=2),
            con_factura=False,
        ),
    )
    assert credito.fecha_pago is None
    [deuda] = servicios.por_pagar(db, esc.ctx)
    assert (deuda.numero, deuda.dias_para_vencer) == (credito.numero, 2)
    reglas.evaluar(db, esc.ctx.empresa_id)
    [alerta] = _activas(db, esc, "pago_proveedor")
    assert "vence en 2 días" in alerta.mensaje

    with pytest.raises(ReglaNegocio, match="anterior a la de la compra"):
        servicios.pagar_compra(db, esc.ctx, credito.id, credito.fecha - timedelta(days=1))
    servicios.pagar_compra(db, esc.ctx, credito.id, hoy())
    assert servicios.por_pagar(db, esc.ctx) == []
    with pytest.raises(ReglaNegocio, match="ya está pagada"):
        servicios.pagar_compra(db, esc.ctx, credito.id, hoy())
    reglas.evaluar(db, esc.ctx.empresa_id)
    assert _activas(db, esc, "pago_proveedor") == []


# ---------------------------------------------------------------- impuestos


def test_impuestos_con_credito_fiscal_que_pasa_al_mes_siguiente(
    db: Session, esc: Escenario
) -> None:
    # El escenario compró Bs 600 con factura el 01/11/2026: crédito fiscal Bs 78.
    p = _entregado(db, esc, 100, "1.5", "R-1")
    p.entregado_at = ahora().replace(year=2026, month=11, day=10)
    servicios.asegurar_categorias(db, esc.ctx.empresa_id)
    gasolina = next(c for c in servicios.listar_categorias(db, esc.ctx) if c.nombre == "Gasolina")
    g = servicios.registrar_gasto(
        db,
        esc.ctx,
        GastoEntrada(
            fecha=date(2026, 11, 3), categoria_id=gasolina.id, monto=D(100), con_factura=True
        ),
    )
    assert g.con_factura
    pf = parametros.leer(db, esc.ctx.empresa_id)
    [noviembre, diciembre] = impuestos.mensual(
        db, esc.ctx.empresa_id, pf, date(2026, 11, 1), date(2026, 12, 31)
    )
    assert noviembre.ventas == D("150.00")
    assert (noviembre.iva_debito, noviembre.iva_credito) == (D("19.50"), D("91.00"))
    assert (noviembre.iva_pagar, noviembre.saldo_siguiente, noviembre.it) == (
        D(0),
        D("71.50"),
        D("4.50"),
    )
    assert noviembre.total_pagar == D("4.50")
    assert diciembre.saldo_anterior == D("71.50")
    # El arrastre se calcula aunque el rango empiece después.
    [solo_diciembre] = impuestos.mensual(
        db, esc.ctx.empresa_id, pf, date(2026, 12, 1), date(2026, 12, 31)
    )
    assert solo_diciembre.saldo_anterior == D("71.50")


# ---------------------------------------------------------------- reportes y API


def _kpis(r: Reporte) -> dict[str, object]:
    return {k.clave: k.valor for k in r.kpis}


def test_reportes_financieros(db: Session, entregas: tuple[Escenario, Pedido, Pedido]) -> None:
    esc, p1, _p2 = entregas
    servicios.asegurar_categorias(db, esc.ctx.empresa_id)
    sueldos = next(c for c in servicios.listar_categorias(db, esc.ctx) if c.nombre == "Sueldos")
    servicios.registrar_gasto(
        db, esc.ctx, GastoEntrada(fecha=hoy(), categoria_id=sueldos.id, monto=D(50))
    )
    servicios.registrar_cobro(db, esc.ctx, _cobro(esc, "150", _det(p1, "150")))
    f = Filtros(desde=hoy().replace(day=1), hasta=hoy(), agrupacion=Agrupacion.MES)

    r = rep.resultados(db, esc.ctx, f)
    k = _kpis(r)
    # Ventas 230, costo 140, gastos 50. IVA: 13 % de 230 = 29,90 menos 13 % de la compra del
    # escenario (Bs 600 el 01/11) = 78 → -48,10. IT: 3 % de 230 = 6,90.
    assert (k["ventas"], k["bruta"], k["gastos"]) == (D("230.00"), D("90.00"), D("50.00"))
    assert k["impuestos"] == D("-41.20")
    assert k["neta"] == D("81.20")
    conceptos = [x["concepto"] for x in r.tablas[0].filas]
    assert "(-) Sueldos" in conceptos and conceptos[-1] == "= Ganancia neta"

    flujo = _kpis(rep.flujo_caja(db, esc.ctx, f))
    assert (flujo["entradas"], flujo["por_cobrar"]) == (D("150.00"), D("80.00"))
    assert flujo["salidas"] == D("650.00")  # compra al contado del 01/11 + sueldos

    cobranza = rep.cobranza(db, esc.ctx, f)
    assert _kpis(cobranza)["pendiente"] == D("80.00")
    assert _kpis(cobranza)["dias_cobro"] == 0
    assert cobranza.tablas[0].filas[0]["por_vencer"] == D("80.00")

    impuesto = rep.impuestos_reporte(db, esc.ctx, f)
    assert _kpis(impuesto)["it"] == D("6.90")


def test_api_finanzas_y_permisos(
    db: Session, entregas: tuple[Escenario, Pedido, Pedido], iniciar_sesion: Login
) -> None:
    esc, p1, p2 = entregas
    admin = iniciar_sesion("admin@prueba.bo")
    assert admin.get("/api/finanzas/por-cobrar").status_code == 403
    desde = hoy().replace(day=1).isoformat()
    assert admin.get(f"/api/reportes/resultados?desde={desde}&hasta={hoy()}").status_code == 403
    assert admin.get(f"/api/reportes/productos?desde={desde}&hasta={hoy()}").status_code == 200

    dueno = iniciar_sesion("dueno@prueba.bo")
    r = dueno.post(
        "/api/finanzas/cobros",
        json={
            "cadena_id": str(esc.cadena.id),
            "fecha": hoy().isoformat(),
            "monto": "225",
            "referencia": "OP-1",
            "detalles": [
                {"pedido_id": str(p1.id), "monto": "150"},
                {
                    "pedido_id": str(p2.id),
                    "monto": "75",
                    "cerrar_diferencia": True,
                    "motivo_diferencia": "Precio mal facturado",
                },
            ],
        },
    )
    assert r.status_code == 201, r.text
    cobro = r.json()
    assert cobro["diferencias"] == "5.00" and cobro["detalles"][1]["pedido_numero"] == p2.numero

    r = dueno.post(
        f"/api/finanzas/cobros/{cobro['id']}/comprobante",
        files={"archivo": ("transferencia.jpg", JPEG, "image/jpeg")},
    )
    assert r.status_code == 200, r.text
    comprobante = r.json()["comprobante_id"]
    assert dueno.get(f"/api/finanzas/comprobantes/{comprobante}").content == JPEG

    por_cobrar = dueno.get("/api/finanzas/por-cobrar").json()
    assert D(por_cobrar["total_pendiente"]) == 0
    todas = dueno.get("/api/finanzas/por-cobrar?todas=true").json()
    assert {c["estado"] for c in todas["cuentas"]} == {"SALDADA"}

    assert dueno.get(f"/api/finanzas/impuestos?desde={desde}&hasta={hoy()}").status_code == 200
    r = dueno.put(
        "/api/finanzas/parametros", json={"dias_credito": 30, "iva_pct": "13", "it_pct": "3"}
    )
    assert r.status_code == 200 and r.json()["dias_credito"] == 30
    assert dueno.get("/api/finanzas/parametros").json()["dias_credito"] == 30
    r = dueno.get(f"/api/reportes/resultados/exportar?desde={desde}&hasta={hoy()}&formato=xlsx")
    assert r.status_code == 200 and r.content[:2] == b"PK"
    r = dueno.get(f"/api/reportes/cobranza/exportar?desde={desde}&hasta={hoy()}&formato=pdf")
    assert r.status_code == 200 and r.content[:4] == b"%PDF"

    r = dueno.post(
        f"/api/finanzas/cobros/{cobro['id']}/anular", json={"motivo": "Prueba de anulación"}
    )
    assert r.json()["estado"] == EstadoRegistro.ANULADO
