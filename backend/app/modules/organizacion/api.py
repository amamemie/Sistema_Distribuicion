import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.identidad.contexto import Contexto
from app.modules.identidad.dependencias import requiere, usuario_actual
from app.modules.organizacion import servicios
from app.modules.organizacion.models import Ubicacion
from app.modules.organizacion.schemas import (
    UbicacionActualizacion,
    UbicacionEntrada,
    UbicacionSalida,
)

router = APIRouter(prefix="/ubicaciones", tags=["Ubicaciones"])


@router.get("", response_model=list[UbicacionSalida])
def listar(
    solo_activas: bool = False,
    ctx: Contexto = Depends(usuario_actual),
    db: Session = Depends(get_db),
) -> list[Ubicacion]:
    return servicios.listar(db, ctx, solo_activas)


@router.post("", response_model=UbicacionSalida, status_code=status.HTTP_201_CREATED)
def crear(
    datos: UbicacionEntrada,
    ctx: Contexto = Depends(requiere("ubicaciones.gestionar")),
    db: Session = Depends(get_db),
) -> Ubicacion:
    return servicios.crear(db, ctx, datos)


@router.patch("/{ubicacion_id}", response_model=UbicacionSalida)
def actualizar(
    ubicacion_id: uuid.UUID,
    datos: UbicacionActualizacion,
    ctx: Contexto = Depends(requiere("ubicaciones.gestionar")),
    db: Session = Depends(get_db),
) -> Ubicacion:
    return servicios.actualizar(db, ctx, ubicacion_id, datos)
