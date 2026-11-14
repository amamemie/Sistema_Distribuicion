import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.schemas import Pagina
from app.modules.compras import servicios
from app.modules.compras.schemas import (
    AnulacionEntrada,
    CompraDetalle,
    CompraEntrada,
    CompraResumen,
    PrecioHistorico,
)
from app.modules.identidad.contexto import Contexto
from app.modules.identidad.dependencias import requiere

router = APIRouter(prefix="/compras", tags=["Compras"])
COMPRAS = requiere("compras.registrar")


@router.get("", response_model=Pagina[CompraResumen])
def listar(
    proveedor_id: uuid.UUID | None = None,
    ubicacion_id: uuid.UUID | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    pagina: int = Query(1, ge=1),
    tamano: int = Query(50, ge=1, le=200),
    ctx: Contexto = Depends(COMPRAS),
    db: Session = Depends(get_db),
) -> Pagina[CompraResumen]:
    return servicios.listar(
        db,
        ctx,
        proveedor_id=proveedor_id,
        ubicacion_id=ubicacion_id,
        desde=desde,
        hasta=hasta,
        pagina=pagina,
        tamano=tamano,
    )


@router.get("/precios", response_model=list[PrecioHistorico])
def historial_precios(
    producto_id: uuid.UUID | None = None,
    proveedor_id: uuid.UUID | None = None,
    ctx: Contexto = Depends(COMPRAS),
    db: Session = Depends(get_db),
) -> list[PrecioHistorico]:
    return servicios.historial_precios(db, ctx, producto_id=producto_id, proveedor_id=proveedor_id)


@router.get("/{compra_id}", response_model=CompraDetalle)
def obtener(
    compra_id: uuid.UUID, ctx: Contexto = Depends(COMPRAS), db: Session = Depends(get_db)
) -> CompraDetalle:
    return servicios.detalle(servicios.obtener(db, ctx, compra_id))


@router.post("", response_model=CompraDetalle, status_code=status.HTTP_201_CREATED)
def registrar(
    datos: CompraEntrada, ctx: Contexto = Depends(COMPRAS), db: Session = Depends(get_db)
) -> CompraDetalle:
    return servicios.detalle(servicios.registrar(db, ctx, datos))


@router.post("/{compra_id}/anular", response_model=CompraDetalle)
def anular(
    compra_id: uuid.UUID,
    datos: AnulacionEntrada,
    ctx: Contexto = Depends(COMPRAS),
    db: Session = Depends(get_db),
) -> CompraDetalle:
    return servicios.detalle(servicios.anular(db, ctx, compra_id, datos.motivo))
