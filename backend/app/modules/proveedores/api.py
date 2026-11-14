import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.identidad.contexto import Contexto
from app.modules.identidad.dependencias import requiere, usuario_actual
from app.modules.proveedores import servicios
from app.modules.proveedores.models import Proveedor
from app.modules.proveedores.schemas import (
    ProveedorActualizacion,
    ProveedorEntrada,
    ProveedorSalida,
)

router = APIRouter(prefix="/proveedores", tags=["Proveedores"])


@router.get("", response_model=list[ProveedorSalida])
def listar(
    ctx: Contexto = Depends(usuario_actual), db: Session = Depends(get_db)
) -> list[Proveedor]:
    return servicios.listar(db, ctx)


@router.post("", response_model=ProveedorSalida, status_code=status.HTTP_201_CREATED)
def crear(
    datos: ProveedorEntrada,
    ctx: Contexto = Depends(requiere("proveedores.gestionar")),
    db: Session = Depends(get_db),
) -> Proveedor:
    return servicios.crear(db, ctx, datos)


@router.patch("/{proveedor_id}", response_model=ProveedorSalida)
def actualizar(
    proveedor_id: uuid.UUID,
    datos: ProveedorActualizacion,
    ctx: Contexto = Depends(requiere("proveedores.gestionar")),
    db: Session = Depends(get_db),
) -> Proveedor:
    return servicios.actualizar(db, ctx, proveedor_id, datos)
