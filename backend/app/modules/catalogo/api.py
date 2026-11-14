import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.schemas import Pagina
from app.modules.catalogo import servicios
from app.modules.catalogo.models import Categoria, Marca, Presentacion
from app.modules.catalogo.schemas import (
    CategoriaSalida,
    LimiteEntrada,
    LimiteSalida,
    MarcaSalida,
    NombreActualizacion,
    NombreEntrada,
    PresentacionActualizacion,
    PresentacionEntrada,
    PresentacionSalida,
    ProductoActualizacion,
    ProductoDetalle,
    ProductoEntrada,
    ProductoSalida,
)
from app.modules.identidad.contexto import Contexto
from app.modules.identidad.dependencias import requiere

router = APIRouter(tags=["Catálogo"])
VER = requiere("catalogo.ver")
GESTIONAR = requiere("catalogo.gestionar")


@router.get("/categorias", response_model=list[CategoriaSalida])
def listar_categorias(
    ctx: Contexto = Depends(VER), db: Session = Depends(get_db)
) -> list[Categoria]:
    return servicios.listar_simples(db, ctx, Categoria)


@router.post("/categorias", response_model=CategoriaSalida, status_code=status.HTTP_201_CREATED)
def crear_categoria(
    datos: NombreEntrada, ctx: Contexto = Depends(GESTIONAR), db: Session = Depends(get_db)
) -> Categoria:
    return servicios.crear_simple(db, ctx, Categoria, datos)


@router.patch("/categorias/{categoria_id}", response_model=CategoriaSalida)
def actualizar_categoria(
    categoria_id: uuid.UUID,
    datos: NombreActualizacion,
    ctx: Contexto = Depends(GESTIONAR),
    db: Session = Depends(get_db),
) -> Categoria:
    return servicios.actualizar_simple(db, ctx, Categoria, categoria_id, datos)


@router.get("/marcas", response_model=list[MarcaSalida])
def listar_marcas(ctx: Contexto = Depends(VER), db: Session = Depends(get_db)) -> list[Marca]:
    return servicios.listar_simples(db, ctx, Marca)


@router.post("/marcas", response_model=MarcaSalida, status_code=status.HTTP_201_CREATED)
def crear_marca(
    datos: NombreEntrada, ctx: Contexto = Depends(GESTIONAR), db: Session = Depends(get_db)
) -> Marca:
    return servicios.crear_simple(db, ctx, Marca, datos)


@router.patch("/marcas/{marca_id}", response_model=MarcaSalida)
def actualizar_marca(
    marca_id: uuid.UUID,
    datos: NombreActualizacion,
    ctx: Contexto = Depends(GESTIONAR),
    db: Session = Depends(get_db),
) -> Marca:
    return servicios.actualizar_simple(db, ctx, Marca, marca_id, datos)


@router.get("/productos", response_model=Pagina[ProductoSalida])
def listar_productos(
    buscar: str | None = None,
    categoria_id: uuid.UUID | None = None,
    activo: bool | None = None,
    pagina: int = Query(1, ge=1),
    tamano: int = Query(50, ge=1, le=200),
    ctx: Contexto = Depends(VER),
    db: Session = Depends(get_db),
) -> Pagina[ProductoSalida]:
    items, total = servicios.listar_productos(
        db,
        ctx,
        buscar=buscar,
        categoria_id=categoria_id,
        activo=activo,
        pagina=pagina,
        tamano=tamano,
    )
    return Pagina(
        items=[ProductoSalida.model_validate(p) for p in items],
        total=total,
        pagina=pagina,
        tamano=tamano,
    )


def _detalle(db: Session, producto_id: uuid.UUID, ctx: Contexto) -> ProductoDetalle:
    producto = servicios.obtener_producto(db, ctx, producto_id)
    base = ProductoSalida.model_validate(producto).model_dump()
    limites = [LimiteSalida.model_validate(lim) for lim in servicios.limites_de(db, producto.id)]
    return ProductoDetalle(**base, limites=limites)


@router.get("/productos/{producto_id}", response_model=ProductoDetalle)
def obtener_producto(
    producto_id: uuid.UUID, ctx: Contexto = Depends(VER), db: Session = Depends(get_db)
) -> ProductoDetalle:
    return _detalle(db, producto_id, ctx)


@router.post("/productos", response_model=ProductoDetalle, status_code=status.HTTP_201_CREATED)
def crear_producto(
    datos: ProductoEntrada, ctx: Contexto = Depends(GESTIONAR), db: Session = Depends(get_db)
) -> ProductoDetalle:
    producto = servicios.crear_producto(db, ctx, datos)
    return _detalle(db, producto.id, ctx)


@router.patch("/productos/{producto_id}", response_model=ProductoDetalle)
def actualizar_producto(
    producto_id: uuid.UUID,
    datos: ProductoActualizacion,
    ctx: Contexto = Depends(GESTIONAR),
    db: Session = Depends(get_db),
) -> ProductoDetalle:
    servicios.actualizar_producto(db, ctx, producto_id, datos)
    return _detalle(db, producto_id, ctx)


@router.post(
    "/productos/{producto_id}/presentaciones",
    response_model=PresentacionSalida,
    status_code=status.HTTP_201_CREATED,
)
def agregar_presentacion(
    producto_id: uuid.UUID,
    datos: PresentacionEntrada,
    ctx: Contexto = Depends(GESTIONAR),
    db: Session = Depends(get_db),
) -> Presentacion:
    return servicios.agregar_presentacion(db, ctx, producto_id, datos)


@router.patch("/presentaciones/{presentacion_id}", response_model=PresentacionSalida)
def actualizar_presentacion(
    presentacion_id: uuid.UUID,
    datos: PresentacionActualizacion,
    ctx: Contexto = Depends(GESTIONAR),
    db: Session = Depends(get_db),
) -> Presentacion:
    return servicios.actualizar_presentacion(db, ctx, presentacion_id, datos)


@router.put("/productos/{producto_id}/limites", response_model=list[LimiteSalida])
def guardar_limites(
    producto_id: uuid.UUID,
    limites: list[LimiteEntrada],
    ctx: Contexto = Depends(GESTIONAR),
    db: Session = Depends(get_db),
) -> list[LimiteSalida]:
    return [
        LimiteSalida.model_validate(lim)
        for lim in servicios.guardar_limites(db, ctx, producto_id, limites)
    ]
