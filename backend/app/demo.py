"""Datos de demostración del catálogo e inventario (solo desarrollo).

Usa los mismos servicios que la aplicación, así que todo queda auditado y en el kardex.
"""

from datetime import timedelta
from decimal import Decimal as D

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.tiempo import hoy
from app.modules.catalogo import servicios as catalogo
from app.modules.catalogo.models import Categoria, Marca, Producto
from app.modules.catalogo.schemas import NombreEntrada, PresentacionEntrada, ProductoEntrada
from app.modules.clientes import servicios as clientes
from app.modules.clientes.schemas import CadenaEntrada, SucursalClienteEntrada
from app.modules.compras import servicios as compras
from app.modules.compras.schemas import CompraCostoEntrada, CompraEntrada, CompraLineaEntrada
from app.modules.identidad.contexto import Contexto
from app.modules.inventario import servicios as inventario
from app.modules.inventario.schemas import TransferenciaEntrada, TransferenciaLineaEntrada
from app.modules.organizacion.models import Ubicacion
from app.modules.proveedores import servicios as proveedores
from app.modules.proveedores.schemas import ProveedorEntrada

# (sku, nombre, categoría, marca, unidad, vence, [(presentación, factor)], precio por la mayor)
PRODUCTOS = [
    (
        "PAN-001",
        "Paño multiuso amarillo",
        "Limpieza",
        "Brillex",
        "paño",
        False,
        [("Fardo", 100), ("Paquete", 10)],
        "250",
    ),
    (
        "VIR-001",
        "Viruta de acero",
        "Limpieza",
        "Brillex",
        "unidad",
        False,
        [("Caja", 144), ("Docena", 12)],
        "180",
    ),
    (
        "GUA-001",
        "Guante de látex talla M",
        "Limpieza",
        "Protek",
        "par",
        False,
        [("Caja", 600), ("Fardo", 300)],
        "900",
    ),
    (
        "ESP-001",
        "Esponja doble uso",
        "Limpieza",
        "Brillex",
        "unidad",
        False,
        [("Fardo", 120), ("Paquete", 6)],
        "216",
    ),
    (
        "DET-001",
        "Detergente en polvo 1 kg",
        "Limpieza",
        "Espumax",
        "bolsa",
        False,
        [("Fardo", 12)],
        "168",
    ),
    (
        "LAV-001",
        "Lavavajillas líquido 750 ml",
        "Limpieza",
        "Espumax",
        "botella",
        False,
        [("Caja", 12)],
        "120",
    ),
    (
        "JAB-001",
        "Jabón de tocador 90 g",
        "Higiene",
        "Suave",
        "unidad",
        False,
        [("Caja", 72), ("Paquete", 3)],
        "216",
    ),
    (
        "PAP-001",
        "Papel higiénico doble hoja",
        "Higiene",
        "Suave",
        "rollo",
        False,
        [("Fardo", 48), ("Paquete", 4)],
        "168",
    ),
    (
        "BOL-001",
        "Bolsa de basura 50 L",
        "Hogar",
        "Protek",
        "unidad",
        False,
        [("Fardo", 500), ("Paquete", 10)],
        "300",
    ),
    (
        "LEC-001",
        "Leche entera 1 L",
        "Alimentos",
        "Valle Andino",
        "unidad",
        True,
        [("Caja", 12)],
        "72",
    ),
    (
        "YOG-001",
        "Yogur bebible frutilla 1 L",
        "Alimentos",
        "Valle Andino",
        "unidad",
        True,
        [("Caja", 6)],
        "60",
    ),
    ("CAR-001", "Carne de res molida", "Alimentos", None, "kg", True, [], "48"),
]

CADENAS = {
    "Hipermaxi": ["Hipermaxi Zona Sur", "Hipermaxi Obrajes", "Hipermaxi Sopocachi"],
    "Ketal": ["Ketal Calacoto", "Ketal San Miguel"],
    "Fidalga": ["Fidalga El Prado"],
}


def cargar(db: Session, ctx: Contexto) -> bool:
    """Devuelve False si el catálogo ya tenía productos (no hace nada)."""
    if db.scalar(select(Producto.id).where(Producto.empresa_id == ctx.empresa_id).limit(1)):
        return False

    categorias = {
        n: catalogo.crear_simple(db, ctx, Categoria, NombreEntrada(nombre=n))
        for n in ("Limpieza", "Higiene", "Hogar", "Alimentos")
    }
    marcas = {
        n: catalogo.crear_simple(db, ctx, Marca, NombreEntrada(nombre=n))
        for n in ("Brillex", "Protek", "Espumax", "Suave", "Valle Andino")
    }
    productos: dict[str, tuple[Producto, D]] = {}
    for sku, nombre, cat, marca, unidad, vence, pres, precio in PRODUCTOS:
        p = catalogo.crear_producto(
            db,
            ctx,
            ProductoEntrada(
                sku=sku,
                nombre=nombre,
                categoria_id=categorias[cat].id,
                marca_id=marcas[marca].id if marca else None,
                unidad_base=unidad,
                controla_vencimiento=vence,
                presentaciones=[PresentacionEntrada(nombre=n, factor=D(f)) for n, f in pres],
            ),
        )
        productos[sku] = (p, D(precio))

    limpieza = proveedores.crear(
        db,
        ctx,
        ProveedorEntrada(
            nombre="Importadora Limpieza Total (demo)",
            nit="1020304050",
            telefono="2-2400000",
            contacto="Rosa Quispe",
            producto_ids=[
                productos[s][0].id
                for s in (
                    "PAN-001",
                    "VIR-001",
                    "GUA-001",
                    "ESP-001",
                    "DET-001",
                    "LAV-001",
                    "BOL-001",
                )
            ],
        ),
    )
    consumo = proveedores.crear(
        db,
        ctx,
        ProveedorEntrada(
            nombre="Distribuidora Consumo Andino (demo)",
            nit="2030405060",
            telefono="2-2410000",
            contacto="Marco Mamani",
            producto_ids=[
                productos[s][0].id for s in ("JAB-001", "PAP-001", "LEC-001", "YOG-001", "CAR-001")
            ],
        ),
    )
    for cadena, sucursales in CADENAS.items():
        c = clientes.crear(db, ctx, CadenaEntrada(nombre=cadena))
        for s in sucursales:
            clientes.crear_sucursal(db, ctx, c.id, SucursalClienteEntrada(nombre=s))

    ubic = {
        u.nombre: u
        for u in db.scalars(select(Ubicacion).where(Ubicacion.empresa_id == ctx.empresa_id))
    }
    deposito = ubic.get("Depósito Central")
    if deposito is None:
        return True

    def linea(
        sku: str, cantidad: str, lote: str | None = None, dias: int | None = None
    ) -> CompraLineaEntrada:
        producto, precio = productos[sku]
        mayor = producto.presentaciones[0] if producto.presentaciones else None
        return CompraLineaEntrada(
            producto_id=producto.id,
            presentacion_id=mayor.id if mayor else None,
            cantidad=D(cantidad),
            precio_presentacion=precio,
            lote_codigo=lote,
            lote_vencimiento=hoy() + timedelta(days=dias) if dias is not None else None,
        )

    compras.registrar(
        db,
        ctx,
        CompraEntrada(
            proveedor_id=limpieza.id,
            ubicacion_id=deposito.id,
            fecha=hoy() - timedelta(days=10),
            numero_documento="F-001245",
            lineas=[
                linea("PAN-001", "8"),
                linea("VIR-001", "5"),
                linea("GUA-001", "3"),
                linea("ESP-001", "4"),
                linea("DET-001", "10"),
                linea("LAV-001", "6"),
                linea("BOL-001", "2"),
            ],
            costos=[CompraCostoEntrada(concepto="Flete", monto=D("150"))],
        ),
    )
    compras.registrar(
        db,
        ctx,
        CompraEntrada(
            proveedor_id=consumo.id,
            ubicacion_id=deposito.id,
            fecha=hoy() - timedelta(days=3),
            numero_documento="NV-7781",
            lineas=[
                linea("JAB-001", "4"),
                linea("PAP-001", "6"),
                linea("LEC-001", "10", "L-2611A", 20),
                linea("LEC-001", "5", "L-2612B", 35),
                linea("YOG-001", "8", "Y-0042", 12),
                linea("CAR-001", "40", "C-1114", 4),
            ],
        ),
    )
    for nombre_sucursal, cantidades in (
        ("Sucursal Centro", {"PAN-001": "150", "VIR-001": "96", "DET-001": "24", "LEC-001": "36"}),
        ("Sucursal Sur", {"PAN-001": "100", "ESP-001": "60", "JAB-001": "72", "CAR-001": "15"}),
    ):
        sucursal = ubic.get(nombre_sucursal)
        if sucursal:
            inventario.transferir(
                db,
                ctx,
                TransferenciaEntrada(
                    origen_id=deposito.id,
                    destino_id=sucursal.id,
                    observaciones="Reposición inicial",
                    lineas=[
                        TransferenciaLineaEntrada(producto_id=productos[s][0].id, cantidad=D(c))
                        for s, c in cantidades.items()
                    ],
                ),
            )
    return True


# ---------------------------------------------------------------- pedidos de ejemplo


def _pdf_oc(titulo: str, renglones: list[str]) -> bytes:
    """PDF mínimo de una página con texto: hace de OC de ejemplo en el visor."""

    def escapar(t: str) -> str:
        return t.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    texto = ["BT", "/F1 16 Tf", "50 790 Td", f"({escapar(titulo)}) Tj", "/F1 11 Tf"]
    for r in renglones:
        texto += ["0 -20 Td", f"({escapar(r)}) Tj"]
    texto.append("ET")
    contenido = "\n".join(texto).encode("latin-1")
    objetos = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n" % len(contenido) + contenido + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>",
    ]
    salida = b"%PDF-1.4\n"
    posiciones = []
    for i, obj in enumerate(objetos, start=1):
        posiciones.append(len(salida))
        salida += b"%d 0 obj\n" % i + obj + b"\nendobj\n"
    inicio_xref = len(salida)
    salida += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objetos) + 1)
    salida += b"".join(b"%010d 00000 n \n" % p for p in posiciones)
    salida += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objetos) + 1,
        inicio_xref,
    )
    return salida


def cargar_pedidos(db: Session, ctx: Contexto) -> bool:
    """Tres pedidos de ejemplo (entregado, confirmado y un borrador para revisar).
    Devuelve False si ya había pedidos."""
    from app.modules.clientes.models import Cadena, SucursalCliente
    from app.modules.pedidos import servicios as pedidos
    from app.modules.pedidos.models import Pedido
    from app.modules.pedidos.schemas import (
        AlistarEntrada,
        AlistarLineaEntrada,
        PedidoBorradorEntrada,
        PedidoCrear,
        PedidoLineaEntrada,
    )

    if db.scalar(select(Pedido.id).where(Pedido.empresa_id == ctx.empresa_id).limit(1)):
        return False
    sucursal = db.scalar(
        select(Ubicacion).where(
            Ubicacion.empresa_id == ctx.empresa_id, Ubicacion.nombre == "Sucursal Centro"
        )
    )
    productos = {
        p.sku: p for p in db.scalars(select(Producto).where(Producto.empresa_id == ctx.empresa_id))
    }
    destinos = {
        s.nombre: s
        for s in db.scalars(
            select(SucursalCliente)
            .join(Cadena, Cadena.id == SucursalCliente.cadena_id)
            .where(Cadena.empresa_id == ctx.empresa_id)
        )
    }
    if sucursal is None or not {"PAN-001", "DET-001", "VIR-001", "LEC-001"} <= productos.keys():
        return False

    # (destino, n.º OC, días atrás, [(código, descripción, sku o None, cantidad, precio, total)])
    Linea = tuple[str, str, str | None, str, str, str]
    ejemplos: list[tuple[str, str, int, list[Linea]]] = [
        (
            "Hipermaxi Obrajes",
            "HX-55120",
            2,
            [
                ("770101", "PANO MULTIUSO AMARILLO", "PAN-001", "50", "3.20", "160.00"),
                ("770455", "DETERGENTE POLVO 1KG", "DET-001", "12", "16.50", "198.00"),
            ],
        ),
        (
            "Ketal Calacoto",
            "KT-9087",
            1,
            [
                ("K-2231", "VIRUTA ACERO UNID", "VIR-001", "48", "1.60", "76.80"),
                ("K-0870", "LECHE ENTERA 1LT", "LEC-001", "24", "7.50", "180.00"),
            ],
        ),
        (
            "Fidalga El Prado",
            "FD-30311",
            0,
            [
                ("F-118", "PAÑO MULTIUSO X1", "PAN-001", "60", "3.40", "204.00"),
                ("F-240", "DETERGENTE 1 KG", "DET-001", "20", "16.50", "300.00"),
                ("F-377", "ESPONJA DOBLE USO", None, "30", "2.10", "63.00"),
            ],
        ),
    ]
    creados = []
    for destino, numero, dias, lineas in ejemplos:
        cliente = destinos.get(destino)
        if cliente is None:
            continue
        pdf = _pdf_oc(
            f"ORDEN DE COMPRA {numero}",
            [f"Cliente: {destino}", f"Fecha: {hoy() - timedelta(days=dias)}", ""]
            + [f"{c:<8} {d:<26} {q:>5} x {p:>6} = {t:>8}" for c, d, _, q, p, t in lineas]
            + ["", f"TOTAL Bs {sum(D(t) for *_, t in lineas):.2f}"],
        )
        pedido = pedidos.crear(db, ctx, PedidoCrear(ubicacion_id=sucursal.id))
        pedidos.agregar_documentos(db, ctx, pedido.id, [(pdf, f"OC-{numero}.pdf")])
        pedido = pedidos.guardar_borrador(
            db,
            ctx,
            pedido.id,
            PedidoBorradorEntrada(
                ubicacion_id=sucursal.id,
                cadena_id=cliente.cadena_id,
                sucursal_cliente_id=cliente.id,
                numero_oc=numero,
                fecha_oc=hoy() - timedelta(days=dias),
                total_oc=sum((D(t) for *_, t in lineas), D(0)),
                lineas=[
                    PedidoLineaEntrada(
                        codigo_cliente=c,
                        descripcion_cliente=d,
                        producto_id=productos[s].id if s else None,
                        cantidad_oc=D(q),
                        precio_oc=D(p),
                        total_linea_oc=D(t),
                    )
                    for c, d, s, q, p, t in lineas
                ],
            ),
        )
        creados.append(pedido)

    if len(creados) == 3:
        entregado, confirmado, _ = creados
        entregado = pedidos.confirmar(db, ctx, entregado.id)
        pedidos.alistar(
            db,
            ctx,
            entregado.id,
            AlistarEntrada(
                lineas=[
                    AlistarLineaEntrada(linea_id=x.id, cantidad_alistada=x.cantidad_confirmada)
                    for x in entregado.lineas
                ]
            ),
        )
        pedidos.entregar(
            db,
            ctx,
            entregado.id,
            receptor_nombre="Encargado de recepción",
            observacion=None,
            foto=None,
            firma=None,
        )
        pedidos.confirmar(db, ctx, confirmado.id)
    return True
