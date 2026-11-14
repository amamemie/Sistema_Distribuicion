"""Ayudantes para crear datos de catálogo en las pruebas."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.modules.catalogo import servicios as catalogo
from app.modules.catalogo.models import Categoria, Producto
from app.modules.catalogo.schemas import NombreEntrada, PresentacionEntrada, ProductoEntrada
from app.modules.compras import servicios as compras
from app.modules.compras.models import Compra
from app.modules.compras.schemas import CompraCostoEntrada, CompraEntrada, CompraLineaEntrada
from app.modules.identidad.contexto import Contexto
from app.modules.proveedores import servicios as proveedores
from app.modules.proveedores.models import Proveedor
from app.modules.proveedores.schemas import ProveedorEntrada


@dataclass
class Catalogo:
    categoria: Categoria
    guantes: Producto  # fardo de 300, caja de 600
    leche: Producto  # controla vencimiento, caja de 12
    proveedor: Proveedor


def crear_catalogo(db: Session, ctx: Contexto) -> Catalogo:
    categoria = catalogo.crear_simple(db, ctx, Categoria, NombreEntrada(nombre="Limpieza"))
    guantes = catalogo.crear_producto(
        db,
        ctx,
        ProductoEntrada(
            sku="GUA-001",
            nombre="Guante de látex",
            categoria_id=categoria.id,
            presentaciones=[
                PresentacionEntrada(nombre="Fardo", factor=Decimal(300)),
                PresentacionEntrada(nombre="Caja", factor=Decimal(600)),
            ],
        ),
    )
    leche = catalogo.crear_producto(
        db,
        ctx,
        ProductoEntrada(
            sku="LEC-001",
            nombre="Leche entera 1L",
            categoria_id=categoria.id,
            controla_vencimiento=True,
            presentaciones=[PresentacionEntrada(nombre="Caja", factor=Decimal(12))],
        ),
    )
    proveedor = proveedores.crear(db, ctx, ProveedorEntrada(nombre="Proveedor Andino"))
    return Catalogo(categoria, guantes, leche, proveedor)


def presentacion(producto: Producto, nombre: str) -> str:
    return str(next(p.id for p in producto.presentaciones if p.nombre == nombre))


def comprar(
    db: Session,
    ctx: Contexto,
    cat: Catalogo,
    ubicacion_id: object,
    lineas: list[CompraLineaEntrada],
    costos: list[CompraCostoEntrada] | None = None,
) -> Compra:
    return compras.registrar(
        db,
        ctx,
        CompraEntrada(
            proveedor_id=cat.proveedor.id,
            ubicacion_id=ubicacion_id,
            fecha=date(2026, 11, 1),
            lineas=lineas,
            costos=costos or [],
        ),
    )
