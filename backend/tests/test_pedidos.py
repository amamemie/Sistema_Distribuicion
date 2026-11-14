"""Reglas de pedidos: reserva al confirmar, descuento al alistar, rentabilidad, anulación,
duplicados, devoluciones y equivalencias."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal as D

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import Conflicto, ReglaNegocio, SinPermiso
from app.core.tiempo import hoy
from app.modules.clientes import servicios as clientes
from app.modules.clientes.models import Cadena, SucursalCliente
from app.modules.clientes.schemas import CadenaEntrada, SucursalClienteEntrada
from app.modules.compras.schemas import CompraLineaEntrada
from app.modules.identidad.contexto import Contexto
from app.modules.inventario import consultas
from app.modules.inventario import servicios as inventario
from app.modules.inventario.models import Ajuste, EstadoAjuste, StockUbicacion
from app.modules.inventario.schemas import TransferenciaEntrada, TransferenciaLineaEntrada
from app.modules.pedidos import servicios as pedidos
from app.modules.pedidos.models import EstadoPedido, Pedido
from app.modules.pedidos.schemas import (
    AlistarEntrada,
    AlistarLineaEntrada,
    DevolucionEntrada,
    DevolucionLineaEntrada,
    PedidoBorradorEntrada,
    PedidoCrear,
    PedidoLineaEntrada,
)
from tests.conftest import Datos
from tests.fabrica import Catalogo, comprar, crear_catalogo

Login = Callable[[str], TestClient]
JPEG = b"\xff\xd8\xff\xe0" + b"0" * 200  # basta con la firma del formato


@dataclass
class Escenario:
    ctx: Contexto
    cat: Catalogo
    datos: Datos
    cadena: Cadena
    sucursal_cliente: SucursalCliente


@pytest.fixture
def esc(db: Session, datos: Datos) -> Escenario:
    ctx = Contexto(usuario=datos.dueno, ip=None, user_agent=None)
    cat = crear_catalogo(db, ctx)
    # 600 guantes en la sucursal a Bs 1 la unidad (2 fardos de 300 a Bs 300).
    comprar(
        db,
        ctx,
        cat,
        datos.sucursal.id,
        [
            CompraLineaEntrada(
                producto_id=cat.guantes.id,
                presentacion_id=next(
                    p.id for p in cat.guantes.presentaciones if p.nombre == "Fardo"
                ),
                cantidad=D(2),
                precio_presentacion=D(300),
            )
        ],
    )
    cadena = clientes.crear(db, ctx, CadenaEntrada(nombre="Hipermaxi"))
    sucursal = clientes.crear_sucursal(db, ctx, cadena.id, SucursalClienteEntrada(nombre="Obrajes"))
    return Escenario(ctx, cat, datos, cadena, sucursal)


def _saldo(db: Session, esc: Escenario) -> StockUbicacion:
    db.expire_all()
    saldo = db.scalar(
        select(StockUbicacion).where(
            StockUbicacion.ubicacion_id == esc.datos.sucursal.id,
            StockUbicacion.producto_id == esc.cat.guantes.id,
        )
    )
    assert saldo is not None
    return saldo


def _borrador(
    db: Session,
    esc: Escenario,
    *,
    cantidad: D = D(100),
    confirmada: D | None = None,
    numero_oc: str = "OC-1001",
    precio: D = D("1.50"),
    documento: bool = True,
    ctx: Contexto | None = None,
) -> Pedido:
    ctx = ctx or esc.ctx
    pedido = pedidos.crear(db, ctx, PedidoCrear(ubicacion_id=esc.datos.sucursal.id))
    if documento:
        pedidos.agregar_documentos(db, ctx, pedido.id, [(JPEG, "oc.jpg")])
    return pedidos.guardar_borrador(
        db,
        ctx,
        pedido.id,
        PedidoBorradorEntrada(
            ubicacion_id=esc.datos.sucursal.id,
            cadena_id=esc.cadena.id,
            sucursal_cliente_id=esc.sucursal_cliente.id,
            numero_oc=numero_oc,
            fecha_oc=hoy(),
            total_oc=(cantidad * precio).quantize(D("0.01")),
            lineas=[
                PedidoLineaEntrada(
                    codigo_cliente="HX-77",
                    descripcion_cliente="GUANTE LATEX M",
                    producto_id=esc.cat.guantes.id,
                    cantidad_oc=cantidad,
                    precio_oc=precio,
                    total_linea_oc=(cantidad * precio).quantize(D("0.01")),
                    cantidad_confirmada=confirmada,
                )
            ],
        ),
    )


def _alistar(db: Session, esc: Escenario, pedido: Pedido, cantidad: D, merma: D = D(0)) -> Pedido:
    return pedidos.alistar(
        db,
        esc.ctx,
        pedido.id,
        AlistarEntrada(
            lineas=[
                AlistarLineaEntrada(
                    linea_id=pedido.lineas[0].id, cantidad_alistada=cantidad, cantidad_merma=merma
                )
            ]
        ),
    )


def _verificar(db: Session, esc: Escenario) -> None:
    resultado = consultas.verificar(db, esc.ctx)
    assert resultado.correcto, resultado.diferencias


def test_flujo_completo_reserva_descuento_y_rentabilidad(db: Session, esc: Escenario) -> None:
    pedido = _borrador(db, esc)
    assert pedido.estado == EstadoPedido.BORRADOR
    assert _saldo(db, esc).comprometido == 0  # el borrador no toca el stock

    pedido = pedidos.confirmar(db, esc.ctx, pedido.id)
    saldo = _saldo(db, esc)
    assert pedido.estado == EstadoPedido.CONFIRMADO
    assert (saldo.fisico, saldo.comprometido) == (D(600), D(100))
    _verificar(db, esc)

    # Salen 90 (menos de lo confirmado) y 5 se encontraron rotos (D-11).
    pedido = _alistar(db, esc, pedido, D(90), merma=D(5))
    saldo = _saldo(db, esc)
    assert pedido.estado == EstadoPedido.ALISTADO
    assert (saldo.fisico, saldo.comprometido) == (D(505), D(0))
    linea = pedido.lineas[0]
    assert (linea.cantidad_alistada, linea.costo_unitario) == (D(90), D(1))
    assert (pedido.ingreso, pedido.costo, pedido.ganancia, pedido.margen) == (
        D("135.00"),
        D("90.00"),
        D("45.00"),
        D("33.33"),
    )
    merma = db.scalars(select(Ajuste).where(Ajuste.pedido_id == pedido.id)).one()
    assert merma.estado == EstadoAjuste.APLICADO  # el dueño puede aprobar
    _verificar(db, esc)

    pedido = pedidos.entregar(
        db,
        esc.ctx,
        pedido.id,
        receptor_nombre="Juan Pérez",
        observacion=None,
        foto=(JPEG, "constancia.jpg"),
        firma=None,
    )
    assert pedido.estado == EstadoPedido.ENTREGADO
    assert pedido.constancia_foto_id is not None
    with pytest.raises(ReglaNegocio, match="entregado no se puede anular"):
        pedidos.anular(db, esc.ctx, pedido.id, "Me equivoqué de pedido")
    assert [e.tipo for e in pedido.eventos] == [
        "CREADO",
        "DOCUMENTO_AGREGADO",
        "CONFIRMADO",
        "ALISTADO",
        "ENTREGADO",
    ]


def test_no_se_reserva_mas_de_lo_disponible(db: Session, esc: Escenario) -> None:
    pedido = _borrador(db, esc, cantidad=D(700))
    validaciones, _, _ = pedidos.revision(db, esc.ctx, pedido)
    assert any(v.nivel == "error" and "solo hay 600" in v.mensaje for v in validaciones)
    with pytest.raises(ReglaNegocio, match="solo hay 600"):
        pedidos.confirmar(db, esc.ctx, pedido.id)

    # D-02: el encargado reduce la cantidad y confirma un pedido incompleto.
    pedido = _borrador(db, esc, cantidad=D(700), confirmada=D(600), numero_oc="OC-1002")
    pedido = pedidos.confirmar(db, esc.ctx, pedido.id)
    assert (pedido.lineas[0].cantidad_oc, pedido.lineas[0].cantidad_confirmada) == (D(700), D(600))
    assert _saldo(db, esc).comprometido == D(600)


def test_no_se_confirma_mas_de_lo_que_pide_la_oc(db: Session, esc: Escenario) -> None:
    with pytest.raises(ReglaNegocio, match="más de lo que pide la OC"):
        _borrador(db, esc, cantidad=D(10), confirmada=D(11))


def test_lo_reservado_no_se_puede_transferir_ni_ajustar(db: Session, esc: Escenario) -> None:
    pedidos.confirmar(db, esc.ctx, _borrador(db, esc, cantidad=D(500)).id)

    def transferir(cantidad: D) -> None:
        inventario.transferir(
            db,
            esc.ctx,
            TransferenciaEntrada(
                origen_id=esc.datos.sucursal.id,
                destino_id=esc.datos.deposito.id,
                lineas=[
                    TransferenciaLineaEntrada(producto_id=esc.cat.guantes.id, cantidad=cantidad)
                ],
            ),
        )

    with pytest.raises(ReglaNegocio, match="disponible 100"):
        transferir(D(101))
    transferir(D(100))
    assert _saldo(db, esc).fisico == D(500)
    _verificar(db, esc)


def test_unidades_vencidas_no_se_reservan(db: Session, esc: Escenario) -> None:
    comprar(
        db,
        esc.ctx,
        esc.cat,
        esc.datos.sucursal.id,
        [
            CompraLineaEntrada(
                producto_id=esc.cat.leche.id,
                cantidad=D(10),
                precio_presentacion=D(5),
                lote_codigo="L-VIEJO",
                lote_vencimiento=hoy() - timedelta(days=1),
            )
        ],
    )
    pedido = pedidos.crear(db, esc.ctx, PedidoCrear(ubicacion_id=esc.datos.sucursal.id))
    pedidos.agregar_documentos(db, esc.ctx, pedido.id, [(JPEG, "oc.jpg")])
    pedidos.guardar_borrador(
        db,
        esc.ctx,
        pedido.id,
        PedidoBorradorEntrada(
            ubicacion_id=esc.datos.sucursal.id,
            cadena_id=esc.cadena.id,
            sucursal_cliente_id=esc.sucursal_cliente.id,
            numero_oc="OC-LECHE",
            fecha_oc=hoy(),
            lineas=[
                PedidoLineaEntrada(
                    descripcion_cliente="LECHE",
                    producto_id=esc.cat.leche.id,
                    cantidad_oc=D(5),
                    precio_oc=D(7),
                )
            ],
        ),
    )
    with pytest.raises(ReglaNegocio, match="solo hay 0"):
        pedidos.confirmar(db, esc.ctx, pedido.id)


def test_oc_duplicada(db: Session, esc: Escenario) -> None:
    primero = _borrador(db, esc, numero_oc="OC-2001")
    with pytest.raises(Conflicto, match="ya está registrada en el pedido"):
        _borrador(db, esc, numero_oc="oc-2001")  # sin distinguir mayúsculas
    pedidos.anular(db, esc.ctx, primero.id, "OC cargada por error")
    assert _borrador(db, esc, numero_oc="OC-2001").estado == EstadoPedido.BORRADOR


def test_confirmar_exige_la_oc_adjunta_y_los_datos(db: Session, esc: Escenario) -> None:
    pedido = _borrador(db, esc, documento=False)
    with pytest.raises(ReglaNegocio, match="Adjunte la OC"):
        pedidos.confirmar(db, esc.ctx, pedido.id)
    vacio = pedidos.crear(db, esc.ctx, PedidoCrear(ubicacion_id=esc.datos.sucursal.id))
    with pytest.raises(ReglaNegocio, match="Indique la cadena"):
        pedidos.confirmar(db, esc.ctx, vacio.id)


def test_los_pedidos_salen_de_una_sucursal(db: Session, esc: Escenario) -> None:
    with pytest.raises(ReglaNegocio, match="es un depósito"):
        pedidos.crear(db, esc.ctx, PedidoCrear(ubicacion_id=esc.datos.deposito.id))


def test_anular_confirmado_libera_y_alistado_revierte(db: Session, esc: Escenario) -> None:
    confirmado = pedidos.confirmar(db, esc.ctx, _borrador(db, esc, numero_oc="A").id)
    pedidos.anular(db, esc.ctx, confirmado.id, "El supermercado canceló")
    assert _saldo(db, esc).comprometido == 0

    alistado = pedidos.confirmar(db, esc.ctx, _borrador(db, esc, numero_oc="B").id)
    alistado = _alistar(db, esc, alistado, D(100))
    assert _saldo(db, esc).fisico == D(500)
    alistado = pedidos.anular(db, esc.ctx, alistado.id, "No se despachó")
    saldo = _saldo(db, esc)
    assert (saldo.fisico, saldo.comprometido) == (D(600), D(0))
    assert alistado.anulado_desde == EstadoPedido.ALISTADO
    _verificar(db, esc)


def test_devolucion_despues_de_entregar(db: Session, esc: Escenario) -> None:
    pedido = pedidos.confirmar(db, esc.ctx, _borrador(db, esc).id)
    pedido = _alistar(db, esc, pedido, D(100))
    pedido = pedidos.entregar(
        db, esc.ctx, pedido.id, receptor_nombre=None, observacion=None, foto=None, firma=None
    )
    entrada = DevolucionEntrada(
        motivo="Rechazo en recepción",
        lineas=[DevolucionLineaEntrada(linea_id=pedido.lineas[0].id, cantidad=D(20))],
    )
    pedido = pedidos.devolver(db, esc.ctx, pedido.id, entrada)
    assert _saldo(db, esc).fisico == D(520)
    assert (pedido.ingreso, pedido.costo, pedido.ganancia) == (D("120.00"), D("80.00"), D("40.00"))
    with pytest.raises(ReglaNegocio, match="se entregaron 80"):
        pedidos.devolver(
            db,
            esc.ctx,
            pedido.id,
            DevolucionEntrada(
                motivo="Otra devolución",
                lineas=[DevolucionLineaEntrada(linea_id=pedido.lineas[0].id, cantidad=D(81))],
            ),
        )
    _verificar(db, esc)


def test_equivalencias_aprendidas_al_confirmar(db: Session, esc: Escenario) -> None:
    antes = pedidos.sugerencias(
        db, esc.ctx, cadena_id=esc.cadena.id, codigo="HX-77", descripcion=None
    )
    assert antes == []
    pedidos.confirmar(db, esc.ctx, _borrador(db, esc).id)
    por_codigo = pedidos.sugerencias(
        db, esc.ctx, cadena_id=esc.cadena.id, codigo="hx-77", descripcion=None
    )
    assert por_codigo[0].producto.id == esc.cat.guantes.id
    assert por_codigo[0].fuente == "equivalencia"
    parecido = pedidos.sugerencias(
        db, esc.ctx, cadena_id=None, codigo=None, descripcion="guante de latex talla M"
    )
    assert parecido and parecido[0].producto.id == esc.cat.guantes.id


def test_precio_distinto_del_ultimo_genera_aviso(db: Session, esc: Escenario) -> None:
    pedidos.confirmar(db, esc.ctx, _borrador(db, esc, numero_oc="P1", precio=D("1.50")).id)
    segundo = _borrador(db, esc, numero_oc="P2", precio=D("1.20"))
    validaciones, _, precios = pedidos.revision(db, esc.ctx, segundo)
    assert precios[esc.cat.guantes.id][0] == D("1.5000")
    assert any(v.nivel == "aviso" and "distinto del último" in v.mensaje for v in validaciones)


def test_encargado_ve_solo_sus_pedidos_y_no_anula_ajenos(db: Session, esc: Escenario) -> None:
    esc.datos.encargado.ubicaciones = [esc.datos.sucursal]
    db.commit()
    ctx_encargado = Contexto(usuario=esc.datos.encargado, ip=None, user_agent=None)
    del_dueno = _borrador(db, esc, numero_oc="D1")
    propio = _borrador(db, esc, numero_oc="E1", ctx=ctx_encargado)
    listado = pedidos.listar(
        db,
        ctx_encargado,
        estado=None,
        cadena_id=None,
        ubicacion_id=None,
        buscar=None,
        desde=None,
        hasta=None,
        pagina=1,
        tamano=50,
    )
    assert [p.id for p in listado.items] == [propio.id]
    confirmado = pedidos.confirmar(db, ctx_encargado, propio.id)
    with pytest.raises(SinPermiso):
        pedidos.anular(db, ctx_encargado, confirmado.id, "Quiero anularlo")
    assert del_dueno.estado == EstadoPedido.BORRADOR


def test_merma_del_encargado_queda_pendiente(db: Session, esc: Escenario) -> None:
    esc.datos.encargado.ubicaciones = [esc.datos.sucursal]
    db.commit()
    ctx_encargado = Contexto(usuario=esc.datos.encargado, ip=None, user_agent=None)
    pedido = pedidos.confirmar(db, ctx_encargado, _borrador(db, esc, ctx=ctx_encargado).id)
    pedidos.alistar(
        db,
        ctx_encargado,
        pedido.id,
        AlistarEntrada(
            lineas=[
                AlistarLineaEntrada(
                    linea_id=pedido.lineas[0].id, cantidad_alistada=D(98), cantidad_merma=D(2)
                )
            ]
        ),
    )
    merma = db.scalars(select(Ajuste).where(Ajuste.pedido_id == pedido.id)).one()
    assert merma.estado == EstadoAjuste.PENDIENTE
    assert _saldo(db, esc).fisico == D(502)
    _verificar(db, esc)


def test_api_documentos_y_costos_ocultos(
    db: Session, esc: Escenario, iniciar_sesion: Login
) -> None:
    esc.datos.encargado.ubicaciones = [esc.datos.sucursal]
    db.commit()
    encargado = iniciar_sesion("encargado@prueba.bo")
    r = encargado.post("/api/pedidos", json={"ubicacion_id": str(esc.datos.sucursal.id)})
    assert r.status_code == 201, r.text
    pedido_id = r.json()["id"]

    r = encargado.post(
        f"/api/pedidos/{pedido_id}/documentos",
        files=[("archivos", ("virus.exe", b"MZ\x90\x00", "application/octet-stream"))],
    )
    assert r.status_code == 422
    assert "no es una imagen" in r.json()["detalle"]

    r = encargado.post(
        f"/api/pedidos/{pedido_id}/documentos",
        files=[
            ("archivos", ("pagina1.jpg", JPEG, "image/jpeg")),
            ("archivos", ("oc.pdf", b"%PDF-1.7\n...", "application/pdf")),
        ],
    )
    assert r.status_code == 200, r.text
    documentos = r.json()["detalle_documentos"]
    assert [d["tipo_mime"] for d in documentos] == ["image/jpeg", "application/pdf"]
    r = encargado.get(f"/api/pedidos/{pedido_id}/archivos/{documentos[0]['id']}")
    assert r.status_code == 200 and r.content == JPEG

    r = encargado.put(
        f"/api/pedidos/{pedido_id}",
        json={
            "ubicacion_id": str(esc.datos.sucursal.id),
            "cadena_id": str(esc.cadena.id),
            "sucursal_cliente_id": str(esc.sucursal_cliente.id),
            "numero_oc": "API-1",
            "fecha_oc": str(date.today()),
            "lineas": [
                {
                    "descripcion_cliente": "GUANTE",
                    "producto_id": str(esc.cat.guantes.id),
                    "cantidad_oc": "10",
                    "precio_oc": "1.5",
                }
            ],
        },
    )
    assert r.status_code == 200, r.text
    linea = r.json()["detalle_lineas"][0]
    assert linea["disponible"] == "600.000"
    assert encargado.post(f"/api/pedidos/{pedido_id}/confirmar").status_code == 200
    r = encargado.post(
        f"/api/pedidos/{pedido_id}/alistar",
        json={"lineas": [{"linea_id": linea["id"], "cantidad_alistada": "10"}]},
    )
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["ingreso"] == "15.00"
    assert cuerpo["costo"] is None and cuerpo["ganancia"] is None  # sin costos.ver
    assert cuerpo["detalle_lineas"][0]["costo_unitario"] is None

    dueno = iniciar_sesion("dueno@prueba.bo")
    r = dueno.get(f"/api/pedidos/{pedido_id}")
    assert r.json()["ganancia"] == "5.00"
