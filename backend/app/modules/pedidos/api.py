import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.schemas import Pagina
from app.modules.documentos import servicios as documentos
from app.modules.identidad.contexto import Contexto
from app.modules.identidad.dependencias import requiere, requiere_alguno
from app.modules.pedidos import servicios
from app.modules.pedidos.models import EstadoPedido
from app.modules.pedidos.schemas import (
    AlistarEntrada,
    AnularEntrada,
    DevolucionEntrada,
    PedidoBorradorEntrada,
    PedidoCrear,
    PedidoDetalle,
    PedidoResumen,
    Sugerencia,
)

router = APIRouter(prefix="/pedidos", tags=["Pedidos"])
VER = requiere_alguno(
    "pedidos.escanear",
    "pedidos.confirmar",
    "pedidos.alistar",
    "pedidos.entregar",
    "pedidos.anular",
    "pedidos.ver_todos",
)
ESCANEAR = requiere("pedidos.escanear")


def _subidas(archivos: list[UploadFile]) -> list[tuple[bytes, str | None]]:
    return [(documentos.leer_subida(a), a.filename) for a in archivos]


@router.get("", response_model=Pagina[PedidoResumen])
def listar(
    estado: EstadoPedido | None = None,
    cadena_id: uuid.UUID | None = None,
    ubicacion_id: uuid.UUID | None = None,
    buscar: str | None = Query(None, max_length=60),
    desde: date | None = None,
    hasta: date | None = None,
    pagina: int = Query(1, ge=1),
    tamano: int = Query(50, ge=1, le=200),
    ctx: Contexto = Depends(VER),
    db: Session = Depends(get_db),
) -> Pagina[PedidoResumen]:
    return servicios.listar(
        db,
        ctx,
        estado=estado,
        cadena_id=cadena_id,
        ubicacion_id=ubicacion_id,
        buscar=buscar,
        desde=desde,
        hasta=hasta,
        pagina=pagina,
        tamano=tamano,
    )


@router.post("", response_model=PedidoDetalle, status_code=status.HTTP_201_CREATED)
def crear(
    datos: PedidoCrear, ctx: Contexto = Depends(ESCANEAR), db: Session = Depends(get_db)
) -> PedidoDetalle:
    return servicios.detalle(db, ctx, servicios.crear(db, ctx, datos))


@router.get("/emparejar", response_model=list[Sugerencia])
def emparejar(
    cadena_id: uuid.UUID | None = None,
    codigo: str | None = Query(None, max_length=60),
    descripcion: str | None = Query(None, max_length=300),
    ctx: Contexto = Depends(ESCANEAR),
    db: Session = Depends(get_db),
) -> list[Sugerencia]:
    return servicios.sugerencias(
        db, ctx, cadena_id=cadena_id, codigo=codigo, descripcion=descripcion
    )


@router.get("/{pedido_id}", response_model=PedidoDetalle)
def obtener(
    pedido_id: uuid.UUID, ctx: Contexto = Depends(VER), db: Session = Depends(get_db)
) -> PedidoDetalle:
    return servicios.detalle(db, ctx, servicios.obtener(db, ctx, pedido_id))


@router.put("/{pedido_id}", response_model=PedidoDetalle)
def guardar_borrador(
    pedido_id: uuid.UUID,
    datos: PedidoBorradorEntrada,
    ctx: Contexto = Depends(ESCANEAR),
    db: Session = Depends(get_db),
) -> PedidoDetalle:
    return servicios.detalle(db, ctx, servicios.guardar_borrador(db, ctx, pedido_id, datos))


@router.post("/{pedido_id}/documentos", response_model=PedidoDetalle)
def agregar_documentos(
    pedido_id: uuid.UUID,
    archivos: list[UploadFile] = File(...),
    ctx: Contexto = Depends(ESCANEAR),
    db: Session = Depends(get_db),
) -> PedidoDetalle:
    pedido = servicios.agregar_documentos(db, ctx, pedido_id, _subidas(archivos))
    return servicios.detalle(db, ctx, pedido)


@router.delete("/{pedido_id}/documentos/{archivo_id}", response_model=PedidoDetalle)
def quitar_documento(
    pedido_id: uuid.UUID,
    archivo_id: uuid.UUID,
    ctx: Contexto = Depends(ESCANEAR),
    db: Session = Depends(get_db),
) -> PedidoDetalle:
    pedido = servicios.quitar_documento(db, ctx, pedido_id, archivo_id)
    return servicios.detalle(db, ctx, pedido)


@router.get("/{pedido_id}/archivos/{archivo_id}", response_class=FileResponse)
def descargar_archivo(
    pedido_id: uuid.UUID,
    archivo_id: uuid.UUID,
    ctx: Contexto = Depends(VER),
    db: Session = Depends(get_db),
) -> FileResponse:
    archivo = servicios.archivo_de_pedido(db, ctx, pedido_id, archivo_id)
    return FileResponse(
        documentos.ruta_absoluta(archivo),
        media_type=archivo.tipo_mime,
        filename=archivo.nombre_original,
        content_disposition_type="inline",
        headers={"Cache-Control": "private, max-age=86400", "X-Content-Type-Options": "nosniff"},
    )


@router.post("/{pedido_id}/confirmar", response_model=PedidoDetalle)
def confirmar(
    pedido_id: uuid.UUID,
    ctx: Contexto = Depends(requiere("pedidos.confirmar")),
    db: Session = Depends(get_db),
) -> PedidoDetalle:
    return servicios.detalle(db, ctx, servicios.confirmar(db, ctx, pedido_id))


@router.post("/{pedido_id}/alistar", response_model=PedidoDetalle)
def alistar(
    pedido_id: uuid.UUID,
    datos: AlistarEntrada,
    ctx: Contexto = Depends(requiere("pedidos.alistar")),
    db: Session = Depends(get_db),
) -> PedidoDetalle:
    return servicios.detalle(db, ctx, servicios.alistar(db, ctx, pedido_id, datos))


@router.post("/{pedido_id}/entregar", response_model=PedidoDetalle)
def entregar(
    pedido_id: uuid.UUID,
    receptor_nombre: str | None = Form(None, max_length=120),
    observacion: str | None = Form(None, max_length=500),
    foto: UploadFile | None = File(None),
    firma: UploadFile | None = File(None),
    ctx: Contexto = Depends(requiere("pedidos.entregar")),
    db: Session = Depends(get_db),
) -> PedidoDetalle:
    pedido = servicios.entregar(
        db,
        ctx,
        pedido_id,
        receptor_nombre=receptor_nombre,
        observacion=observacion,
        foto=_subidas([foto])[0] if foto else None,
        firma=_subidas([firma])[0] if firma else None,
    )
    return servicios.detalle(db, ctx, pedido)


@router.post("/{pedido_id}/anular", response_model=PedidoDetalle)
def anular(
    pedido_id: uuid.UUID,
    datos: AnularEntrada,
    ctx: Contexto = Depends(VER),
    db: Session = Depends(get_db),
) -> PedidoDetalle:
    return servicios.detalle(db, ctx, servicios.anular(db, ctx, pedido_id, datos.motivo))


@router.post("/{pedido_id}/devoluciones", response_model=PedidoDetalle)
def devolver(
    pedido_id: uuid.UUID,
    datos: DevolucionEntrada,
    ctx: Contexto = Depends(requiere("pedidos.anular")),
    db: Session = Depends(get_db),
) -> PedidoDetalle:
    return servicios.detalle(db, ctx, servicios.devolver(db, ctx, pedido_id, datos))
