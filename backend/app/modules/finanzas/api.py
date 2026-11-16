import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.schemas import Pagina
from app.modules.compras import servicios as compras
from app.modules.compras.schemas import CompraResumen
from app.modules.documentos import servicios as documentos
from app.modules.finanzas import parametros, servicios
from app.modules.finanzas.parametros import ParametrosFinanzas
from app.modules.finanzas.schemas import (
    AjusteSaldoEntrada,
    AnulacionEntrada,
    CategoriaGastoEntrada,
    CategoriaGastoSalida,
    CierreSaldoEntrada,
    CobroDetalleCompleto,
    CobroEntrada,
    CobroResumen,
    CompraPorPagar,
    GastoEntrada,
    GastoSalida,
    ImpuestoMes,
    PaginaGastos,
    PagoCompraEntrada,
    PorCobrar,
)
from app.modules.identidad.contexto import Contexto
from app.modules.identidad.dependencias import requiere

router = APIRouter(prefix="/finanzas", tags=["Finanzas"])
VER = requiere("finanzas.ver")
COBROS = requiere("finanzas.cobros")
GASTOS = requiere("finanzas.gastos")
CONFIGURAR = requiere("configuracion.gestionar")


# ================================================================ por cobrar y cobros


@router.get("/por-cobrar", response_model=PorCobrar)
def por_cobrar(
    cadena_id: uuid.UUID | None = None,
    todas: bool = False,
    ctx: Contexto = Depends(VER),
    db: Session = Depends(get_db),
) -> PorCobrar:
    return servicios.por_cobrar(db, ctx, cadena_id=cadena_id, todas=todas)


@router.post(
    "/por-cobrar/{pedido_id}/cerrar",
    response_model=CobroDetalleCompleto,
    status_code=status.HTTP_201_CREATED,
)
def cerrar_saldo(
    pedido_id: uuid.UUID,
    datos: CierreSaldoEntrada,
    ctx: Contexto = Depends(COBROS),
    db: Session = Depends(get_db),
) -> CobroDetalleCompleto:
    return servicios.cobro_detalle(db, servicios.cerrar_saldo(db, ctx, pedido_id, datos.motivo))


@router.post(
    "/por-cobrar/cadenas/{cadena_id}/ajustar",
    response_model=CobroDetalleCompleto,
    status_code=status.HTTP_201_CREATED,
)
def ajustar_saldo(
    cadena_id: uuid.UUID,
    datos: AjusteSaldoEntrada,
    ctx: Contexto = Depends(COBROS),
    db: Session = Depends(get_db),
) -> CobroDetalleCompleto:
    cobro = servicios.ajustar_saldo(db, ctx, cadena_id, datos.monto, datos.motivo)
    return servicios.cobro_detalle(db, cobro)


@router.get("/cobros", response_model=Pagina[CobroResumen])
def listar_cobros(
    cadena_id: uuid.UUID | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    pagina: int = Query(1, ge=1),
    tamano: int = Query(30, ge=1, le=200),
    ctx: Contexto = Depends(VER),
    db: Session = Depends(get_db),
) -> Pagina[CobroResumen]:
    items, total = servicios.listar_cobros(
        db, ctx, cadena_id=cadena_id, desde=desde, hasta=hasta, pagina=pagina, tamano=tamano
    )
    return Pagina(items=items, total=total, pagina=pagina, tamano=tamano)


@router.get("/cobros/{cobro_id}", response_model=CobroDetalleCompleto)
def obtener_cobro(
    cobro_id: uuid.UUID, ctx: Contexto = Depends(VER), db: Session = Depends(get_db)
) -> CobroDetalleCompleto:
    return servicios.cobro_detalle(db, servicios.obtener_cobro(db, ctx, cobro_id))


@router.post("/cobros", response_model=CobroDetalleCompleto, status_code=status.HTTP_201_CREATED)
def registrar_cobro(
    datos: CobroEntrada, ctx: Contexto = Depends(COBROS), db: Session = Depends(get_db)
) -> CobroDetalleCompleto:
    return servicios.cobro_detalle(db, servicios.registrar_cobro(db, ctx, datos))


@router.post("/cobros/{cobro_id}/anular", response_model=CobroDetalleCompleto)
def anular_cobro(
    cobro_id: uuid.UUID,
    datos: AnulacionEntrada,
    ctx: Contexto = Depends(COBROS),
    db: Session = Depends(get_db),
) -> CobroDetalleCompleto:
    return servicios.cobro_detalle(db, servicios.anular_cobro(db, ctx, cobro_id, datos.motivo))


@router.post("/cobros/{cobro_id}/comprobante", response_model=CobroDetalleCompleto)
def comprobante_cobro(
    cobro_id: uuid.UUID,
    archivo: UploadFile = File(...),
    ctx: Contexto = Depends(COBROS),
    db: Session = Depends(get_db),
) -> CobroDetalleCompleto:
    cobro = servicios.adjuntar_comprobante_cobro(
        db, ctx, cobro_id, documentos.leer_subida(archivo), archivo.filename
    )
    return servicios.cobro_detalle(db, cobro)


@router.get("/comprobantes/{archivo_id}", response_class=FileResponse)
def descargar_comprobante(
    archivo_id: uuid.UUID, ctx: Contexto = Depends(VER), db: Session = Depends(get_db)
) -> FileResponse:
    archivo = servicios.archivo_de(db, ctx, archivo_id)
    return FileResponse(
        documentos.ruta_absoluta(archivo),
        media_type=archivo.tipo_mime,
        filename=archivo.nombre_original,
        content_disposition_type="inline",
        headers={"Cache-Control": "private, max-age=86400", "X-Content-Type-Options": "nosniff"},
    )


# ================================================================ gastos


@router.get("/categorias-gasto", response_model=list[CategoriaGastoSalida])
def listar_categorias(
    ctx: Contexto = Depends(VER), db: Session = Depends(get_db)
) -> list[CategoriaGastoSalida]:
    return servicios.listar_categorias(db, ctx)


@router.post(
    "/categorias-gasto", response_model=CategoriaGastoSalida, status_code=status.HTTP_201_CREATED
)
def crear_categoria(
    datos: CategoriaGastoEntrada, ctx: Contexto = Depends(GASTOS), db: Session = Depends(get_db)
) -> CategoriaGastoSalida:
    return servicios.crear_categoria(db, ctx, datos)


@router.put("/categorias-gasto/{categoria_id}", response_model=CategoriaGastoSalida)
def editar_categoria(
    categoria_id: uuid.UUID,
    datos: CategoriaGastoEntrada,
    ctx: Contexto = Depends(GASTOS),
    db: Session = Depends(get_db),
) -> CategoriaGastoSalida:
    return servicios.editar_categoria(db, ctx, categoria_id, datos)


@router.get("/gastos", response_model=PaginaGastos)
def listar_gastos(
    desde: date | None = None,
    hasta: date | None = None,
    categoria_id: uuid.UUID | None = None,
    ubicacion_id: uuid.UUID | None = None,
    buscar: str | None = Query(None, max_length=100),
    pagina: int = Query(1, ge=1),
    tamano: int = Query(30, ge=1, le=200),
    ctx: Contexto = Depends(VER),
    db: Session = Depends(get_db),
) -> PaginaGastos:
    return servicios.listar_gastos(
        db,
        ctx,
        desde=desde,
        hasta=hasta,
        categoria_id=categoria_id,
        ubicacion_id=ubicacion_id,
        buscar=buscar,
        pagina=pagina,
        tamano=tamano,
    )


@router.post("/gastos", response_model=GastoSalida, status_code=status.HTTP_201_CREATED)
def registrar_gasto(
    datos: GastoEntrada, ctx: Contexto = Depends(GASTOS), db: Session = Depends(get_db)
) -> GastoSalida:
    return servicios.gasto_salida(servicios.registrar_gasto(db, ctx, datos))


@router.post("/gastos/{gasto_id}/anular", response_model=GastoSalida)
def anular_gasto(
    gasto_id: uuid.UUID,
    datos: AnulacionEntrada,
    ctx: Contexto = Depends(GASTOS),
    db: Session = Depends(get_db),
) -> GastoSalida:
    return servicios.gasto_salida(servicios.anular_gasto(db, ctx, gasto_id, datos.motivo))


@router.post("/gastos/{gasto_id}/comprobante", response_model=GastoSalida)
def comprobante_gasto(
    gasto_id: uuid.UUID,
    archivo: UploadFile = File(...),
    ctx: Contexto = Depends(GASTOS),
    db: Session = Depends(get_db),
) -> GastoSalida:
    gasto = servicios.adjuntar_comprobante_gasto(
        db, ctx, gasto_id, documentos.leer_subida(archivo), archivo.filename
    )
    return servicios.gasto_salida(gasto)


# ================================================================ por pagar


@router.get("/por-pagar", response_model=list[CompraPorPagar])
def por_pagar(ctx: Contexto = Depends(VER), db: Session = Depends(get_db)) -> list[CompraPorPagar]:
    return servicios.por_pagar(db, ctx)


@router.post("/compras/{compra_id}/pagar", response_model=CompraResumen)
def pagar_compra(
    compra_id: uuid.UUID,
    datos: PagoCompraEntrada,
    ctx: Contexto = Depends(GASTOS),
    db: Session = Depends(get_db),
) -> CompraResumen:
    return compras.resumen(servicios.pagar_compra(db, ctx, compra_id, datos.fecha))


# ================================================================ impuestos y parámetros


@router.get("/impuestos", response_model=list[ImpuestoMes])
def impuestos(
    desde: date,
    hasta: date,
    ctx: Contexto = Depends(VER),
    db: Session = Depends(get_db),
) -> list[ImpuestoMes]:
    return servicios.impuestos_mensuales(db, ctx, desde, hasta)


@router.get("/parametros", response_model=ParametrosFinanzas)
def ver_parametros(
    ctx: Contexto = Depends(VER), db: Session = Depends(get_db)
) -> ParametrosFinanzas:
    return parametros.leer(db, ctx.empresa_id)


@router.put("/parametros", response_model=ParametrosFinanzas)
def guardar_parametros(
    datos: ParametrosFinanzas, ctx: Contexto = Depends(CONFIGURAR), db: Session = Depends(get_db)
) -> ParametrosFinanzas:
    return servicios.guardar_parametros(db, ctx, datos)
