from datetime import datetime
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import NoEncontrado
from app.core.tiempo import hoy
from app.modules.identidad.contexto import Contexto
from app.modules.identidad.dependencias import requiere_alguno
from app.modules.reportes import exportar
from app.modules.reportes.consultas import REPORTES
from app.modules.reportes.schemas import Filtros, Reporte

router = APIRouter(prefix="/reportes", tags=["Reportes"])
VER = requiere_alguno("reportes.operativos", "reportes.rentabilidad")
TIPOS = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
}


def _generar(clave: str, db: Session, ctx: Contexto, filtros: Filtros) -> Reporte:
    funcion = REPORTES.get(clave)
    if funcion is None:
        raise NoEncontrado("Ese reporte no existe.")
    return funcion(db, ctx, filtros)


@router.get("/{clave}", response_model=Reporte)
def ver(
    clave: str,
    filtros: Annotated[Filtros, Query()],
    ctx: Contexto = Depends(VER),
    db: Session = Depends(get_db),
) -> Reporte:
    return _generar(clave, db, ctx, filtros)


@router.get("/{clave}/exportar")
def exportar_reporte(
    clave: str,
    filtros: Annotated[Filtros, Query()],
    formato: Literal["xlsx", "pdf"] = "xlsx",
    ctx: Contexto = Depends(VER),
    db: Session = Depends(get_db),
) -> Response:
    reporte = _generar(clave, db, ctx, filtros)
    ahora = datetime.now(ZoneInfo(get_settings().zona_horaria))
    if formato == "xlsx":
        contenido = exportar.excel(reporte)
    else:
        contenido = exportar.pdf(
            reporte, f"Generado el {ahora:%d/%m/%Y %H:%M} por {ctx.usuario.nombre}"
        )
    nombre = exportar.nombre_archivo(reporte, formato, hoy())
    return Response(
        content=contenido,
        media_type=TIPOS[formato],
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )
