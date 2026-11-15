"""Lectura automática de OC: interpretación (sin OCR, con palabras sintéticas) y su
integración con los pedidos (con un extractor falso)."""

from contextlib import nullcontext
from datetime import date
from decimal import Decimal as D

import pytest
from sqlalchemy.orm import Session

from app.core.tiempo import hoy
from app.modules.documentos.lectura import numeros
from app.modules.documentos.lectura.interpretar import interpretar
from app.modules.documentos.lectura.modelos import Palabra
from app.modules.documentos.lectura.plantillas.base import conciliar
from app.modules.pedidos import lectura
from app.modules.pedidos import servicios as pedidos
from app.modules.pedidos.models import EstadoLectura, Lectura
from app.modules.pedidos.schemas import PedidoCrear
from tests.test_pedidos import JPEG, Escenario
from tests.test_pedidos import esc as esc

# ---------------------------------------------------------------- documentos sintéticos


def _hoja(filas: list[list[tuple[int, str]]], *, confianza: float = 0.99) -> list[Palabra]:
    """Cada fila: [(x, texto), …]; las filas se separan 20 px en vertical."""
    palabras = []
    for i, fila in enumerate(filas):
        y = 100 + i * 20
        for x, texto in fila:
            palabras.append(Palabra(texto, x, y, x + 8 * len(texto), y + 12, confianza))
    return palabras


HIPERMAXI = [
    [(77, "Nro. O/C: 11472345"), (412, "HIPERMAXI S.A"), (695, "F. Impreso: 10/11/2026")],
    [(320, "DOCUMENTO DE AVISO DE DESPACHO")],
    [
        (85, "Nro. Aviso de despacho:"),
        (274, "3993213"),
        (473, "Fecha de entrega:"),
        (663, "11/11/2026"),
    ],
    [
        (87, "Nro. de Orden de Compra:"),
        (275, "11472345"),
        (472, "Fecha de Orden de Compra:"),
        (665, "10/11/2026"),
    ],
    [(492, "Enviar a.:"), (568, "HIPERMAXI TORRES DEL POETA")],
    [
        (93, "Barra"),
        (190, "Barra"),
        (285, "Descripción"),
        (452, "Cant. OC"),
        (537, "Cant."),
        (592, "U/M"),
        (641, "Precio U."),
        (711, "Total Bs"),
        (774, "Recepción"),
    ],
    [(93, "Proveedor"), (190, "Hipermaxi"), (287, "Producto"), (536, "Dpcho.")],
    [
        (96, "HIPER20120910350561"),
        (284, "BOLSA BLANCA BELEN ECO"),
        (496, "40"),
        (566, "40 PCE"),
        (671, "19.5"),
        (740, "780"),
        (790, "-40-"),
    ],
    [(95, "461585"), (284, "27X48X100 S/E")],
    [
        (99, "900100722386"),
        (190, "90010072238"),
        (286, "GUANTES ASATEX GRUESO"),
        (497, "72"),
        (567, "72 PCE"),
        (673, "13.8"),
        (727, "9£6"),
    ],  # total ilegible
    [(286, "TALLA 8")],
    [
        (116, "4710348816909 471034881690"),
        (298, "GUANTE JOHN TALLA 8"),
        (501, "21"),
        (565, "12 PCE"),
        (671, "16.8"),
        (730, "201.6"),
    ],  # Cant. OC mal leída (21 por 12)
    [(110, "Nro. Doc:"), (440, "Paq. :"), (500, "124"), (650, "SubTotal:"), (720, "1,975.20")],
    [(650, "Total:"), (720, "1,975.20")],
    [(118, "Responsable: 220153 ZALLES COLLQUE BISMARCK RAUL")],
]


def test_numeros_y_fechas() -> None:
    assert numeros.numero("1,324.80") == D("1324.80")
    assert numeros.numero("1.324,80") == D("1324.80")
    assert numeros.numero("13,8") == D("13.8")
    assert numeros.numero("1O3") == D("103")  # O leída en lugar de 0
    assert numeros.numero("PCE") is None
    assert numeros.fecha("Fecha: 10/11/2026 06:13") == date(2026, 11, 10)


def test_conciliar_corrige_la_lectura_mas_dudosa() -> None:
    assert conciliar([D(40), D(40)], D("19.5"), D(780)) == (D(40), D("19.5"), D(780), 1.0)
    assert conciliar([D(21), D(12)], D("16.8"), D("201.6"))[0] == D(12)  # usa Cant. Dpcho.
    cantidad, precio, total, factor = conciliar(
        [D(24)], D("16.8"), D(1032), conf_precio=1, conf_total=0.7
    )
    assert (cantidad, precio, total, factor) == (D(24), D("16.8"), D("403.20"), 0.6)


def test_plantilla_hipermaxi() -> None:
    oc = interpretar(_hoja(HIPERMAXI))
    assert oc.plantilla == "hipermaxi"
    assert (oc.numero_oc, oc.fecha_oc, oc.fecha_entrega) == (
        "11472345",
        date(2026, 11, 10),
        date(2026, 11, 11),
    )
    assert oc.destino_texto == "HIPERMAXI TORRES DEL POETA"
    assert oc.total == D("1975.20")
    assert oc.emisor == "Zalles Collque Bismarck Raul"
    assert [(x.codigo, x.cantidad, x.precio, x.total) for x in oc.lineas] == [
        ("350561", D(40), D("19.5"), D(780)),
        ("90010072238", D(72), D("13.8"), D("993.6")),
        ("471034881690", D(12), D("16.8"), D("201.6")),
    ]
    assert oc.lineas[0].codigo_alterno == "HIPER20120910461585"
    assert oc.lineas[0].descripcion == "BOLSA BLANCA BELEN ECO 27X48X100 S/E"
    assert oc.lineas[1].confianza["total"] < 0.85  # se calculó: queda resaltado para revisar
    assert oc.aritmetica_ok


def test_plantilla_generica_para_formatos_desconocidos() -> None:
    hoja = [
        [(80, "SUPERMERCADO KETAL S.A."), (500, "ORDEN DE COMPRA N° 778812")],
        [(80, "Fecha de emisión: 03/11/2026"), (500, "Fecha de entrega: 05/11/2026")],
        [(80, "Entregar en: KETAL CALACOTO")],
        [(80, "Código"), (200, "Artículo"), (480, "Cant."), (560, "P. Unit."), (650, "Importe")],
        [
            (80, "7701234567890"),
            (200, "GUANTE LATEX M"),
            (480, "24"),
            (560, "12.50"),
            (650, "300.00"),
        ],
        [
            (80, "7709876543210"),
            (200, "BOLSA BASURA 50L"),
            (480, "10"),
            (560, "8.00"),
            (650, "80.00"),
        ],
        [(560, "TOTAL Bs"), (650, "380.00")],
    ]
    oc = interpretar(_hoja(hoja))
    assert oc.plantilla == "generica"
    assert (oc.numero_oc, oc.fecha_oc, oc.total) == ("778812", date(2026, 11, 3), D("380.00"))
    assert oc.destino_texto == "KETAL CALACOTO"
    assert [(x.codigo, x.descripcion, x.cantidad, x.precio) for x in oc.lineas] == [
        ("7701234567890", "GUANTE LATEX M", D(24), D("12.50")),
        ("7709876543210", "BOLSA BASURA 50L", D(10), D("8.00")),
    ]
    assert oc.aritmetica_ok


RECEPCION = [
    [
        (36, "COMPRAS"),
        (269, "HIPERMAXI"),
        (327, "S.A"),
        (498, "No."),
        (515, "Rec."),
        (536, ":"),
        (541, "8345686"),
    ],
    [
        (36, "14-11-2026"),
        (254, "NOTA"),
        (284, "DE"),
        (300, "RECEPCION"),
        (496, "Fecha"),
        (525, ":"),
        (530, "22/10/2026"),
    ],
    [(36, "No."), (53, "O/C."), (80, ":"), (85, "11409941"), (506, "T/C"), (529, "11.68")],
    [(36, "U/N"), (78, ":"), (84, "42"), (96, "U.N."), (118, "EL"), (133, "PRADO")],
    [
        (38, "Cod."),
        (60, "Articulo"),
        (118, "Cod."),
        (140, "Fabrica"),
        (198, "Descripcion"),
        (383, "U/M"),
        (426, "Cantidad"),
        (488, "Precio"),
        (516, "U."),
        (560, "Total"),
    ],
    [
        (58, "350561"),
        (118, "350561"),
        (188, "BOLSA"),
        (216, "BLANCA"),
        (251, "BELEN"),
        (383, "PCE"),
        (438, "100.00"),
        (503, "19.500"),
        (560, "1,950.00"),
    ],
    [
        (58, "660378"),
        (118, "90010072238"),
        (188, "GUANTES"),
        (227, "ASATEX"),
        (261, "GRUESO"),
        (383, "PCE"),
        (438, "48.00"),
        (503, "13.800"),
        (560, "662.40"),
    ],
    [
        (36, "Almacen"),
        (77, ":"),
        (82, "42"),
        (95, "CBBA"),
        (376, "Paq."),
        (401, "148.00"),
        (488, "SubTotal"),
        (527, ":"),
        (545, "2,612.40"),
    ],
    [
        (36, "No.Ingr."),
        (83, "40582019"),
        (426, "0.000"),
        (451, "%"),
        (484, "Descuento"),
        (529, ":"),
        (549, "12.40"),
    ],
    [(36, "Acreedor"), (491, "Total"), (515, "Bs"), (528, ":"), (548, "2,600.00")],
    [(36, "Cta.x"), (60, "Pagar"), (133, "Fecha"), (159, "Vcto."), (184, ":"), (189, "30/10/2026")],
]


def test_plantilla_nota_de_recepcion_hipermaxi() -> None:
    oc = interpretar(_hoja(RECEPCION))
    assert oc.plantilla == "hipermaxi_recepcion"
    assert (oc.numero_oc, oc.numero_documento, oc.fecha_oc) == (
        "11409941",
        "8345686",
        date(2026, 10, 22),
    )
    assert oc.destino_texto == "EL PRADO"
    assert (oc.total, oc.descuento) == (D("2600.00"), D("12.40"))
    assert [
        (x.codigo, x.codigo_alterno, x.descripcion, x.cantidad, x.precio, x.total)
        for x in oc.lineas
    ] == [
        ("350561", "350561", "BOLSA BLANCA BELEN", D(100), D("19.5"), D(1950)),
        ("660378", "90010072238", "GUANTES ASATEX GRUESO", D(48), D("13.8"), D("662.4")),
    ]
    assert oc.aritmetica_ok  # subtotal - descuento = total


def test_nota_de_recepcion_fotografiada() -> None:
    """Con OCR, las cajas suelen juntar varias palabras ("Cod. Fabrica", "350561 350561")."""
    filas = [list(f) for f in RECEPCION]
    filas[4] = [
        (69, "Cod. Articulo"),
        (259, "Cod. Fabrica"),
        (445, "Descripcion"),
        (881, "U/M"),
        (984, "Cantidad"),
        (1129, "Precio U."),
        (1298, "Total"),
    ]
    filas[5] = [
        (117, "350561"),
        (259, "350561"),
        (424, "BOLSA BLANCA BELEN"),
        (882, "PCE"),
        (1015, "100.00"),
        (1170, "19.500"),
        (1303, "1,950.00"),
    ]
    filas[6] = [
        (127, "660378 90010072238"),
        (435, "GUANTES ASATEX GRUESO"),
        (893, "PCE 48.00"),
        (1180, "13.800"),
        (1311, "662.40"),
    ]
    oc = interpretar(_hoja(filas))
    assert [(x.codigo, x.codigo_alterno, x.cantidad, x.total) for x in oc.lineas] == [
        ("350561", "350561", D(100), D(1950)),
        ("660378", "90010072238", D(48), D("662.4")),
    ]


# ---------------------------------------------------------------- integración con pedidos


class ExtractorFalso:
    nombre = "falso"

    def __init__(self, filas: list[list[tuple[int, str]]]) -> None:
        self.filas = filas

    def extraer(self, archivos: list[tuple[bytes, str]]) -> list[Palabra]:
        assert archivos and archivos[0][1] == "image/jpeg"
        return _hoja(self.filas)


@pytest.fixture
def cola(monkeypatch: pytest.MonkeyPatch) -> list[object]:
    encoladas: list[object] = []
    monkeypatch.setattr(lectura, "encolar", encoladas.append)
    return encoladas


def _hipermaxi_de_prueba(esc: Escenario) -> list[list[tuple[int, str]]]:
    """La hoja sintética apuntando a datos del escenario: una línea con el código de los
    guantes ya aprendido y otra desconocida."""
    filas = [list(f) for f in HIPERMAXI[:7]]
    fecha = hoy().strftime("%d/%m/%Y")
    filas[3] = [
        (87, "Nro. de Orden de Compra:"),
        (275, "55501"),
        (472, "Fecha de Orden de Compra:"),
        (665, fecha),
    ]
    filas[4] = [(492, "Enviar a.:"), (568, "HIPERMAXI OBRAJES LA PAZ")]
    filas += [
        [
            (99, "777"),
            (190, "HX-77"),
            (286, "GUANTE LATEX M"),
            (497, "50"),
            (567, "50 PCE"),
            (673, "1.5"),
            (727, "75"),
        ],
        [
            (99, "888"),
            (190, "HX-99"),
            (286, "PRODUCTO NUEVO"),
            (497, "10"),
            (567, "10 PCE"),
            (673, "2"),
            (727, "20"),
        ],
        [(650, "Total:"), (720, "95.00")],
    ]
    return filas


def test_la_oc_se_lee_al_subirla_y_completa_el_borrador(
    db: Session, esc: Escenario, cola: list[object]
) -> None:
    # Equivalencia aprendida: HX-77 = guantes (de un pedido anterior confirmado).
    from tests.test_pedidos import _borrador

    pedidos.confirmar(db, esc.ctx, _borrador(db, esc, numero_oc="OC-ANTERIOR").id)
    cola.clear()

    pedido = pedidos.crear(db, esc.ctx, PedidoCrear(ubicacion_id=esc.datos.sucursal.id))
    pedidos.agregar_documentos(db, esc.ctx, pedido.id, [(JPEG, "oc.jpg")])
    assert len(cola) == 1
    lect = lectura.ultima(db, pedido.id)
    assert lect is not None and lect.estado == EstadoLectura.PENDIENTE

    lectura.procesar(
        lect.id, ExtractorFalso(_hipermaxi_de_prueba(esc)), sesion=lambda: nullcontext(db)
    )
    db.expire_all()
    lect = db.get(Lectura, lect.id)
    assert lect is not None
    assert (lect.estado, lect.plantilla, lect.aritmetica_ok, lect.aplicada) == (
        EstadoLectura.COMPLETADA,
        "hipermaxi",
        True,
        True,
    )
    pedido = pedidos.obtener(db, esc.ctx, pedido.id)
    assert pedido.cadena_id == esc.cadena.id
    assert pedido.sucursal_cliente_id == esc.sucursal_cliente.id  # "Obrajes" reconocido
    assert (pedido.numero_oc, pedido.total_oc) == ("55501", D("95.00"))
    assert [x.producto_id for x in pedido.lineas] == [esc.cat.guantes.id, None]
    assert pedido.lineas[0].confianza and pedido.lineas[0].confianza["cantidad"] > 0.9
    assert [e.tipo for e in pedido.eventos][-1] == "LEIDO"

    # El encargado elige el producto de la línea nueva, corrige un precio y confirma:
    # quedan registradas las correcciones (dato para medir la precisión del formato).
    from app.modules.pedidos.schemas import PedidoBorradorEntrada, PedidoLineaEntrada

    pedidos.guardar_borrador(
        db,
        esc.ctx,
        pedido.id,
        PedidoBorradorEntrada(
            ubicacion_id=esc.datos.sucursal.id,
            cadena_id=esc.cadena.id,
            sucursal_cliente_id=esc.sucursal_cliente.id,
            numero_oc="55501",
            fecha_oc=hoy(),
            total_oc=D("95.00"),
            lineas=[
                PedidoLineaEntrada(
                    codigo_cliente="HX-77",
                    descripcion_cliente="GUANTE LATEX M",
                    producto_id=esc.cat.guantes.id,
                    cantidad_oc=D(50),
                    precio_oc=D("1.5"),
                    total_linea_oc=D(75),
                ),
                PedidoLineaEntrada(
                    codigo_cliente="HX-99",
                    descripcion_cliente="PRODUCTO NUEVO",
                    producto_id=esc.cat.guantes.id,
                    cantidad_oc=D(10),
                    precio_oc=D("2.5"),
                    total_linea_oc=D(25),
                ),
            ],
        ),
    )
    pedidos.confirmar(db, esc.ctx, pedido.id)
    lect = db.get(Lectura, lect.id)
    assert lect is not None and lect.precision is not None
    cambios = lect.correcciones["cambios"] if lect.correcciones else []
    assert {(c["campo"], c["linea"]) for c in cambios} == {
        ("precio", 2),
        ("total_linea", 2),
    }
    assert lect.precision == D("77.78")  # 7 de 9 campos sin corregir


def test_no_pisa_lo_cargado_a_mano(db: Session, esc: Escenario, cola: list[object]) -> None:
    from tests.test_pedidos import _borrador

    pedido = _borrador(db, esc, numero_oc="A-MANO")  # sube la OC y luego carga datos a mano
    lect = lectura.ultima(db, pedido.id)
    assert lect is not None
    lectura.procesar(
        lect.id, ExtractorFalso(_hipermaxi_de_prueba(esc)), sesion=lambda: nullcontext(db)
    )
    db.expire_all()
    pedido = pedidos.obtener(db, esc.ctx, pedido.id)
    assert pedido.numero_oc == "A-MANO"
    lect = db.get(Lectura, lect.id)
    assert lect is not None and lect.estado == EstadoLectura.COMPLETADA and not lect.aplicada


def test_lectura_fallida_queda_registrada(db: Session, esc: Escenario, cola: list[object]) -> None:
    class ExtractorRoto:
        nombre = "roto"

        def extraer(self, archivos: list[tuple[bytes, str]]) -> list[Palabra]:
            raise ValueError("imagen ilegible")

    pedido = pedidos.crear(db, esc.ctx, PedidoCrear(ubicacion_id=esc.datos.sucursal.id))
    pedidos.agregar_documentos(db, esc.ctx, pedido.id, [(JPEG, "oc.jpg")])
    lect = lectura.ultima(db, pedido.id)
    assert lect is not None
    lectura.procesar(lect.id, ExtractorRoto(), sesion=lambda: nullcontext(db))
    lect = db.get(Lectura, lect.id)
    assert lect is not None and lect.estado == EstadoLectura.FALLIDA
    assert lect.error and "Cargue los datos a mano" in lect.error


def test_nota_de_recepcion_completa_el_borrador(
    db: Session, esc: Escenario, cola: list[object]
) -> None:
    from app.modules.catalogo import servicios as catalogo
    from app.modules.catalogo.schemas import ProductoEntrada
    from app.modules.clientes import servicios as clientes
    from app.modules.clientes.schemas import SucursalClienteEntrada

    # El SKU del producto es el código de fábrica (D-22): se empareja solo, sin equivalencia.
    guante = catalogo.crear_producto(
        db,
        esc.ctx,
        ProductoEntrada(
            sku="90010072238",
            nombre="GUANTES ASATEX GRUESO TALLA 8",
            categoria_id=esc.cat.guantes.categoria_id,
        ),
    )
    prado = clientes.crear_sucursal(
        db, esc.ctx, esc.cadena.id, SucursalClienteEntrada(nombre="El Prado")
    )
    db.expire_all()  # la cadena ya estaba cargada en la sesión sin la sucursal nueva
    filas = [list(f) for f in RECEPCION]
    filas[1][-1] = (530, hoy().strftime("%d/%m/%Y"))
    pedido = pedidos.crear(
        db,
        esc.ctx,
        PedidoCrear(ubicacion_id=esc.datos.sucursal.id, observaciones="Entregar temprano"),
    )
    pedidos.agregar_documentos(db, esc.ctx, pedido.id, [(JPEG, "nota.jpg")])
    lect = lectura.ultima(db, pedido.id)
    assert lect is not None
    lectura.procesar(lect.id, ExtractorFalso(filas), sesion=lambda: nullcontext(db))
    db.expire_all()
    pedido = pedidos.obtener(db, esc.ctx, pedido.id)
    assert (pedido.cadena_id, pedido.sucursal_cliente_id) == (esc.cadena.id, prado.id)
    assert (pedido.numero_oc, pedido.fecha_oc, pedido.total_oc) == ("11409941", hoy(), D("2600"))
    assert pedido.observaciones == "Nota de recepción N.º 8345686 · Entregar temprano"
    assert [x.producto_id for x in pedido.lineas] == [None, guante.id]
    assert pedido.lineas[1].codigo_cliente == "660378"
