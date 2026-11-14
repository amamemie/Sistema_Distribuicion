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
