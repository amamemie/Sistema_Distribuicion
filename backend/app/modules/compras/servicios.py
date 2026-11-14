import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import eventos
from app.core.errors import NoEncontrado, ReglaNegocio
from app.core.schemas import Pagina
from app.core.tiempo import ahora, hoy
from app.modules.catalogo import servicios as catalogo
from app.modules.compras.models import Compra, CompraCosto, CompraLinea, EstadoCompra
from app.modules.compras.schemas import (
    CompraCostoSalida,
    CompraDetalle,
    CompraEntrada,
    CompraLineaSalida,
    CompraResumen,
    PrecioHistorico,
    Referencia,
)
from app.modules.identidad import auditoria
from app.modules.identidad.contexto import Contexto
from app.modules.inventario import dominio, motor
from app.modules.inventario.models import TipoMovimiento
from app.modules.organizacion import servicios as ubicaciones
from app.modules.proveedores import servicios as proveedores

ORIGEN = "COMPRA"


def registrar(db: Session, ctx: Contexto, datos: CompraEntrada) -> Compra:
    """Registra la compra y su ingreso al inventario en una sola transacción."""
    proveedor = proveedores.operable(db, ctx, datos.proveedor_id)
    ubicacion = ubicaciones.operable(db, ctx, datos.ubicacion_id)
    if datos.fecha > hoy():
        raise ReglaNegocio("La fecha de la compra no puede ser futura.")

    # 1. Validar y calcular cada línea (sin tocar todavía el inventario).
    calculos = []
    for i, linea in enumerate(datos.lineas, start=1):
        producto = catalogo.producto_operable(db, ctx, linea.producto_id)
        presentacion = catalogo.presentacion_de(producto, linea.presentacion_id)
        factor = presentacion.factor if presentacion else Decimal(1)
        if producto.controla_vencimiento and not (linea.lote_codigo and linea.lote_vencimiento):
            raise ReglaNegocio(
                f"Línea {i}: «{producto.nombre}» controla vencimiento; indique el lote y su "
                "fecha de vencimiento."
            )
        cantidad_base = dominio.a_base(linea.cantidad, factor)
        if cantidad_base <= 0:
            raise ReglaNegocio(f"Línea {i}: la cantidad es demasiado pequeña.")
        subtotal = dominio.redondear(linea.cantidad * linea.precio_presentacion, dominio.Q_DINERO)
        calculos.append((linea, producto, presentacion, factor, cantidad_base, subtotal))

    costos_adicionales = sum((c.monto for c in datos.costos), Decimal(0))
    prorrateos = dominio.prorratear([c[5] for c in calculos], costos_adicionales)
    subtotal_compra = sum((c[5] for c in calculos), Decimal(0))

    compra = Compra(
        empresa_id=ctx.empresa_id,
        proveedor_id=proveedor.id,
        ubicacion_id=ubicacion.id,
        fecha=datos.fecha,
        numero_documento=datos.numero_documento,
        subtotal=subtotal_compra,
        costos_adicionales=costos_adicionales,
        total=subtotal_compra + costos_adicionales,
        observaciones=datos.observaciones,
        usuario_id=ctx.usuario.id,
        costos=[CompraCosto(concepto=c.concepto.strip(), monto=c.monto) for c in datos.costos],
    )
    db.add(compra)
    db.flush()
    origen = motor.Origen(ORIGEN, compra.id)

    # 2. Ingresar al inventario (con bloqueo de los saldos involucrados).
    motor.bloquear(db, ctx, ((ubicacion.id, c[1].id) for c in calculos))
    for orden, (
        (linea, producto, presentacion, factor, cantidad_base, subtotal),
        prorrateo,
    ) in enumerate(zip(calculos, prorrateos, strict=True), start=1):
        costo_unitario = dominio.redondear((subtotal + prorrateo) / cantidad_base, dominio.Q_COSTO)
        lote = motor.nuevo_lote(
            db,
            ctx,
            producto_id=producto.id,
            costo_unitario=costo_unitario,
            origen=origen,
            codigo=linea.lote_codigo,
            vencimiento=linea.lote_vencimiento,
            proveedor_id=proveedor.id,
        )
        db.add(
            CompraLinea(
                compra_id=compra.id,
                orden=orden,
                producto_id=producto.id,
                presentacion_id=presentacion.id if presentacion else None,
                presentacion_nombre=presentacion.nombre if presentacion else producto.unidad_base,
                factor=factor,
                cantidad=linea.cantidad,
                precio_presentacion=linea.precio_presentacion,
                subtotal=subtotal,
                prorrateo=prorrateo,
                cantidad_base=cantidad_base,
                costo_unitario_base=costo_unitario,
                lote_id=lote.id,
            )
        )
        motor.entrada(
            db,
            ctx,
            tipo=TipoMovimiento.COMPRA,
            ubicacion_id=ubicacion.id,
            lote=lote,
            cantidad=cantidad_base,
            costo_unitario=costo_unitario,
            origen=origen,
        )

    auditoria.registrar_ctx(
        db,
        ctx,
        accion="compra.registrar",
        entidad="compra",
        entidad_id=compra.id,
        despues={
            "numero": compra.numero,
            "proveedor": proveedor.nombre,
            "ubicacion": ubicacion.nombre,
            "total": compra.total,
            "lineas": len(calculos),
        },
    )
    eventos.publicar(
        db,
        empresa_id=ctx.empresa_id,
        tipo="CompraRegistrada",
        agregado="compra",
        agregado_id=compra.id,
        datos={"numero": compra.numero, "ubicacion_id": ubicacion.id, "total": compra.total},
    )
    db.commit()
    db.refresh(compra)
    return compra


def obtener(db: Session, ctx: Contexto, compra_id: uuid.UUID) -> Compra:
    compra = db.get(Compra, compra_id)
    if compra is None or compra.empresa_id != ctx.empresa_id:
        raise NoEncontrado("La compra no existe.")
    return compra


def anular(db: Session, ctx: Contexto, compra_id: uuid.UUID, motivo: str) -> Compra:
    compra = obtener(db, ctx, compra_id)
    if compra.estado == EstadoCompra.ANULADA:
        raise ReglaNegocio("La compra ya está anulada.")
    ubicaciones.operable(db, ctx, compra.ubicacion_id)
    try:
        motor.revertir(db, ctx, motor.Origen(ORIGEN, compra.id), motivo)
    except ReglaNegocio as error:
        raise ReglaNegocio(
            "No se puede anular: parte de lo comprado ya salió de la ubicación (se transfirió o "
            f"vendió). {error.detalle}"
        ) from error
    compra.estado = EstadoCompra.ANULADA
    compra.anulacion_motivo = motivo
    compra.anulado_por_id = ctx.usuario.id
    compra.anulado_at = ahora()
    auditoria.registrar_ctx(
        db,
        ctx,
        accion="compra.anular",
        entidad="compra",
        entidad_id=compra.id,
        antes={"estado": EstadoCompra.REGISTRADA},
        despues={"estado": compra.estado, "motivo": motivo},
    )
    eventos.publicar(
        db,
        empresa_id=ctx.empresa_id,
        tipo="CompraAnulada",
        agregado="compra",
        agregado_id=compra.id,
        datos={"numero": compra.numero},
    )
    db.commit()
    return compra


def listar(
    db: Session,
    ctx: Contexto,
    *,
    proveedor_id: uuid.UUID | None,
    ubicacion_id: uuid.UUID | None,
    desde: date | None,
    hasta: date | None,
    pagina: int,
    tamano: int,
) -> Pagina[CompraResumen]:
    filtros = [Compra.empresa_id == ctx.empresa_id]
    if proveedor_id:
        filtros.append(Compra.proveedor_id == proveedor_id)
    if ubicacion_id:
        filtros.append(Compra.ubicacion_id == ubicacion_id)
    if desde:
        filtros.append(Compra.fecha >= desde)
    if hasta:
        filtros.append(Compra.fecha <= hasta)
    total = db.scalar(select(func.count()).select_from(Compra).where(*filtros)) or 0
    compras = db.scalars(
        select(Compra)
        .where(*filtros)
        .order_by(Compra.fecha.desc(), Compra.numero.desc())
        .offset((pagina - 1) * tamano)
        .limit(tamano)
    )
    return Pagina(items=[resumen(c) for c in compras], total=total, pagina=pagina, tamano=tamano)


def resumen(c: Compra) -> CompraResumen:
    return CompraResumen(
        id=c.id,
        numero=c.numero,
        fecha=c.fecha,
        numero_documento=c.numero_documento,
        proveedor=Referencia(id=c.proveedor.id, nombre=c.proveedor.nombre),
        ubicacion=Referencia(id=c.ubicacion.id, nombre=c.ubicacion.nombre),
        estado=c.estado,
        total=c.total,
        usuario_nombre=c.usuario.nombre_completo,
        created_at=c.created_at,
    )


def detalle(c: Compra) -> CompraDetalle:
    return CompraDetalle(
        **resumen(c).model_dump(),
        subtotal=c.subtotal,
        costos_adicionales=c.costos_adicionales,
        observaciones=c.observaciones,
        anulacion_motivo=c.anulacion_motivo,
        anulado_at=c.anulado_at,
        costos=[CompraCostoSalida.model_validate(x) for x in c.costos],
        lineas=[
            CompraLineaSalida(
                producto_id=linea.producto_id,
                producto_sku=linea.producto.sku,
                producto_nombre=linea.producto.nombre,
                unidad_base=linea.producto.unidad_base,
                presentacion_nombre=linea.presentacion_nombre,
                factor=linea.factor,
                cantidad=linea.cantidad,
                precio_presentacion=linea.precio_presentacion,
                subtotal=linea.subtotal,
                prorrateo=linea.prorrateo,
                cantidad_base=linea.cantidad_base,
                costo_unitario_base=linea.costo_unitario_base,
                lote_codigo=linea.lote.codigo,
                lote_vencimiento=linea.lote.vencimiento,
            )
            for linea in c.lineas
        ],
    )


def historial_precios(
    db: Session,
    ctx: Contexto,
    *,
    producto_id: uuid.UUID | None,
    proveedor_id: uuid.UUID | None,
    limite: int = 200,
) -> list[PrecioHistorico]:
    consulta = (
        select(CompraLinea, Compra)
        .join(Compra, Compra.id == CompraLinea.compra_id)
        .where(Compra.empresa_id == ctx.empresa_id, Compra.estado == EstadoCompra.REGISTRADA)
        .order_by(Compra.fecha.desc(), Compra.numero.desc())
        .limit(limite)
    )
    if producto_id:
        consulta = consulta.where(CompraLinea.producto_id == producto_id)
    if proveedor_id:
        consulta = consulta.where(Compra.proveedor_id == proveedor_id)
    return [
        PrecioHistorico(
            fecha=compra.fecha,
            compra_numero=compra.numero,
            proveedor=Referencia(id=compra.proveedor.id, nombre=compra.proveedor.nombre),
            producto_id=linea.producto_id,
            producto_nombre=linea.producto.nombre,
            presentacion_nombre=linea.presentacion_nombre,
            precio_presentacion=linea.precio_presentacion,
            costo_unitario_base=linea.costo_unitario_base,
        )
        for linea, compra in db.execute(consulta)
    ]
