import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.schemas import Pagina
from app.modules.alertas import servicios
from app.modules.alertas.models import EstadoAlerta, Severidad
from app.modules.alertas.parametros import Parametros
from app.modules.alertas.schemas import (
    AlertaSalida,
    FilaReposicion,
    MarcarLeidas,
    PronosticoSalida,
    ResultadoEvaluacion,
    ResumenAlertas,
    SugerenciaCompraSalida,
    SugerenciaTransferenciaSalida,
)
from app.modules.identidad.contexto import Contexto
from app.modules.identidad.dependencias import requiere, requiere_alguno, usuario_actual

router = APIRouter(tags=["Alertas y reposición"])
REPOSICION = requiere_alguno("inventario.transferir", "compras.registrar")
CONFIGURAR = requiere("configuracion.gestionar")


@router.get("/alertas", response_model=Pagina[AlertaSalida])
def listar(
    estado: EstadoAlerta | None = EstadoAlerta.ACTIVA,
    severidad: Severidad | None = None,
    tipo: str | None = Query(None, max_length=40),
    solo_no_leidas: bool = False,
    pagina: int = Query(1, ge=1),
    tamano: int = Query(30, ge=1, le=100),
    ctx: Contexto = Depends(usuario_actual),
    db: Session = Depends(get_db),
) -> Pagina[AlertaSalida]:
    return servicios.listar(
        db,
        ctx,
        estado=estado,
        severidad=severidad,
        tipo=tipo,
        solo_no_leidas=solo_no_leidas,
        pagina=pagina,
        tamano=tamano,
    )


@router.get("/alertas/resumen", response_model=ResumenAlertas)
def resumen(
    ctx: Contexto = Depends(usuario_actual), db: Session = Depends(get_db)
) -> ResumenAlertas:
    return servicios.resumen(db, ctx)


@router.post("/alertas/leidas")
def marcar_leidas(
    datos: MarcarLeidas, ctx: Contexto = Depends(usuario_actual), db: Session = Depends(get_db)
) -> dict[str, int]:
    return {"marcadas": servicios.marcar_leidas(db, ctx, datos.ids)}


@router.post("/alertas/{alerta_id}/atender", status_code=status.HTTP_204_NO_CONTENT)
def atender(
    alerta_id: uuid.UUID, ctx: Contexto = Depends(usuario_actual), db: Session = Depends(get_db)
) -> None:
    servicios.atender(db, ctx, alerta_id)


@router.post("/alertas/evaluar", response_model=ResultadoEvaluacion)
def evaluar(
    recalcular_pronostico: bool = False,
    ctx: Contexto = Depends(requiere_alguno("inventario.ver", "configuracion.gestionar")),
    db: Session = Depends(get_db),
) -> ResultadoEvaluacion:
    return servicios.evaluar_ahora(db, ctx, recalcular_pronostico=recalcular_pronostico)


@router.get("/alertas/parametros", response_model=Parametros)
def leer_parametros(
    ctx: Contexto = Depends(
        requiere_alguno("configuracion.gestionar", "inventario.transferir", "compras.registrar")
    ),
    db: Session = Depends(get_db),
) -> Parametros:
    return servicios.leer_parametros(db, ctx)


@router.put("/alertas/parametros", response_model=Parametros)
def guardar_parametros(
    datos: Parametros, ctx: Contexto = Depends(CONFIGURAR), db: Session = Depends(get_db)
) -> Parametros:
    return servicios.guardar_parametros(db, ctx, datos)


@router.get("/reposicion/transferencias", response_model=list[SugerenciaTransferenciaSalida])
def transferencias(
    ctx: Contexto = Depends(requiere("inventario.transferir")), db: Session = Depends(get_db)
) -> list[SugerenciaTransferenciaSalida]:
    return servicios.transferencias(db, ctx)


@router.get("/reposicion/compras", response_model=list[SugerenciaCompraSalida])
def compras(
    ctx: Contexto = Depends(requiere("compras.registrar")), db: Session = Depends(get_db)
) -> list[SugerenciaCompraSalida]:
    return servicios.compras(db, ctx)


@router.get("/reposicion/plan", response_model=list[FilaReposicion])
def plan(
    ctx: Contexto = Depends(REPOSICION), db: Session = Depends(get_db)
) -> list[FilaReposicion]:
    return servicios.plan_completo(db, ctx)


@router.get("/reposicion/pronostico/{producto_id}", response_model=list[PronosticoSalida])
def pronostico(
    producto_id: uuid.UUID, ctx: Contexto = Depends(REPOSICION), db: Session = Depends(get_db)
) -> list[PronosticoSalida]:
    return servicios.pronostico_de(db, ctx, producto_id)
