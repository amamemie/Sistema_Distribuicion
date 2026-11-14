import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.clientes import servicios
from app.modules.clientes.models import Cadena, SucursalCliente
from app.modules.clientes.schemas import (
    CadenaActualizacion,
    CadenaEntrada,
    CadenaSalida,
    SucursalClienteActualizacion,
    SucursalClienteEntrada,
    SucursalClienteSalida,
)
from app.modules.identidad.contexto import Contexto
from app.modules.identidad.dependencias import requiere, usuario_actual

router = APIRouter(tags=["Clientes"])
GESTIONAR = requiere("clientes.gestionar")


@router.get("/cadenas", response_model=list[CadenaSalida])
def listar(ctx: Contexto = Depends(usuario_actual), db: Session = Depends(get_db)) -> list[Cadena]:
    return servicios.listar(db, ctx)


@router.post("/cadenas", response_model=CadenaSalida, status_code=status.HTTP_201_CREATED)
def crear(
    datos: CadenaEntrada, ctx: Contexto = Depends(GESTIONAR), db: Session = Depends(get_db)
) -> Cadena:
    return servicios.crear(db, ctx, datos)


@router.patch("/cadenas/{cadena_id}", response_model=CadenaSalida)
def actualizar(
    cadena_id: uuid.UUID,
    datos: CadenaActualizacion,
    ctx: Contexto = Depends(GESTIONAR),
    db: Session = Depends(get_db),
) -> Cadena:
    return servicios.actualizar(db, ctx, cadena_id, datos)


@router.post(
    "/cadenas/{cadena_id}/sucursales",
    response_model=SucursalClienteSalida,
    status_code=status.HTTP_201_CREATED,
)
def crear_sucursal(
    cadena_id: uuid.UUID,
    datos: SucursalClienteEntrada,
    ctx: Contexto = Depends(GESTIONAR),
    db: Session = Depends(get_db),
) -> SucursalCliente:
    return servicios.crear_sucursal(db, ctx, cadena_id, datos)


@router.patch("/sucursales-cliente/{sucursal_id}", response_model=SucursalClienteSalida)
def actualizar_sucursal(
    sucursal_id: uuid.UUID,
    datos: SucursalClienteActualizacion,
    ctx: Contexto = Depends(GESTIONAR),
    db: Session = Depends(get_db),
) -> SucursalCliente:
    return servicios.actualizar_sucursal(db, ctx, sucursal_id, datos)
