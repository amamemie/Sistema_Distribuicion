"""Casos de uso de inventario: transferencias, ajustes y conteos físicos."""

import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import eventos
from app.core.errors import NoEncontrado, ReglaNegocio
from app.core.schemas import Pagina
from app.core.tiempo import ahora
from app.modules.catalogo import servicios as catalogo
from app.modules.catalogo.models import Presentacion, Producto
from app.modules.identidad import auditoria
from app.modules.identidad.contexto import Contexto
from app.modules.inventario import dominio, motor
from app.modules.inventario.models import (
    Ajuste,
    AjusteLinea,
    ConteoFisico,
    ConteoLinea,
    EstadoAjuste,
    EstadoConteo,
    EstadoDocumento,
    Lote,
    MotivoAjuste,
    StockUbicacion,
    TipoMovimiento,
    Transferencia,
    TransferenciaLinea,
)
from app.modules.inventario.schemas import (
    AjusteEntrada,
    AjusteLineaSalida,
    AjusteSalida,
    ConteoEntrada,
    ConteoLineaEntrada,
    ConteoLineaSalida,
    ConteoSalida,
    LineaCantidad,
    LineaDocumentoSalida,
    Referencia,
    TransferenciaEntrada,
    TransferenciaSalida,
)
from app.modules.organizacion import servicios as ubicaciones
from app.modules.organizacion.models import Empresa

CERO = Decimal(0)
UNO = Decimal(1)


@dataclass
class LineaResuelta:
    producto: Producto
    presentacion: Presentacion | None
    factor: Decimal
    cantidad: Decimal
    cantidad_base: Decimal

    @property
    def presentacion_nombre(self) -> str:
        return self.presentacion.nombre if self.presentacion else self.producto.unidad_base


def _resolver(db: Session, ctx: Contexto, linea: LineaCantidad, numero: int) -> LineaResuelta:
    producto = catalogo.producto_operable(db, ctx, linea.producto_id)
    presentacion = catalogo.presentacion_de(producto, linea.presentacion_id)
    factor = presentacion.factor if presentacion else UNO
    cantidad_base = dominio.a_base(linea.cantidad, factor)
    if cantidad_base <= 0:
        raise ReglaNegocio(f"Línea {numero}: la cantidad es demasiado pequeña.")
    return LineaResuelta(producto, presentacion, factor, linea.cantidad, cantidad_base)


# ================================================================ transferencias

ORIGEN_TRANSFERENCIA = "TRANSFERENCIA"


def transferir(db: Session, ctx: Contexto, datos: TransferenciaEntrada) -> Transferencia:
    """Transferencia inmediata (D-13): sale del origen y entra al destino en una transacción."""
    if datos.origen_id == datos.destino_id:
        raise ReglaNegocio("El origen y el destino deben ser distintos.")
    origen = ubicaciones.obtener(db, ctx, datos.origen_id)
    destino = ubicaciones.obtener(db, ctx, datos.destino_id)
    for u in (origen, destino):
        if not u.activo:
            raise ReglaNegocio(f"La ubicación «{u.nombre}» está inactiva.")
    if not (ubicaciones.tiene_acceso(ctx, origen.id) or ubicaciones.tiene_acceso(ctx, destino.id)):
        raise ReglaNegocio("Debe tener acceso al origen o al destino de la transferencia.")

    lineas = [_resolver(db, ctx, linea, i) for i, linea in enumerate(datos.lineas, start=1)]
    transferencia = Transferencia(
        empresa_id=ctx.empresa_id,
        origen_id=origen.id,
        destino_id=destino.id,
        observaciones=datos.observaciones,
        usuario_id=ctx.usuario.id,
    )
    db.add(transferencia)
    db.flush()
    doc = motor.Origen(ORIGEN_TRANSFERENCIA, transferencia.id)

    saldos = motor.bloquear(
        db, ctx, [(u, lr.producto.id) for lr in lineas for u in (origen.id, destino.id)]
    )
    for orden, (lr, entrada) in enumerate(zip(lineas, datos.lineas, strict=True), start=1):
        costo = saldos[(origen.id, lr.producto.id)].cpp
        salidas = motor.salida(
            db,
            ctx,
            tipo=TipoMovimiento.TRANSFERENCIA_SALIDA,
            ubicacion_id=origen.id,
            producto_id=lr.producto.id,
            cantidad=lr.cantidad_base,
            origen=doc,
            lote_id=entrada.lote_id,
            excluir_vencidos=True,
        )
        for mov in salidas:
            lote = db.get(Lote, mov.lote_id)
            assert lote is not None
            motor.entrada(
                db,
                ctx,
                tipo=TipoMovimiento.TRANSFERENCIA_ENTRADA,
                ubicacion_id=destino.id,
                lote=lote,
                cantidad=-mov.cantidad,
                costo_unitario=mov.costo_unitario,
                origen=doc,
            )
        db.add(
            TransferenciaLinea(
                transferencia_id=transferencia.id,
                orden=orden,
                producto_id=lr.producto.id,
                presentacion_id=lr.presentacion.id if lr.presentacion else None,
                presentacion_nombre=lr.presentacion_nombre,
                factor=lr.factor,
                cantidad=lr.cantidad,
                cantidad_base=lr.cantidad_base,
                costo_unitario=costo,
            )
        )
    auditoria.registrar_ctx(
        db,
        ctx,
        accion="transferencia.realizar",
        entidad="transferencia",
        entidad_id=transferencia.id,
        despues={
            "numero": transferencia.numero,
            "origen": origen.nombre,
            "destino": destino.nombre,
            "lineas": len(lineas),
        },
    )
    eventos.publicar(
        db,
        empresa_id=ctx.empresa_id,
        tipo="TransferenciaRealizada",
        agregado="transferencia",
        agregado_id=transferencia.id,
        datos={"origen_id": origen.id, "destino_id": destino.id, "numero": transferencia.numero},
    )
    db.commit()
    db.refresh(transferencia)
    return transferencia


def obtener_transferencia(db: Session, ctx: Contexto, transferencia_id: uuid.UUID) -> Transferencia:
    t = db.get(Transferencia, transferencia_id)
    if t is None or t.empresa_id != ctx.empresa_id:
        raise NoEncontrado("La transferencia no existe.")
    return t


def anular_transferencia(
    db: Session, ctx: Contexto, transferencia_id: uuid.UUID, motivo: str
) -> Transferencia:
    t = obtener_transferencia(db, ctx, transferencia_id)
    if t.estado == EstadoDocumento.ANULADA:
        raise ReglaNegocio("La transferencia ya está anulada.")
    try:
        motor.revertir(db, ctx, motor.Origen(ORIGEN_TRANSFERENCIA, t.id), motivo)
    except ReglaNegocio as error:
        raise ReglaNegocio(
            f"No se puede anular: el destino ya usó parte de la mercadería. {error.detalle}"
        ) from error
    t.estado = EstadoDocumento.ANULADA
    t.anulacion_motivo = motivo
    t.anulado_por_id = ctx.usuario.id
    t.anulado_at = ahora()
    auditoria.registrar_ctx(
        db,
        ctx,
        accion="transferencia.anular",
        entidad="transferencia",
        entidad_id=t.id,
        despues={"motivo": motivo},
    )
    db.commit()
    return t


def listar_transferencias(
    db: Session, ctx: Contexto, ubicacion_id: uuid.UUID | None, pagina: int, tamano: int
) -> Pagina[TransferenciaSalida]:
    filtros = [Transferencia.empresa_id == ctx.empresa_id]
    if ubicacion_id:
        filtros.append(
            (Transferencia.origen_id == ubicacion_id) | (Transferencia.destino_id == ubicacion_id)
        )
    total = db.scalar(select(func.count()).select_from(Transferencia).where(*filtros)) or 0
    items = db.scalars(
        select(Transferencia)
        .where(*filtros)
        .order_by(Transferencia.numero.desc())
        .offset((pagina - 1) * tamano)
        .limit(tamano)
    )
    return Pagina(
        items=[salida_transferencia(t, ctx) for t in items],
        total=total,
        pagina=pagina,
        tamano=tamano,
    )


def salida_transferencia(t: Transferencia, ctx: Contexto) -> TransferenciaSalida:
    ver_costos = ctx.puede("costos.ver")
    return TransferenciaSalida(
        id=t.id,
        numero=t.numero,
        fecha=t.created_at,
        origen=Referencia(id=t.origen.id, nombre=t.origen.nombre),
        destino=Referencia(id=t.destino.id, nombre=t.destino.nombre),
        estado=t.estado,
        observaciones=t.observaciones,
        usuario_nombre=t.usuario.nombre_completo,
        anulacion_motivo=t.anulacion_motivo,
        lineas=[
            LineaDocumentoSalida(
                producto_id=x.producto_id,
                producto_sku=x.producto.sku,
                producto_nombre=x.producto.nombre,
                unidad_base=x.producto.unidad_base,
                presentacion_nombre=x.presentacion_nombre,
                factor=x.factor,
                cantidad=x.cantidad,
                cantidad_base=x.cantidad_base,
                costo_unitario=x.costo_unitario if ver_costos else None,
            )
            for x in t.lineas
        ],
    )


# ================================================================ ajustes

ORIGEN_AJUSTE = "AJUSTE"
_SOLO_DISMINUCION = {MotivoAjuste.MERMA, MotivoAjuste.ROTURA, MotivoAjuste.VENCIMIENTO}


def _umbral_ajuste(db: Session, ctx: Contexto) -> Decimal:
    empresa = db.get(Empresa, ctx.empresa_id)
    valor = (empresa.configuracion if empresa else {}).get("umbral_ajuste_bs", 0)
    return Decimal(str(valor))


def crear_ajuste(db: Session, ctx: Contexto, datos: AjusteEntrada) -> Ajuste:
    """Registra un ajuste. Se aplica de inmediato si quien lo registra puede aprobar ajustes
    (o si su valor no supera el umbral configurado); si no, queda PENDIENTE de aprobación."""
    ubicacion = ubicaciones.operable(db, ctx, datos.ubicacion_id)
    resueltas = [_resolver(db, ctx, linea, i) for i, linea in enumerate(datos.lineas, start=1)]
    saldos = motor.bloquear(db, ctx, [(ubicacion.id, lr.producto.id) for lr in resueltas])

    ajuste = Ajuste(
        empresa_id=ctx.empresa_id,
        ubicacion_id=ubicacion.id,
        motivo=datos.motivo,
        observacion=datos.observacion.strip(),
        estado=EstadoAjuste.PENDIENTE,
        solicitado_por_id=ctx.usuario.id,
    )
    db.add(ajuste)
    db.flush()
    valor_total = CERO
    for orden, (lr, entrada) in enumerate(zip(resueltas, datos.lineas, strict=True), start=1):
        saldo = saldos[(ubicacion.id, lr.producto.id)]
        aumento = entrada.sentido == "AUMENTO"
        if aumento and datos.motivo in _SOLO_DISMINUCION:
            raise ReglaNegocio(
                f"Línea {orden}: el motivo {datos.motivo.value} solo permite disminuir."
            )
        if aumento:
            if lr.producto.controla_vencimiento and not entrada.lote_vencimiento:
                raise ReglaNegocio(
                    f"Línea {orden}: «{lr.producto.nombre}» controla vencimiento; indique la fecha."
                )
            costo = entrada.costo_unitario if entrada.costo_unitario is not None else saldo.cpp
            if entrada.costo_unitario is None and saldo.cpp == 0:
                raise ReglaNegocio(
                    f"Línea {orden}: «{lr.producto.nombre}» no tiene costo registrado en esta "
                    "ubicación; indique el costo unitario."
                )
        else:
            costo = saldo.cpp
            if entrada.lote_id is not None:
                lote = db.get(Lote, entrada.lote_id)
                if lote is None or lote.producto_id != lr.producto.id:
                    raise ReglaNegocio(f"Línea {orden}: el lote no corresponde al producto.")
            disponible = saldo.fisico - saldo.comprometido
            if lr.cantidad_base > disponible:
                raise ReglaNegocio(
                    f"Línea {orden}: solo hay {dominio.formatear_cantidad(disponible)} "
                    f"{lr.producto.unidad_base} disponibles de «{lr.producto.nombre}»."
                )
        signo = UNO if aumento else -UNO
        valor = dominio.redondear(signo * lr.cantidad_base * costo, dominio.Q_DINERO)
        valor_total += valor
        db.add(
            AjusteLinea(
                ajuste_id=ajuste.id,
                orden=orden,
                producto_id=lr.producto.id,
                presentacion_id=lr.presentacion.id if lr.presentacion else None,
                presentacion_nombre=lr.presentacion_nombre,
                factor=lr.factor,
                cantidad=lr.cantidad,
                cantidad_base=signo * lr.cantidad_base,
                lote_id=None if aumento else entrada.lote_id,
                lote_codigo=entrada.lote_codigo if aumento else None,
                lote_vencimiento=entrada.lote_vencimiento if aumento else None,
                costo_unitario=costo,
                valor=valor,
            )
        )
    ajuste.valor_total = valor_total
    db.flush()
    db.refresh(ajuste)

    auditoria.registrar_ctx(
        db,
        ctx,
        accion="ajuste.registrar",
        entidad="ajuste",
        entidad_id=ajuste.id,
        despues={
            "numero": ajuste.numero,
            "ubicacion": ubicacion.nombre,
            "motivo": datos.motivo,
            "valor_estimado": valor_total,
        },
    )
    if ctx.puede("inventario.aprobar_ajuste") or abs(valor_total) <= _umbral_ajuste(db, ctx):
        _aplicar(db, ctx, ajuste)
    db.commit()
    db.refresh(ajuste)
    return ajuste


def _aplicar(db: Session, ctx: Contexto, ajuste: Ajuste) -> None:
    doc = motor.Origen(ORIGEN_AJUSTE, ajuste.id)
    motivo = f"{ajuste.motivo.value}: {ajuste.observacion}"
    saldos = motor.bloquear(db, ctx, [(ajuste.ubicacion_id, x.producto_id) for x in ajuste.lineas])
    total = CERO
    for linea in ajuste.lineas:
        if linea.cantidad_base > 0:
            costo = linea.costo_unitario
            if costo is None:
                costo = saldos[(ajuste.ubicacion_id, linea.producto_id)].cpp
            lote = motor.nuevo_lote(
                db,
                ctx,
                producto_id=linea.producto_id,
                costo_unitario=costo,
                origen=doc,
                codigo=linea.lote_codigo,
                vencimiento=linea.lote_vencimiento,
            )
            motor.entrada(
                db,
                ctx,
                tipo=TipoMovimiento.AJUSTE_POSITIVO,
                ubicacion_id=ajuste.ubicacion_id,
                lote=lote,
                cantidad=linea.cantidad_base,
                costo_unitario=costo,
                origen=doc,
                motivo=motivo,
            )
            linea.costo_unitario = costo
            linea.valor = dominio.redondear(linea.cantidad_base * costo, dominio.Q_DINERO)
        else:
            movimientos = motor.salida(
                db,
                ctx,
                tipo=TipoMovimiento.AJUSTE_NEGATIVO,
                ubicacion_id=ajuste.ubicacion_id,
                producto_id=linea.producto_id,
                cantidad=-linea.cantidad_base,
                origen=doc,
                lote_id=linea.lote_id,
                motivo=motivo,
            )
            linea.costo_unitario = movimientos[0].costo_unitario
            linea.valor = dominio.redondear(
                sum((m.costo_total for m in movimientos), CERO), dominio.Q_DINERO
            )
        total += linea.valor
    ajuste.valor_total = total
    ajuste.estado = EstadoAjuste.APLICADO
    ajuste.resuelto_por_id = ctx.usuario.id
    ajuste.resuelto_at = ahora()
    auditoria.registrar_ctx(
        db,
        ctx,
        accion="ajuste.aplicar",
        entidad="ajuste",
        entidad_id=ajuste.id,
        despues={"numero": ajuste.numero, "valor": total},
    )
    eventos.publicar(
        db,
        empresa_id=ctx.empresa_id,
        tipo="AjusteAplicado",
        agregado="ajuste",
        agregado_id=ajuste.id,
        datos={
            "numero": ajuste.numero,
            "motivo": ajuste.motivo,
            "valor": total,
            "ubicacion_id": ajuste.ubicacion_id,
        },
    )


def obtener_ajuste(db: Session, ctx: Contexto, ajuste_id: uuid.UUID) -> Ajuste:
    ajuste = db.get(Ajuste, ajuste_id)
    if ajuste is None or ajuste.empresa_id != ctx.empresa_id:
        raise NoEncontrado("El ajuste no existe.")
    return ajuste


def aprobar_ajuste(db: Session, ctx: Contexto, ajuste_id: uuid.UUID, nota: str | None) -> Ajuste:
    ajuste = obtener_ajuste(db, ctx, ajuste_id)
    if ajuste.estado != EstadoAjuste.PENDIENTE:
        raise ReglaNegocio("Solo se pueden aprobar ajustes pendientes.")
    ajuste.resolucion_nota = nota
    _aplicar(db, ctx, ajuste)
    db.commit()
    return ajuste


def rechazar_ajuste(db: Session, ctx: Contexto, ajuste_id: uuid.UUID, nota: str | None) -> Ajuste:
    ajuste = obtener_ajuste(db, ctx, ajuste_id)
    if ajuste.estado != EstadoAjuste.PENDIENTE:
        raise ReglaNegocio("Solo se pueden rechazar ajustes pendientes.")
    ajuste.estado = EstadoAjuste.RECHAZADO
    ajuste.resuelto_por_id = ctx.usuario.id
    ajuste.resuelto_at = ahora()
    ajuste.resolucion_nota = nota
    auditoria.registrar_ctx(
        db,
        ctx,
        accion="ajuste.rechazar",
        entidad="ajuste",
        entidad_id=ajuste.id,
        despues={"numero": ajuste.numero, "nota": nota},
    )
    db.commit()
    return ajuste


def listar_ajustes(
    db: Session,
    ctx: Contexto,
    estado: EstadoAjuste | None,
    ubicacion_id: uuid.UUID | None,
    pagina: int,
    tamano: int,
) -> Pagina[AjusteSalida]:
    filtros = [Ajuste.empresa_id == ctx.empresa_id]
    if estado:
        filtros.append(Ajuste.estado == estado)
    if ubicacion_id:
        filtros.append(Ajuste.ubicacion_id == ubicacion_id)
    total = db.scalar(select(func.count()).select_from(Ajuste).where(*filtros)) or 0
    items = db.scalars(
        select(Ajuste)
        .where(*filtros)
        .order_by(Ajuste.numero.desc())
        .offset((pagina - 1) * tamano)
        .limit(tamano)
    )
    return Pagina(
        items=[salida_ajuste(a, ctx) for a in items], total=total, pagina=pagina, tamano=tamano
    )


def salida_ajuste(a: Ajuste, ctx: Contexto) -> AjusteSalida:
    ver = ctx.puede("costos.ver")
    return AjusteSalida(
        id=a.id,
        numero=a.numero,
        fecha=a.created_at,
        ubicacion=Referencia(id=a.ubicacion.id, nombre=a.ubicacion.nombre),
        motivo=a.motivo,
        observacion=a.observacion,
        estado=a.estado,
        valor_total=a.valor_total if ver else None,
        solicitado_por=a.solicitado_por.nombre_completo,
        resuelto_por=a.resuelto_por.nombre_completo if a.resuelto_por else None,
        resuelto_at=a.resuelto_at,
        resolucion_nota=a.resolucion_nota,
        conteo_id=a.conteo_id,
        lineas=[
            AjusteLineaSalida(
                producto_id=x.producto_id,
                producto_sku=x.producto.sku,
                producto_nombre=x.producto.nombre,
                unidad_base=x.producto.unidad_base,
                presentacion_nombre=x.presentacion_nombre,
                factor=x.factor,
                cantidad=x.cantidad,
                cantidad_base=abs(x.cantidad_base),
                sentido="AUMENTO" if x.cantidad_base > 0 else "DISMINUCION",
                lote_codigo=x.lote_codigo,
                lote_vencimiento=x.lote_vencimiento,
                costo_unitario=x.costo_unitario if ver else None,
                valor=x.valor if ver else None,
            )
            for x in a.lineas
        ],
    )


# ================================================================ conteos físicos


def crear_conteo(db: Session, ctx: Contexto, datos: ConteoEntrada) -> ConteoFisico:
    ubicacion = ubicaciones.operable(db, ctx, datos.ubicacion_id)
    conteo = ConteoFisico(
        empresa_id=ctx.empresa_id,
        ubicacion_id=ubicacion.id,
        observaciones=datos.observaciones,
        usuario_id=ctx.usuario.id,
    )
    db.add(conteo)
    db.flush()
    if datos.cargar_productos_con_stock:
        consulta = (
            select(StockUbicacion.producto_id)
            .join(Producto, Producto.id == StockUbicacion.producto_id)
            .where(StockUbicacion.ubicacion_id == ubicacion.id, StockUbicacion.fisico > 0)
        )
        if datos.categoria_id:
            consulta = consulta.where(Producto.categoria_id == datos.categoria_id)
        for producto_id in db.scalars(consulta):
            db.add(ConteoLinea(conteo_id=conteo.id, producto_id=producto_id))
    auditoria.registrar_ctx(
        db,
        ctx,
        accion="conteo.crear",
        entidad="conteo",
        entidad_id=conteo.id,
        despues={"numero": conteo.numero, "ubicacion": ubicacion.nombre},
    )
    db.commit()
    db.refresh(conteo)
    return conteo


def obtener_conteo(db: Session, ctx: Contexto, conteo_id: uuid.UUID) -> ConteoFisico:
    conteo = db.get(ConteoFisico, conteo_id)
    if conteo is None or conteo.empresa_id != ctx.empresa_id:
        raise NoEncontrado("El conteo no existe.")
    return conteo


def _conteo_abierto(db: Session, ctx: Contexto, conteo_id: uuid.UUID) -> ConteoFisico:
    conteo = obtener_conteo(db, ctx, conteo_id)
    if conteo.estado != EstadoConteo.ABIERTO:
        raise ReglaNegocio("El conteo ya no está abierto.")
    return conteo


def guardar_lineas_conteo(
    db: Session, ctx: Contexto, conteo_id: uuid.UUID, lineas: list[ConteoLineaEntrada]
) -> ConteoFisico:
    conteo = _conteo_abierto(db, ctx, conteo_id)
    ubicaciones.operable(db, ctx, conteo.ubicacion_id)
    existentes = {x.producto_id: x for x in conteo.lineas}
    for entrada in lineas:
        catalogo.obtener_producto(db, ctx, entrada.producto_id)
        linea = existentes.get(entrada.producto_id)
        if linea is None:
            linea = ConteoLinea(conteo_id=conteo.id, producto_id=entrada.producto_id)
            db.add(linea)
            existentes[entrada.producto_id] = linea
        linea.cantidad_contada = entrada.cantidad_contada
        linea.vencimiento = entrada.vencimiento
    db.commit()
    db.refresh(conteo)
    return conteo


def aprobar_conteo(db: Session, ctx: Contexto, conteo_id: uuid.UUID) -> ConteoFisico:
    """Compara lo contado con el stock actual y genera un ajuste aplicado por las diferencias."""
    conteo = _conteo_abierto(db, ctx, conteo_id)
    contadas = [x for x in conteo.lineas if x.cantidad_contada is not None]
    if not contadas:
        raise ReglaNegocio("No hay cantidades contadas para aprobar.")
    saldos = motor.bloquear(db, ctx, [(conteo.ubicacion_id, x.producto_id) for x in contadas])
    ajuste = Ajuste(
        empresa_id=ctx.empresa_id,
        ubicacion_id=conteo.ubicacion_id,
        motivo=MotivoAjuste.CONTEO_FISICO,
        observacion=f"Conteo físico #{conteo.numero}",
        estado=EstadoAjuste.PENDIENTE,
        solicitado_por_id=conteo.usuario_id,
        conteo_id=conteo.id,
    )
    lineas_ajuste: list[AjusteLinea] = []
    for linea in contadas:
        saldo = saldos[(conteo.ubicacion_id, linea.producto_id)]
        assert linea.cantidad_contada is not None
        linea.cantidad_sistema = saldo.fisico
        diferencia = linea.cantidad_contada - saldo.fisico
        if diferencia == 0:
            continue
        producto = linea.producto
        if diferencia > 0 and producto.controla_vencimiento and not linea.vencimiento:
            raise ReglaNegocio(
                f"«{producto.nombre}» tiene sobrante y controla vencimiento; indique la fecha."
            )
        if linea.cantidad_contada < saldo.comprometido:
            raise ReglaNegocio(
                f"«{producto.nombre}»: lo contado es menor que lo reservado para pedidos."
            )
        lineas_ajuste.append(
            AjusteLinea(
                orden=len(lineas_ajuste) + 1,
                producto_id=producto.id,
                presentacion_nombre=producto.unidad_base,
                factor=UNO,
                cantidad=abs(diferencia),
                cantidad_base=diferencia,
                lote_vencimiento=linea.vencimiento if diferencia > 0 else None,
                costo_unitario=saldo.cpp if diferencia > 0 else None,
            )
        )
    if lineas_ajuste:
        ajuste.lineas = lineas_ajuste
        db.add(ajuste)
        db.flush()
        db.refresh(ajuste)
        _aplicar(db, ctx, ajuste)
    conteo.estado = EstadoConteo.APROBADO
    conteo.aprobado_por_id = ctx.usuario.id
    conteo.aprobado_at = ahora()
    auditoria.registrar_ctx(
        db,
        ctx,
        accion="conteo.aprobar",
        entidad="conteo",
        entidad_id=conteo.id,
        despues={"numero": conteo.numero, "diferencias": len(lineas_ajuste)},
    )
    db.commit()
    db.refresh(conteo)
    return conteo


def anular_conteo(db: Session, ctx: Contexto, conteo_id: uuid.UUID) -> ConteoFisico:
    conteo = _conteo_abierto(db, ctx, conteo_id)
    conteo.estado = EstadoConteo.ANULADO
    auditoria.registrar_ctx(
        db,
        ctx,
        accion="conteo.anular",
        entidad="conteo",
        entidad_id=conteo.id,
        despues={"numero": conteo.numero},
    )
    db.commit()
    return conteo


def listar_conteos(db: Session, ctx: Contexto, pagina: int, tamano: int) -> Pagina[ConteoSalida]:
    filtros = [ConteoFisico.empresa_id == ctx.empresa_id]
    total = db.scalar(select(func.count()).select_from(ConteoFisico).where(*filtros)) or 0
    items = db.scalars(
        select(ConteoFisico)
        .where(*filtros)
        .order_by(ConteoFisico.numero.desc())
        .offset((pagina - 1) * tamano)
        .limit(tamano)
    )
    return Pagina(
        items=[salida_conteo(db, c, ctx, con_lineas=False) for c in items],
        total=total,
        pagina=pagina,
        tamano=tamano,
    )


def salida_conteo(
    db: Session, c: ConteoFisico, ctx: Contexto, con_lineas: bool = True
) -> ConteoSalida:
    ver = ctx.puede("costos.ver")
    ajuste_id = db.scalar(select(Ajuste.id).where(Ajuste.conteo_id == c.id))
    lineas: list[ConteoLineaSalida] = []
    if con_lineas:
        saldos = {
            s.producto_id: s
            for s in db.scalars(
                select(StockUbicacion).where(StockUbicacion.ubicacion_id == c.ubicacion_id)
            )
        }
        for x in sorted(c.lineas, key=lambda linea: linea.producto.nombre):
            saldo = saldos.get(x.producto_id)
            sistema = (
                x.cantidad_sistema
                if c.estado == EstadoConteo.APROBADO and x.cantidad_sistema is not None
                else (saldo.fisico if saldo else CERO)
            )
            diferencia = None if x.cantidad_contada is None else x.cantidad_contada - sistema
            cpp = saldo.cpp if saldo else CERO
            lineas.append(
                ConteoLineaSalida(
                    producto_id=x.producto_id,
                    producto_sku=x.producto.sku,
                    producto_nombre=x.producto.nombre,
                    unidad_base=x.producto.unidad_base,
                    controla_vencimiento=x.producto.controla_vencimiento,
                    cantidad_sistema=sistema,
                    cantidad_contada=x.cantidad_contada,
                    diferencia=diferencia,
                    vencimiento=x.vencimiento,
                    valor_diferencia=(
                        dominio.redondear(diferencia * cpp, dominio.Q_DINERO)
                        if ver and diferencia is not None
                        else None
                    ),
                )
            )
    return ConteoSalida(
        id=c.id,
        numero=c.numero,
        fecha=c.created_at,
        ubicacion=Referencia(id=c.ubicacion.id, nombre=c.ubicacion.nombre),
        estado=c.estado,
        observaciones=c.observaciones,
        usuario_nombre=c.usuario.nombre_completo,
        aprobado_at=c.aprobado_at,
        ajuste_id=ajuste_id,
        lineas=lineas,
    )
