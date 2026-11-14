import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.schemas import Pagina
from app.modules.identidad.contexto import Contexto
from app.modules.identidad.dependencias import requiere
from app.modules.inventario import consultas, servicios
from app.modules.inventario.models import EstadoAjuste
from app.modules.inventario.schemas import (
    AjusteEntrada,
    AjusteSalida,
    AnulacionEntrada,
    ConteoEntrada,
    ConteoLineaEntrada,
    ConteoSalida,
    LoteEnStock,
    MovimientoKardex,
    ResolucionEntrada,
    ResultadoVerificacion,
    StockProducto,
    TransferenciaEntrada,
    TransferenciaSalida,
)

router = APIRouter(tags=["Inventario"])
VER = requiere("inventario.ver")
TRANSFERIR = requiere("inventario.transferir")
AJUSTAR = requiere("inventario.ajustar")
APROBAR = requiere("inventario.aprobar_ajuste")


# ---------------------------------------------------------------- consultas


@router.get("/inventario/stock", response_model=Pagina[StockProducto])
def stock(
    ubicacion_id: uuid.UUID | None = None,
    buscar: str | None = None,
    categoria_id: uuid.UUID | None = None,
    solo_con_stock: bool = False,
    pagina: int = Query(1, ge=1),
    tamano: int = Query(50, ge=1, le=200),
    ctx: Contexto = Depends(VER),
    db: Session = Depends(get_db),
) -> Pagina[StockProducto]:
    return consultas.stock(
        db,
        ctx,
        ubicacion_id=ubicacion_id,
        buscar=buscar,
        categoria_id=categoria_id,
        solo_con_stock=solo_con_stock,
        pagina=pagina,
        tamano=tamano,
    )


@router.get("/inventario/lotes", response_model=list[LoteEnStock])
def lotes(
    producto_id: uuid.UUID,
    ubicacion_id: uuid.UUID | None = None,
    ctx: Contexto = Depends(VER),
    db: Session = Depends(get_db),
) -> list[LoteEnStock]:
    return consultas.lotes(db, ctx, producto_id, ubicacion_id)


@router.get("/inventario/kardex", response_model=Pagina[MovimientoKardex])
def kardex(
    producto_id: uuid.UUID,
    ubicacion_id: uuid.UUID | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    pagina: int = Query(1, ge=1),
    tamano: int = Query(100, ge=1, le=500),
    ctx: Contexto = Depends(VER),
    db: Session = Depends(get_db),
) -> Pagina[MovimientoKardex]:
    return consultas.kardex(
        db,
        ctx,
        producto_id=producto_id,
        ubicacion_id=ubicacion_id,
        desde=desde,
        hasta=hasta,
        pagina=pagina,
        tamano=tamano,
    )


@router.get("/inventario/verificacion", response_model=ResultadoVerificacion)
def verificar(
    ctx: Contexto = Depends(APROBAR), db: Session = Depends(get_db)
) -> ResultadoVerificacion:
    return consultas.verificar(db, ctx)


# ---------------------------------------------------------------- transferencias


@router.get("/transferencias", response_model=Pagina[TransferenciaSalida])
def listar_transferencias(
    ubicacion_id: uuid.UUID | None = None,
    pagina: int = Query(1, ge=1),
    tamano: int = Query(50, ge=1, le=200),
    ctx: Contexto = Depends(VER),
    db: Session = Depends(get_db),
) -> Pagina[TransferenciaSalida]:
    return servicios.listar_transferencias(db, ctx, ubicacion_id, pagina, tamano)


@router.get("/transferencias/{transferencia_id}", response_model=TransferenciaSalida)
def obtener_transferencia(
    transferencia_id: uuid.UUID, ctx: Contexto = Depends(VER), db: Session = Depends(get_db)
) -> TransferenciaSalida:
    return servicios.salida_transferencia(
        servicios.obtener_transferencia(db, ctx, transferencia_id), ctx
    )


@router.post(
    "/transferencias", response_model=TransferenciaSalida, status_code=status.HTTP_201_CREATED
)
def transferir(
    datos: TransferenciaEntrada, ctx: Contexto = Depends(TRANSFERIR), db: Session = Depends(get_db)
) -> TransferenciaSalida:
    return servicios.salida_transferencia(servicios.transferir(db, ctx, datos), ctx)


@router.post("/transferencias/{transferencia_id}/anular", response_model=TransferenciaSalida)
def anular_transferencia(
    transferencia_id: uuid.UUID,
    datos: AnulacionEntrada,
    ctx: Contexto = Depends(TRANSFERIR),
    db: Session = Depends(get_db),
) -> TransferenciaSalida:
    t = servicios.anular_transferencia(db, ctx, transferencia_id, datos.motivo)
    return servicios.salida_transferencia(t, ctx)


# ---------------------------------------------------------------- ajustes


@router.get("/ajustes", response_model=Pagina[AjusteSalida])
def listar_ajustes(
    estado: EstadoAjuste | None = None,
    ubicacion_id: uuid.UUID | None = None,
    pagina: int = Query(1, ge=1),
    tamano: int = Query(50, ge=1, le=200),
    ctx: Contexto = Depends(VER),
    db: Session = Depends(get_db),
) -> Pagina[AjusteSalida]:
    return servicios.listar_ajustes(db, ctx, estado, ubicacion_id, pagina, tamano)


@router.get("/ajustes/{ajuste_id}", response_model=AjusteSalida)
def obtener_ajuste(
    ajuste_id: uuid.UUID, ctx: Contexto = Depends(VER), db: Session = Depends(get_db)
) -> AjusteSalida:
    return servicios.salida_ajuste(servicios.obtener_ajuste(db, ctx, ajuste_id), ctx)


@router.post("/ajustes", response_model=AjusteSalida, status_code=status.HTTP_201_CREATED)
def crear_ajuste(
    datos: AjusteEntrada, ctx: Contexto = Depends(AJUSTAR), db: Session = Depends(get_db)
) -> AjusteSalida:
    return servicios.salida_ajuste(servicios.crear_ajuste(db, ctx, datos), ctx)


@router.post("/ajustes/{ajuste_id}/aprobar", response_model=AjusteSalida)
def aprobar_ajuste(
    ajuste_id: uuid.UUID,
    datos: ResolucionEntrada,
    ctx: Contexto = Depends(APROBAR),
    db: Session = Depends(get_db),
) -> AjusteSalida:
    return servicios.salida_ajuste(servicios.aprobar_ajuste(db, ctx, ajuste_id, datos.nota), ctx)


@router.post("/ajustes/{ajuste_id}/rechazar", response_model=AjusteSalida)
def rechazar_ajuste(
    ajuste_id: uuid.UUID,
    datos: ResolucionEntrada,
    ctx: Contexto = Depends(APROBAR),
    db: Session = Depends(get_db),
) -> AjusteSalida:
    return servicios.salida_ajuste(servicios.rechazar_ajuste(db, ctx, ajuste_id, datos.nota), ctx)


# ---------------------------------------------------------------- conteos


@router.get("/conteos", response_model=Pagina[ConteoSalida])
def listar_conteos(
    pagina: int = Query(1, ge=1),
    tamano: int = Query(50, ge=1, le=200),
    ctx: Contexto = Depends(VER),
    db: Session = Depends(get_db),
) -> Pagina[ConteoSalida]:
    return servicios.listar_conteos(db, ctx, pagina, tamano)


@router.get("/conteos/{conteo_id}", response_model=ConteoSalida)
def obtener_conteo(
    conteo_id: uuid.UUID, ctx: Contexto = Depends(VER), db: Session = Depends(get_db)
) -> ConteoSalida:
    return servicios.salida_conteo(db, servicios.obtener_conteo(db, ctx, conteo_id), ctx)


@router.post("/conteos", response_model=ConteoSalida, status_code=status.HTTP_201_CREATED)
def crear_conteo(
    datos: ConteoEntrada, ctx: Contexto = Depends(AJUSTAR), db: Session = Depends(get_db)
) -> ConteoSalida:
    return servicios.salida_conteo(db, servicios.crear_conteo(db, ctx, datos), ctx)


@router.put("/conteos/{conteo_id}/lineas", response_model=ConteoSalida)
def guardar_lineas(
    conteo_id: uuid.UUID,
    lineas: list[ConteoLineaEntrada],
    ctx: Contexto = Depends(AJUSTAR),
    db: Session = Depends(get_db),
) -> ConteoSalida:
    conteo = servicios.guardar_lineas_conteo(db, ctx, conteo_id, lineas)
    return servicios.salida_conteo(db, conteo, ctx)


@router.post("/conteos/{conteo_id}/aprobar", response_model=ConteoSalida)
def aprobar_conteo(
    conteo_id: uuid.UUID, ctx: Contexto = Depends(APROBAR), db: Session = Depends(get_db)
) -> ConteoSalida:
    return servicios.salida_conteo(db, servicios.aprobar_conteo(db, ctx, conteo_id), ctx)


@router.post("/conteos/{conteo_id}/anular", response_model=ConteoSalida)
def anular_conteo(
    conteo_id: uuid.UUID, ctx: Contexto = Depends(AJUSTAR), db: Session = Depends(get_db)
) -> ConteoSalida:
    return servicios.salida_conteo(db, servicios.anular_conteo(db, ctx, conteo_id), ctx)
