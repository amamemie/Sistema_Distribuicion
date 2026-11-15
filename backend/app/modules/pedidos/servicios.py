"""Casos de uso de pedidos de supermercado.

Estados (3.4): BORRADOR → CONFIRMADO → ALISTADO → ENTREGADO | ANULADO.

- BORRADOR: se adjunta la OC (fotos/PDF) y se cargan o corrigen sus datos. No toca el stock.
- CONFIRMADO: reserva el stock vigente de la sucursal (sube el comprometido).
- ALISTADO: libera la reserva, descuenta el stock físico (FEFO o lotes elegidos), congela el
  costo y calcula la ganancia. Lo encontrado en mal estado se registra como merma (D-11).
- ENTREGADO: no mueve stock; guarda la constancia de recepción.
- ANULADO: libera la reserva o revierte el alistado. Un pedido entregado no se anula (D-03);
  las devoluciones posteriores se registran aparte (D-12).
"""

import uuid
from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import eventos
from app.core.errors import Conflicto, NoEncontrado, ReglaNegocio, SinPermiso
from app.core.schemas import Pagina
from app.core.tiempo import ahora, hoy
from app.modules.catalogo import servicios as catalogo
from app.modules.catalogo.models import Producto
from app.modules.catalogo.schemas import ProductoSalida
from app.modules.clientes.models import Cadena, SucursalCliente
from app.modules.documentos import servicios as documentos
from app.modules.documentos.models import Archivo
from app.modules.identidad import auditoria
from app.modules.identidad.contexto import Contexto
from app.modules.inventario import dominio as dominio_inv
from app.modules.inventario import motor
from app.modules.inventario import servicios as inventario
from app.modules.inventario.models import (
    Ajuste,
    Lote,
    MotivoAjuste,
    StockLote,
    StockUbicacion,
    TipoMovimiento,
)
from app.modules.inventario.schemas import AjusteEntrada, AjusteLineaEntrada
from app.modules.organizacion import servicios as ubicaciones
from app.modules.organizacion.models import TipoUbicacion, Ubicacion
from app.modules.pedidos import dominio, lectura
from app.modules.pedidos.models import (
    Devolucion,
    DevolucionLinea,
    Equivalencia,
    EstadoLectura,
    EstadoPedido,
    Lectura,
    Pedido,
    PedidoDocumento,
    PedidoEvento,
    PedidoLinea,
    PedidoLineaLote,
)
from app.modules.pedidos.schemas import (
    AjusteRef,
    AlistarEntrada,
    AlistarLineaEntrada,
    DevolucionEntrada,
    DevolucionLineaSalida,
    DevolucionSalida,
    DocumentoSalida,
    EventoSalida,
    LecturaSalida,
    LoteSalida,
    PedidoBorradorEntrada,
    PedidoCrear,
    PedidoDetalle,
    PedidoLineaSalida,
    PedidoResumen,
    PrecisionLectura,
    Referencia,
    Sugerencia,
    Validacion,
)

ORIGEN = "PEDIDO"
ORIGEN_DEVOLUCION = "DEVOLUCION"
MAX_DOCUMENTOS = 20
CERO = Decimal(0)


# ================================================================ utilidades


def _evento(
    db: Session, ctx: Contexto, pedido: Pedido, tipo: str, detalle: dict[str, Any] | None = None
) -> None:
    from fastapi.encoders import jsonable_encoder

    db.add(
        PedidoEvento(
            pedido_id=pedido.id,
            tipo=tipo,
            usuario_id=ctx.usuario.id,
            detalle=jsonable_encoder(detalle) if detalle else None,
        )
    )


def obtener(db: Session, ctx: Contexto, pedido_id: uuid.UUID) -> Pedido:
    pedido = db.get(Pedido, pedido_id)
    if pedido is None or pedido.empresa_id != ctx.empresa_id:
        raise NoEncontrado("El pedido no existe.")
    # D-05: quien escanea es responsable; los demás pedidos requieren permiso.
    if pedido.responsable_id != ctx.usuario.id and not ctx.puede("pedidos.ver_todos"):
        raise NoEncontrado("El pedido no existe.")
    return pedido


def _bloqueado(db: Session, ctx: Contexto, pedido_id: uuid.UUID) -> Pedido:
    """Obtiene el pedido bloqueando su fila: dos personas no cambian su estado a la vez."""
    obtener(db, ctx, pedido_id)
    return db.scalars(
        select(Pedido)
        .where(Pedido.id == pedido_id)
        .with_for_update(of=Pedido)
        .execution_options(populate_existing=True)
    ).one()


def _exigir_estado(pedido: Pedido, *estados: EstadoPedido) -> None:
    if pedido.estado not in estados:
        raise ReglaNegocio(
            f"El pedido #{pedido.numero} está {pedido.estado.value.lower()}; esta acción no "
            "corresponde en ese estado."
        )


def _sucursal_despacho(db: Session, ctx: Contexto, ubicacion_id: uuid.UUID) -> Ubicacion:
    ubicacion = ubicaciones.operable(db, ctx, ubicacion_id)
    if ubicacion.tipo != TipoUbicacion.SUCURSAL:
        raise ReglaNegocio(
            f"«{ubicacion.nombre}» es un depósito: los pedidos se despachan desde una sucursal."
        )
    return ubicacion


def _lineas_activas(pedido: Pedido) -> list[PedidoLinea]:
    return [x for x in pedido.lineas if x.cantidad_confirmada > 0]


def _documentos_activos(pedido: Pedido) -> list[PedidoDocumento]:
    return [d for d in pedido.documentos if d.activo]


def _duplicado(
    db: Session,
    ctx: Contexto,
    pedido: Pedido,
    *,
    cadena_id: uuid.UUID | None = None,
    numero_oc: str | None = None,
) -> Pedido | None:
    """Otro pedido vigente con la misma OC de la misma cadena (por defecto, la del pedido)."""
    cadena_id = cadena_id or pedido.cadena_id
    numero_oc = numero_oc or pedido.numero_oc
    if not (cadena_id and numero_oc):
        return None
    return db.scalars(
        select(Pedido).where(
            Pedido.empresa_id == ctx.empresa_id,
            Pedido.cadena_id == cadena_id,
            func.upper(Pedido.numero_oc) == numero_oc.upper(),
            Pedido.estado != EstadoPedido.ANULADO,
            Pedido.id != pedido.id,
        )
    ).first()


def _mensaje_duplicado(otro: Pedido) -> str:
    return (
        f"La OC {otro.numero_oc} de {otro.cadena.nombre if otro.cadena else 'esta cadena'} ya "
        f"está registrada en el pedido #{otro.numero} ({otro.estado.value.lower()})."
    )


def _commit(db: Session) -> None:
    """Commit que traduce la violación del índice de OC duplicadas en un mensaje claro."""
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        if "uq_pedido_oc_vigente" in str(error.orig):
            raise Conflicto("Esa OC ya está registrada para la misma cadena.") from error
        raise


# ================================================================ borrador


def crear(db: Session, ctx: Contexto, datos: PedidoCrear) -> Pedido:
    ubicacion = _sucursal_despacho(db, ctx, datos.ubicacion_id)
    pedido = Pedido(
        empresa_id=ctx.empresa_id,
        ubicacion_id=ubicacion.id,
        observaciones=datos.observaciones,
        responsable_id=ctx.usuario.id,
    )
    db.add(pedido)
    db.flush()
    _evento(db, ctx, pedido, "CREADO", {"ubicacion": ubicacion.nombre})
    auditoria.registrar_ctx(
        db,
        ctx,
        accion="pedido.crear",
        entidad="pedido",
        entidad_id=pedido.id,
        despues={"numero": pedido.numero, "ubicacion": ubicacion.nombre},
    )
    db.commit()
    db.refresh(pedido)
    return pedido


def agregar_documentos(
    db: Session, ctx: Contexto, pedido_id: uuid.UUID, archivos: list[tuple[bytes, str | None]]
) -> Pedido:
    pedido = _bloqueado(db, ctx, pedido_id)
    _exigir_estado(pedido, EstadoPedido.BORRADOR)
    if not archivos:
        raise ReglaNegocio("Adjunte al menos una foto o PDF de la nota de recepción.")
    if len(_documentos_activos(pedido)) + len(archivos) > MAX_DOCUMENTOS:
        raise ReglaNegocio(f"Un pedido admite como máximo {MAX_DOCUMENTOS} archivos.")
    orden = max((d.orden for d in pedido.documentos), default=0)
    nombres = []
    for contenido, nombre in archivos:
        archivo = documentos.guardar(db, ctx, contenido, nombre)
        orden += 1
        db.add(PedidoDocumento(pedido_id=pedido.id, archivo_id=archivo.id, orden=orden))
        nombres.append(archivo.nombre_original)
    _evento(db, ctx, pedido, "DOCUMENTO_AGREGADO", {"archivos": nombres})
    auditoria.registrar_ctx(
        db,
        ctx,
        accion="pedido.agregar_documento",
        entidad="pedido",
        entidad_id=pedido.id,
        despues={"archivos": nombres},
    )
    nueva = (
        lectura.solicitar(db, ctx, pedido, reemplazar=False)
        if lectura.debe_leer_al_subir(db, pedido)
        else None
    )
    db.commit()
    if nueva:
        lectura.encolar(nueva.id)
    db.refresh(pedido)
    return pedido


def leer(db: Session, ctx: Contexto, pedido_id: uuid.UUID) -> Pedido:
    """Vuelve a leer el documento automáticamente; reemplaza lo cargado en el borrador."""
    pedido = _bloqueado(db, ctx, pedido_id)
    _exigir_estado(pedido, EstadoPedido.BORRADOR)
    if not _documentos_activos(pedido):
        raise ReglaNegocio("Adjunte primero la nota de recepción (foto o PDF).")
    nueva = lectura.solicitar(db, ctx, pedido, reemplazar=True)
    _evento(db, ctx, pedido, "LECTURA_SOLICITADA")
    db.commit()
    if nueva:
        lectura.encolar(nueva.id)
    db.refresh(pedido)
    return pedido


def quitar_documento(
    db: Session, ctx: Contexto, pedido_id: uuid.UUID, archivo_id: uuid.UUID
) -> Pedido:
    pedido = _bloqueado(db, ctx, pedido_id)
    _exigir_estado(pedido, EstadoPedido.BORRADOR)
    documento = next((d for d in _documentos_activos(pedido) if d.archivo_id == archivo_id), None)
    if documento is None:
        raise NoEncontrado("El archivo no pertenece a este pedido.")
    documento.activo = False  # se conserva el archivo; solo deja de formar parte de la OC
    _evento(db, ctx, pedido, "DOCUMENTO_QUITADO", {"archivo": documento.archivo.nombre_original})
    auditoria.registrar_ctx(
        db,
        ctx,
        accion="pedido.quitar_documento",
        entidad="pedido",
        entidad_id=pedido.id,
        antes={"archivo": documento.archivo.nombre_original},
    )
    db.commit()
    db.refresh(pedido)
    return pedido


def archivo_de_pedido(
    db: Session, ctx: Contexto, pedido_id: uuid.UUID, archivo_id: uuid.UUID
) -> Archivo:
    """Archivo visible para quien puede ver el pedido (OC o constancia)."""
    pedido = obtener(db, ctx, pedido_id)
    permitidos = {d.archivo_id for d in pedido.documentos}
    permitidos |= {x for x in (pedido.constancia_foto_id, pedido.constancia_firma_id) if x}
    if archivo_id not in permitidos:
        raise NoEncontrado("El archivo no pertenece a este pedido.")
    return documentos.obtener(db, ctx, archivo_id)


def _foto_borrador(p: Pedido) -> dict[str, Any]:
    return {
        "ubicacion_id": p.ubicacion_id,
        "cadena_id": p.cadena_id,
        "sucursal_cliente_id": p.sucursal_cliente_id,
        "numero_oc": p.numero_oc,
        "fecha_oc": p.fecha_oc,
        "total_oc": p.total_oc,
        "lineas": [
            {
                "codigo": x.codigo_cliente,
                "descripcion": x.descripcion_cliente,
                "producto_id": x.producto_id,
                "cantidad_oc": x.cantidad_oc,
                "precio_oc": x.precio_oc,
                "total_linea_oc": x.total_linea_oc,
                "cantidad_confirmada": x.cantidad_confirmada,
            }
            for x in p.lineas
        ],
    }


def guardar_borrador(
    db: Session, ctx: Contexto, pedido_id: uuid.UUID, datos: PedidoBorradorEntrada
) -> Pedido:
    """Guarda los datos de la OC tal como se leyeron o corrigieron (todo es editable, D-06)."""
    pedido = _bloqueado(db, ctx, pedido_id)
    _exigir_estado(pedido, EstadoPedido.BORRADOR)
    antes = _foto_borrador(pedido)

    if datos.ubicacion_id != pedido.ubicacion_id:
        pedido.ubicacion_id = _sucursal_despacho(db, ctx, datos.ubicacion_id).id
    if datos.cadena_id:
        cadena = db.get(Cadena, datos.cadena_id)
        if cadena is None or cadena.empresa_id != ctx.empresa_id:
            raise NoEncontrado("La cadena no existe.")
        if not cadena.activo and cadena.id != pedido.cadena_id:
            raise ReglaNegocio(f"La cadena «{cadena.nombre}» está inactiva.")
    if datos.sucursal_cliente_id:
        sucursal = db.get(SucursalCliente, datos.sucursal_cliente_id)
        if sucursal is None or sucursal.cadena_id != datos.cadena_id:
            raise ReglaNegocio("La sucursal de supermercado no pertenece a la cadena elegida.")
        if not sucursal.activo and sucursal.id != pedido.sucursal_cliente_id:
            raise ReglaNegocio(f"La sucursal de supermercado «{sucursal.nombre}» está inactiva.")
    if datos.fecha_oc and datos.fecha_oc > hoy():
        raise ReglaNegocio("La fecha del pedido no puede ser futura.")
    numero_oc = (datos.numero_oc or "").strip() or None
    # Se verifica antes de modificar nada; el índice único cubre el caso de dos personas
    # guardando la misma OC a la vez.
    if otro := _duplicado(db, ctx, pedido, cadena_id=datos.cadena_id, numero_oc=numero_oc):
        raise Conflicto(_mensaje_duplicado(otro))

    pedido.cadena_id = datos.cadena_id
    pedido.sucursal_cliente_id = datos.sucursal_cliente_id
    pedido.numero_oc = numero_oc
    pedido.fecha_oc = datos.fecha_oc
    pedido.fecha_entrega = datos.fecha_entrega
    pedido.emisor = (datos.emisor or "").strip() or None
    pedido.total_oc = datos.total_oc
    pedido.observaciones = (datos.observaciones or "").strip() or None

    nuevas: list[PedidoLinea] = []
    for orden, linea in enumerate(datos.lineas, start=1):
        if linea.producto_id:
            producto = catalogo.obtener_producto(db, ctx, linea.producto_id)
            if not producto.activo:
                raise ReglaNegocio(f"Línea {orden}: «{producto.nombre}» está inactivo.")
        confirmada = (
            linea.cantidad_oc if linea.cantidad_confirmada is None else linea.cantidad_confirmada
        )
        if confirmada > linea.cantidad_oc:
            raise ReglaNegocio(
                f"Línea {orden}: no se puede confirmar más de la cantidad del pedido "
                f"({dominio_inv.formatear_cantidad(linea.cantidad_oc)})."
            )
        previa = pedido.lineas[orden - 1] if orden - 1 < len(pedido.lineas) else None
        nuevas.append(
            PedidoLinea(
                orden=orden,
                # La confianza de la lectura se conserva mientras la línea no cambie.
                confianza=(
                    previa.confianza
                    if previa
                    and previa.confianza
                    and (previa.cantidad_oc, previa.precio_oc, previa.total_linea_oc)
                    == (linea.cantidad_oc, linea.precio_oc, linea.total_linea_oc)
                    else None
                ),
                codigo_cliente=(linea.codigo_cliente or "").strip() or None,
                descripcion_cliente=linea.descripcion_cliente.strip(),
                producto_id=linea.producto_id,
                cantidad_oc=linea.cantidad_oc,
                precio_oc=linea.precio_oc,
                total_linea_oc=linea.total_linea_oc,
                cantidad_confirmada=confirmada,
            )
        )
    pedido.lineas = nuevas

    auditoria.registrar_ctx(
        db,
        ctx,
        accion="pedido.editar",
        entidad="pedido",
        entidad_id=pedido.id,
        antes=antes,
        despues=_foto_borrador(pedido),
    )
    _commit(db)
    db.refresh(pedido)
    return pedido


# ================================================================ revisión


def _disponibles(
    db: Session, ctx: Contexto, productos: set[uuid.UUID]
) -> dict[tuple[uuid.UUID, uuid.UUID], Decimal]:
    """Disponible para vender por (ubicación, producto): stock vigente - comprometido."""
    if not productos:
        return {}
    vigentes = {
        (ub, prod): cant
        for ub, prod, cant in db.execute(
            select(StockLote.ubicacion_id, StockLote.producto_id, func.sum(StockLote.cantidad))
            .join(Lote, Lote.id == StockLote.lote_id)
            .where(
                Lote.empresa_id == ctx.empresa_id,
                StockLote.producto_id.in_(productos),
                or_(Lote.vencimiento.is_(None), Lote.vencimiento >= hoy()),
            )
            .group_by(StockLote.ubicacion_id, StockLote.producto_id)
        )
    }
    comprometidos = {
        (s.ubicacion_id, s.producto_id): s.comprometido
        for s in db.scalars(
            select(StockUbicacion).where(
                StockUbicacion.empresa_id == ctx.empresa_id,
                StockUbicacion.producto_id.in_(productos),
            )
        )
    }
    return {
        clave: max(vigentes.get(clave, CERO) - comprometidos.get(clave, CERO), CERO)
        for clave in set(vigentes) | set(comprometidos)
    }


def _precios_anteriores(
    db: Session, ctx: Contexto, pedido: Pedido, productos: set[uuid.UUID]
) -> dict[uuid.UUID, tuple[Decimal, date | None, int]]:
    """Último precio de esta cadena para cada producto (pedidos confirmados en adelante)."""
    if not (pedido.cadena_id and productos):
        return {}
    fecha = func.coalesce(Pedido.fecha_oc, func.date(Pedido.confirmado_at))
    filas = db.execute(
        select(PedidoLinea.producto_id, PedidoLinea.precio_oc, fecha, Pedido.numero)
        .join(Pedido, Pedido.id == PedidoLinea.pedido_id)
        .where(
            Pedido.empresa_id == ctx.empresa_id,
            Pedido.cadena_id == pedido.cadena_id,
            Pedido.id != pedido.id,
            Pedido.estado.in_(
                [EstadoPedido.CONFIRMADO, EstadoPedido.ALISTADO, EstadoPedido.ENTREGADO]
            ),
            PedidoLinea.producto_id.in_(productos),
        )
        .ext(distinct_on(PedidoLinea.producto_id))
        .order_by(PedidoLinea.producto_id, fecha.desc(), Pedido.numero.desc())
    )
    return {prod: (precio, f, numero) for prod, precio, f, numero in filas if prod is not None}


def _validaciones(
    db: Session,
    ctx: Contexto,
    pedido: Pedido,
    disponibles: dict[tuple[uuid.UUID, uuid.UUID], Decimal],
    precios: dict[uuid.UUID, tuple[Decimal, date | None, int]],
) -> list[Validacion]:
    v: list[Validacion] = []

    def error(mensaje: str, linea: PedidoLinea | None = None) -> None:
        v.append(Validacion(nivel="error", mensaje=mensaje, linea_id=linea.id if linea else None))

    def aviso(mensaje: str, linea: PedidoLinea | None = None) -> None:
        v.append(Validacion(nivel="aviso", mensaje=mensaje, linea_id=linea.id if linea else None))

    if not pedido.cadena_id:
        error("Indique la cadena.")
    if not pedido.sucursal_cliente_id:
        error("Indique la sucursal de supermercado que recibe el pedido.")
    if not pedido.fecha_oc:
        error("Indique la fecha del pedido.")
    if otro := _duplicado(db, ctx, pedido):
        error(_mensaje_duplicado(otro))
    if not pedido.lineas:
        error("El pedido no tiene líneas.")
    elif not _lineas_activas(pedido):
        error("Todas las cantidades a confirmar están en cero: anule el pedido en su lugar.")

    por_linea = {x.orden: x for x in pedido.lineas}
    for numero, mensaje in dominio.validar_aritmetica(
        [
            dominio.LineaOC(x.orden, x.cantidad_oc, x.precio_oc, x.total_linea_oc)
            for x in pedido.lineas
        ],
        pedido.total_oc,
    ):
        aviso(mensaje, por_linea.get(numero) if numero else None)

    pedido_por_producto: dict[uuid.UUID, Decimal] = defaultdict(lambda: CERO)
    for x in _lineas_activas(pedido):
        if x.producto_id:
            pedido_por_producto[x.producto_id] += x.cantidad_confirmada
    for x in pedido.lineas:
        if x.producto is None:
            if x.cantidad_confirmada > 0:
                error(
                    f"Línea {x.orden}: elija el producto que corresponde a "
                    f"«{x.descripcion_cliente}».",
                    x,
                )
            continue
        if x.cantidad_confirmada > 0:
            disponible = disponibles.get((pedido.ubicacion_id, x.producto.id), CERO)
            if pedido_por_producto[x.producto.id] > disponible:
                error(
                    f"Línea {x.orden}: solo hay {dominio_inv.formatear_cantidad(disponible)} "
                    f"{x.producto.unidad_base} disponibles de «{x.producto.nombre}» en "
                    f"{pedido.ubicacion.nombre}. Reduzca la cantidad o transfiera desde el "
                    "depósito.",
                    x,
                )
        if x.cantidad_confirmada < x.cantidad_oc:
            aviso(
                f"Línea {x.orden}: se confirmarán "
                f"{dominio_inv.formatear_cantidad(x.cantidad_confirmada)} de "
                f"{dominio_inv.formatear_cantidad(x.cantidad_oc)} pedidos.",
                x,
            )
        anterior = precios.get(x.producto.id)
        if anterior and anterior[0] != x.precio_oc:
            aviso(
                f"Línea {x.orden}: el precio (Bs {x.precio_oc.normalize():f}) es distinto del "
                f"último para esta cadena (Bs {anterior[0].normalize():f}, pedido #{anterior[2]}).",
                x,
            )
    return v


def revision(
    db: Session, ctx: Contexto, pedido: Pedido
) -> tuple[
    list[Validacion],
    dict[tuple[uuid.UUID, uuid.UUID], Decimal],
    dict[uuid.UUID, tuple[Decimal, date | None, int]],
]:
    productos = {x.producto_id for x in pedido.lineas if x.producto_id}
    disponibles = _disponibles(db, ctx, productos)
    precios = _precios_anteriores(db, ctx, pedido, productos)
    return _validaciones(db, ctx, pedido, disponibles, precios), disponibles, precios


# ================================================================ confirmar


def _aprender_equivalencias(db: Session, ctx: Contexto, pedido: Pedido) -> int:
    """Cada emparejamiento confirmado se guarda: la próxima OC de la cadena se empareja sola."""
    assert pedido.cadena_id is not None
    aprendidas = 0
    for x in pedido.lineas:
        if not x.producto_id:
            continue
        for clave in dominio.claves_equivalencia(x.codigo_cliente, x.descripcion_cliente):
            db.execute(
                pg_insert(Equivalencia)
                .values(
                    id=uuid.uuid4(),
                    empresa_id=ctx.empresa_id,
                    cadena_id=pedido.cadena_id,
                    clave=clave,
                    codigo_cliente=x.codigo_cliente,
                    descripcion_cliente=x.descripcion_cliente,
                    producto_id=x.producto_id,
                )
                .on_conflict_do_update(
                    index_elements=["cadena_id", "clave"],
                    set_={
                        "producto_id": x.producto_id,
                        "usos": Equivalencia.usos + 1,
                        "ultimo_uso": func.now(),
                    },
                )
            )
            aprendidas += 1
    return aprendidas


def confirmar(db: Session, ctx: Contexto, pedido_id: uuid.UUID) -> Pedido:
    """Confirma lo revisado y reserva el stock. Nunca se reserva más de lo disponible (D-02)."""
    pedido = _bloqueado(db, ctx, pedido_id)
    _exigir_estado(pedido, EstadoPedido.BORRADOR)
    ubicacion = _sucursal_despacho(db, ctx, pedido.ubicacion_id)
    validaciones, _, _ = revision(db, ctx, pedido)
    errores = [x.mensaje for x in validaciones if x.nivel == "error"]
    if errores:
        raise ReglaNegocio("No se puede confirmar: " + " ".join(errores[:5]))

    por_producto: dict[uuid.UUID, Decimal] = defaultdict(lambda: CERO)
    for x in _lineas_activas(pedido):
        assert x.producto_id is not None
        por_producto[x.producto_id] += x.cantidad_confirmada
    motor.bloquear(db, ctx, ((ubicacion.id, p) for p in por_producto))
    for producto_id, cantidad in por_producto.items():
        motor.reservar(
            db, ctx, ubicacion_id=ubicacion.id, producto_id=producto_id, cantidad=cantidad
        )

    pedido.estado = EstadoPedido.CONFIRMADO
    pedido.confirmado_por_id = ctx.usuario.id
    pedido.confirmado_at = ahora()
    aprendidas = _aprender_equivalencias(db, ctx, pedido)
    lectura.registrar_correcciones(db, pedido)
    _evento(db, ctx, pedido, "CONFIRMADO", {"lineas": len(por_producto)})
    auditoria.registrar_ctx(
        db,
        ctx,
        accion="pedido.confirmar",
        entidad="pedido",
        entidad_id=pedido.id,
        antes={"estado": EstadoPedido.BORRADOR},
        despues={
            "estado": pedido.estado,
            "numero_oc": pedido.numero_oc,
            "reservado": {str(k): v for k, v in por_producto.items()},
            "equivalencias": aprendidas,
        },
    )
    eventos.publicar(
        db,
        empresa_id=ctx.empresa_id,
        tipo="PedidoConfirmado",
        agregado="pedido",
        agregado_id=pedido.id,
        datos={"numero": pedido.numero, "ubicacion_id": ubicacion.id},
    )
    _commit(db)
    db.refresh(pedido)
    return pedido


# ================================================================ alistar


def _recalcular_totales(pedido: Pedido) -> None:
    ingreso = sum((x.ingreso or CERO for x in pedido.lineas), CERO)
    costo = sum((x.costo_total or CERO for x in pedido.lineas), CERO)
    r = dominio.rentabilidad(ingreso, costo)
    pedido.ingreso, pedido.costo, pedido.ganancia, pedido.margen = (
        r.ingreso,
        r.costo,
        r.ganancia,
        r.margen,
    )


def alistar(db: Session, ctx: Contexto, pedido_id: uuid.UUID, datos: AlistarEntrada) -> Pedido:
    """Descuenta el stock físico: libera la reserva, saca los lotes (FEFO o elegidos), congela
    el costo y calcula la ganancia. Puede salir menos de lo confirmado (D-11)."""
    pedido = _bloqueado(db, ctx, pedido_id)
    _exigir_estado(pedido, EstadoPedido.CONFIRMADO)
    ubicacion = ubicaciones.operable(db, ctx, pedido.ubicacion_id)
    lineas = {x.id: x for x in pedido.lineas}
    entradas: dict[uuid.UUID, AlistarLineaEntrada] = {}
    for e in datos.lineas:
        linea = lineas.get(e.linea_id)
        if linea is None:
            raise ReglaNegocio("Una de las líneas no pertenece a este pedido.")
        if e.linea_id in entradas:
            raise ReglaNegocio(f"La línea {linea.orden} está repetida.")
        if e.cantidad_alistada > linea.cantidad_confirmada:
            raise ReglaNegocio(
                f"Línea {linea.orden}: no se puede alistar más de lo confirmado "
                f"({dominio_inv.formatear_cantidad(linea.cantidad_confirmada)})."
            )
        if e.lotes and sum((x.cantidad for x in e.lotes), CERO) != e.cantidad_alistada:
            raise ReglaNegocio(
                f"Línea {linea.orden}: la suma de los lotes debe ser igual a la cantidad alistada."
            )
        if (e.cantidad_alistada > 0 or e.cantidad_merma > 0) and linea.producto_id is None:
            raise ReglaNegocio(f"Línea {linea.orden}: no tiene producto.")
        entradas[e.linea_id] = e
    faltan = [x.orden for x in _lineas_activas(pedido) if x.id not in entradas]
    if faltan:
        raise ReglaNegocio(
            "Indique la cantidad alistada de las líneas " + ", ".join(map(str, faltan)) + "."
        )
    if not any(e.cantidad_alistada > 0 for e in entradas.values()):
        raise ReglaNegocio("No se alistó ningún producto: si no se entregará, anule el pedido.")

    doc = motor.Origen(ORIGEN, pedido.id)
    productos = {x.producto_id for x in pedido.lineas if x.producto_id}
    motor.bloquear(db, ctx, ((ubicacion.id, p) for p in productos))
    # 1. Liberar toda la reserva del pedido.
    for x in _lineas_activas(pedido):
        assert x.producto_id is not None
        motor.liberar(
            db,
            ctx,
            ubicacion_id=ubicacion.id,
            producto_id=x.producto_id,
            cantidad=x.cantidad_confirmada,
        )
    # 2. Descontar lo alistado, solo de lotes vigentes, valorado al CPP de la sucursal (D-04).
    motivo = f"Pedido #{pedido.numero}" + (f" · OC {pedido.numero_oc}" if pedido.numero_oc else "")
    for x in pedido.lineas:
        elegida = entradas.get(x.id)
        alistada = elegida.cantidad_alistada if elegida else CERO
        x.cantidad_alistada = alistada
        x.cantidad_merma = elegida.cantidad_merma if elegida else CERO
        if alistada == 0:
            x.costo_unitario, x.costo_total, x.ingreso, x.ganancia = CERO, CERO, CERO, CERO
            continue
        assert x.producto_id is not None and elegida is not None
        tramos: list[tuple[uuid.UUID | None, Decimal]] = (
            [(lt.lote_id, lt.cantidad) for lt in elegida.lotes]
            if elegida.lotes
            else [(None, alistada)]
        )
        valor = CERO
        for lote_id, cantidad in tramos:
            if lote_id is not None:
                lote = db.get(Lote, lote_id)
                if lote is None or lote.producto_id != x.producto_id:
                    raise ReglaNegocio(f"Línea {x.orden}: el lote elegido no es de este producto.")
            for mov in motor.salida(
                db,
                ctx,
                tipo=TipoMovimiento.VENTA,
                ubicacion_id=ubicacion.id,
                producto_id=x.producto_id,
                cantidad=cantidad,
                origen=doc,
                lote_id=lote_id,
                excluir_vencidos=True,
                motivo=motivo,
            ):
                assert mov.lote_id is not None
                x.lotes.append(
                    PedidoLineaLote(
                        lote_id=mov.lote_id,
                        cantidad=-mov.cantidad,
                        costo_unitario=mov.costo_unitario,
                    )
                )
                valor += -mov.costo_total
        x.costo_total = dominio_inv.redondear(valor, dominio_inv.Q_DINERO)
        x.costo_unitario = dominio_inv.redondear(valor / alistada, dominio_inv.Q_COSTO)
        x.ingreso = dominio.total_calculado(alistada, x.precio_oc)
        x.ganancia = x.ingreso - x.costo_total
    _recalcular_totales(pedido)

    # 3. Lo encontrado en mal estado se da de baja como merma vinculada al pedido (D-11).
    mermas = [x for x in pedido.lineas if x.cantidad_merma > 0]
    ajuste = None
    if mermas:
        ajuste = inventario.registrar_ajuste(
            db,
            ctx,
            AjusteEntrada(
                ubicacion_id=ubicacion.id,
                motivo=MotivoAjuste.ROTURA,
                observacion=(
                    datos.observacion_merma
                    or f"Producto en mal estado encontrado al alistar el pedido #{pedido.numero}"
                ),
                lineas=[
                    AjusteLineaEntrada(
                        producto_id=x.producto_id,
                        cantidad=x.cantidad_merma,
                        sentido="DISMINUCION",
                    )
                    for x in mermas
                    if x.producto_id
                ],
            ),
            pedido_id=pedido.id,
        )

    pedido.estado = EstadoPedido.ALISTADO
    pedido.alistado_por_id = ctx.usuario.id
    pedido.alistado_at = ahora()
    _evento(
        db,
        ctx,
        pedido,
        "ALISTADO",
        {"merma_ajuste": ajuste.numero if ajuste else None},
    )
    auditoria.registrar_ctx(
        db,
        ctx,
        accion="pedido.alistar",
        entidad="pedido",
        entidad_id=pedido.id,
        antes={"estado": EstadoPedido.CONFIRMADO},
        despues={
            "estado": pedido.estado,
            "ingreso": pedido.ingreso,
            "costo": pedido.costo,
            "ganancia": pedido.ganancia,
            "merma_ajuste": ajuste.numero if ajuste else None,
        },
    )
    eventos.publicar(
        db,
        empresa_id=ctx.empresa_id,
        tipo="PedidoAlistado",
        agregado="pedido",
        agregado_id=pedido.id,
        datos={
            "numero": pedido.numero,
            "ingreso": pedido.ingreso,
            "costo": pedido.costo,
            "ganancia": pedido.ganancia,
            "margen": pedido.margen,
        },
    )
    db.commit()
    db.refresh(pedido)
    return pedido


# ================================================================ entregar


def entregar(
    db: Session,
    ctx: Contexto,
    pedido_id: uuid.UUID,
    *,
    receptor_nombre: str | None,
    observacion: str | None,
    foto: tuple[bytes, str | None] | None,
    firma: tuple[bytes, str | None] | None,
) -> Pedido:
    pedido = _bloqueado(db, ctx, pedido_id)
    _exigir_estado(pedido, EstadoPedido.ALISTADO)
    if foto:
        pedido.constancia_foto_id = documentos.guardar(db, ctx, *foto, solo_imagen=True).id
    if firma:
        pedido.constancia_firma_id = documentos.guardar(db, ctx, *firma, solo_imagen=True).id
    pedido.receptor_nombre = (receptor_nombre or "").strip()[:120] or None
    pedido.entrega_observacion = (observacion or "").strip()[:500] or None
    pedido.estado = EstadoPedido.ENTREGADO
    pedido.entregado_por_id = ctx.usuario.id
    pedido.entregado_at = ahora()
    _evento(
        db,
        ctx,
        pedido,
        "ENTREGADO",
        {"receptor": pedido.receptor_nombre, "foto": bool(foto), "firma": bool(firma)},
    )
    auditoria.registrar_ctx(
        db,
        ctx,
        accion="pedido.entregar",
        entidad="pedido",
        entidad_id=pedido.id,
        antes={"estado": EstadoPedido.ALISTADO},
        despues={"estado": pedido.estado, "receptor": pedido.receptor_nombre},
    )
    eventos.publicar(
        db,
        empresa_id=ctx.empresa_id,
        tipo="PedidoEntregado",
        agregado="pedido",
        agregado_id=pedido.id,
        datos={"numero": pedido.numero},
    )
    db.commit()
    db.refresh(pedido)
    return pedido


# ================================================================ anular


def anular(db: Session, ctx: Contexto, pedido_id: uuid.UUID, motivo: str) -> Pedido:
    pedido = _bloqueado(db, ctx, pedido_id)
    if pedido.estado == EstadoPedido.ENTREGADO:
        raise ReglaNegocio(
            "Un pedido entregado no se puede anular. Si el supermercado devolvió mercadería, "
            "registre una devolución."
        )
    _exigir_estado(pedido, EstadoPedido.BORRADOR, EstadoPedido.CONFIRMADO, EstadoPedido.ALISTADO)
    propio_borrador = (
        pedido.estado == EstadoPedido.BORRADOR and pedido.responsable_id == ctx.usuario.id
    )
    if not (propio_borrador or ctx.puede("pedidos.anular")):
        raise SinPermiso("No tiene permiso para anular este pedido.")

    anterior = pedido.estado
    if anterior == EstadoPedido.CONFIRMADO:
        ubicaciones.operable(db, ctx, pedido.ubicacion_id)
        motor.bloquear(
            db,
            ctx,
            (
                (pedido.ubicacion_id, x.producto_id)
                for x in _lineas_activas(pedido)
                if x.producto_id
            ),
        )
        for x in _lineas_activas(pedido):
            assert x.producto_id is not None
            motor.liberar(
                db,
                ctx,
                ubicacion_id=pedido.ubicacion_id,
                producto_id=x.producto_id,
                cantidad=x.cantidad_confirmada,
            )
    elif anterior == EstadoPedido.ALISTADO:
        ubicaciones.operable(db, ctx, pedido.ubicacion_id)
        # Devuelve al stock lo alistado, en los mismos lotes y al mismo costo.
        motor.revertir(
            db, ctx, motor.Origen(ORIGEN, pedido.id), f"Anulación pedido #{pedido.numero}: {motivo}"
        )

    pedido.estado = EstadoPedido.ANULADO
    pedido.anulado_desde = anterior
    pedido.anulacion_motivo = motivo
    pedido.anulado_por_id = ctx.usuario.id
    pedido.anulado_at = ahora()
    _evento(db, ctx, pedido, "ANULADO", {"desde": anterior, "motivo": motivo})
    auditoria.registrar_ctx(
        db,
        ctx,
        accion="pedido.anular",
        entidad="pedido",
        entidad_id=pedido.id,
        antes={"estado": anterior},
        despues={"estado": pedido.estado, "motivo": motivo},
    )
    eventos.publicar(
        db,
        empresa_id=ctx.empresa_id,
        tipo="PedidoAnulado",
        agregado="pedido",
        agregado_id=pedido.id,
        datos={"numero": pedido.numero, "desde": anterior},
    )
    db.commit()
    db.refresh(pedido)
    return pedido


# ================================================================ devoluciones (D-12)


def devolver(db: Session, ctx: Contexto, pedido_id: uuid.UUID, datos: DevolucionEntrada) -> Pedido:
    """Mercadería que el supermercado devolvió después de la entrega: vuelve al stock de la
    sucursal en los mismos lotes y al costo con que salió, y se recalcula la ganancia."""
    pedido = _bloqueado(db, ctx, pedido_id)
    _exigir_estado(pedido, EstadoPedido.ENTREGADO)
    ubicacion = ubicaciones.operable(db, ctx, pedido.ubicacion_id)
    lineas = {x.id: x for x in pedido.lineas}
    pedidas: dict[uuid.UUID, Decimal] = defaultdict(lambda: CERO)
    for e in datos.lineas:
        if e.linea_id not in lineas:
            raise ReglaNegocio("Una de las líneas no pertenece a este pedido.")
        pedidas[e.linea_id] += e.cantidad
    for linea_id, cantidad in pedidas.items():
        x = lineas[linea_id]
        entregada = (x.cantidad_alistada or CERO) - x.cantidad_devuelta
        if cantidad > entregada:
            raise ReglaNegocio(
                f"Línea {x.orden}: se entregaron {dominio_inv.formatear_cantidad(entregada)}; no "
                "se puede devolver más."
            )

    devolucion = Devolucion(
        empresa_id=ctx.empresa_id,
        pedido_id=pedido.id,
        motivo=datos.motivo,
        usuario_id=ctx.usuario.id,
    )
    db.add(devolucion)
    db.flush()
    doc = motor.Origen(ORIGEN_DEVOLUCION, devolucion.id)
    motor.bloquear(
        db,
        ctx,
        ((ubicacion.id, p) for i in pedidas if (p := lineas[i].producto_id) is not None),
    )
    motivo = f"Devolución pedido #{pedido.numero}: {datos.motivo}"
    for linea_id, cantidad in pedidas.items():
        x = lineas[linea_id]
        pendiente = cantidad
        valor = CERO
        # Vuelve primero lo último que salió.
        for tramo in reversed(x.lotes):
            libre = tramo.cantidad - tramo.devuelta
            if pendiente == 0 or libre <= 0:
                continue
            tomar = min(libre, pendiente)
            motor.entrada(
                db,
                ctx,
                tipo=TipoMovimiento.DEVOLUCION_CLIENTE,
                ubicacion_id=ubicacion.id,
                lote=tramo.lote,
                cantidad=tomar,
                costo_unitario=tramo.costo_unitario,
                origen=doc,
                motivo=motivo,
            )
            tramo.devuelta += tomar
            valor += tomar * tramo.costo_unitario
            pendiente -= tomar
        assert pendiente == 0
        costo = dominio_inv.redondear(valor, dominio_inv.Q_DINERO)
        neto = (x.cantidad_alistada or CERO) - x.cantidad_devuelta - cantidad
        ingreso_nuevo = dominio.total_calculado(neto, x.precio_oc)
        devolucion.lineas.append(
            DevolucionLinea(
                pedido_linea_id=x.id,
                cantidad=cantidad,
                costo_total=costo,
                ingreso=(x.ingreso or CERO) - ingreso_nuevo,
            )
        )
        x.cantidad_devuelta += cantidad
        x.costo_total = (x.costo_total or CERO) - costo
        x.ingreso = ingreso_nuevo
        x.ganancia = x.ingreso - x.costo_total
    _recalcular_totales(pedido)
    _evento(db, ctx, pedido, "DEVOLUCION", {"numero": devolucion.numero, "motivo": datos.motivo})
    auditoria.registrar_ctx(
        db,
        ctx,
        accion="pedido.devolucion",
        entidad="pedido",
        entidad_id=pedido.id,
        despues={
            "devolucion": devolucion.numero,
            "motivo": datos.motivo,
            "lineas": {str(k): v for k, v in pedidas.items()},
            "ganancia": pedido.ganancia,
        },
    )
    eventos.publicar(
        db,
        empresa_id=ctx.empresa_id,
        tipo="DevolucionRegistrada",
        agregado="pedido",
        agregado_id=pedido.id,
        datos={"numero": pedido.numero, "devolucion": devolucion.numero},
    )
    db.commit()
    db.refresh(pedido)
    return pedido


# ================================================================ emparejamiento


def sugerencias(
    db: Session,
    ctx: Contexto,
    *,
    cadena_id: uuid.UUID | None,
    codigo: str | None,
    descripcion: str | None,
    limite: int = 5,
) -> list[Sugerencia]:
    """Busca el producto interno de una línea de OC: (1) equivalencia ya aprendida para la
    cadena, (2) código de barras o SKU, (3) parecido del nombre (trigramas)."""
    resultado: list[Sugerencia] = []
    vistos: set[uuid.UUID] = set()

    def agregar(producto: Producto, fuente: Any, puntaje: float) -> None:
        if producto.id not in vistos and producto.activo:
            vistos.add(producto.id)
            resultado.append(
                Sugerencia(
                    producto=ProductoSalida.model_validate(producto), fuente=fuente, puntaje=puntaje
                )
            )

    claves = dominio.claves_equivalencia(codigo, descripcion)
    if cadena_id and claves:
        equivalencias = db.scalars(
            select(Equivalencia).where(
                Equivalencia.empresa_id == ctx.empresa_id,
                Equivalencia.cadena_id == cadena_id,
                Equivalencia.clave.in_(claves),
            )
        )
        for eq in sorted(equivalencias, key=lambda e: (not e.clave.startswith("C:"), -e.usos)):
            agregar(eq.producto, "equivalencia", 1.0 if eq.clave.startswith("C:") else 0.95)

    if c := dominio.normalizar_codigo(codigo):
        for p in db.scalars(
            select(Producto).where(
                Producto.empresa_id == ctx.empresa_id,
                or_(
                    func.upper(func.replace(Producto.codigo_barras, " ", "")) == c,
                    func.upper(Producto.sku) == c,
                ),
            )
        ):
            agregar(p, "codigo", 0.9)

    if (d := dominio.normalizar_descripcion(descripcion)) and len(resultado) < limite:
        similitud = func.similarity(func.lower(Producto.nombre), d)
        for p, puntaje in db.execute(
            select(Producto, similitud)
            .where(
                Producto.empresa_id == ctx.empresa_id,
                Producto.activo.is_(True),
                similitud > 0.12,
            )
            .order_by(similitud.desc())
            .limit(limite)
        ):
            agregar(p, "similitud", round(float(puntaje) * 0.85, 3))
    return resultado[:limite]


# ================================================================ consultas y salida


def listar(
    db: Session,
    ctx: Contexto,
    *,
    estado: EstadoPedido | None,
    cadena_id: uuid.UUID | None,
    ubicacion_id: uuid.UUID | None,
    buscar: str | None,
    desde: date | None,
    hasta: date | None,
    pagina: int,
    tamano: int,
) -> Pagina[PedidoResumen]:
    filtros: list[Any] = [Pedido.empresa_id == ctx.empresa_id]
    if not ctx.puede("pedidos.ver_todos"):
        filtros.append(Pedido.responsable_id == ctx.usuario.id)
    if estado:
        filtros.append(Pedido.estado == estado)
    if cadena_id:
        filtros.append(Pedido.cadena_id == cadena_id)
    if ubicacion_id:
        filtros.append(Pedido.ubicacion_id == ubicacion_id)
    if buscar and (texto := buscar.strip()):
        condiciones: list[Any] = [Pedido.numero_oc.ilike(f"%{texto}%")]
        if texto.lstrip("#").isdigit():
            condiciones.append(Pedido.numero == int(texto.lstrip("#")))
        filtros.append(or_(*condiciones))
    fecha = func.date(func.timezone("America/La_Paz", Pedido.created_at))
    if desde:
        filtros.append(fecha >= desde)
    if hasta:
        filtros.append(fecha <= hasta)
    total = db.scalar(select(func.count()).select_from(Pedido).where(*filtros)) or 0
    pedidos = db.scalars(
        select(Pedido)
        .where(*filtros)
        .order_by(Pedido.numero.desc())
        .offset((pagina - 1) * tamano)
        .limit(tamano)
    )
    return Pagina(
        items=[resumen(p, ctx) for p in pedidos], total=total, pagina=pagina, tamano=tamano
    )


def _ref(obj: Any) -> Referencia | None:
    return Referencia(id=obj.id, nombre=obj.nombre) if obj is not None else None


def resumen(p: Pedido, ctx: Contexto) -> PedidoResumen:
    ver_costos = ctx.puede("costos.ver")
    ubicacion = _ref(p.ubicacion)
    assert ubicacion is not None
    return PedidoResumen(
        id=p.id,
        numero=p.numero,
        estado=p.estado,
        numero_oc=p.numero_oc,
        fecha_oc=p.fecha_oc,
        fecha_entrega=p.fecha_entrega,
        cadena=_ref(p.cadena),
        sucursal_cliente=_ref(p.sucursal_cliente),
        ubicacion=ubicacion,
        responsable_id=p.responsable_id,
        responsable_nombre=p.responsable.nombre_completo,
        total_oc=p.total_oc,
        total_calculado=sum(
            (dominio.total_calculado(x.cantidad_oc, x.precio_oc) for x in p.lineas), CERO
        ),
        lineas=len(p.lineas),
        documentos=len(_documentos_activos(p)),
        created_at=p.created_at,
        ganancia=p.ganancia if ver_costos else None,
        margen=p.margen if ver_costos else None,
    )


def detalle(db: Session, ctx: Contexto, p: Pedido) -> PedidoDetalle:
    ver_costos = ctx.puede("costos.ver")
    en_revision = p.estado == EstadoPedido.BORRADOR
    if en_revision:
        validaciones, disponibles, precios = revision(db, ctx, p)
        depositos = {
            u.id
            for u in db.scalars(
                select(Ubicacion).where(
                    Ubicacion.empresa_id == ctx.empresa_id,
                    Ubicacion.tipo == TipoUbicacion.DEPOSITO,
                    Ubicacion.activo.is_(True),
                )
            )
        }
    else:
        validaciones, disponibles, precios, depositos = [], {}, {}, set()

    lineas = []
    for x in p.lineas:
        anterior = precios.get(x.producto_id) if x.producto_id else None
        margen = None
        if ver_costos and x.ingreso is not None and x.costo_total is not None:
            margen = dominio.rentabilidad(x.ingreso, x.costo_total).margen
        lineas.append(
            PedidoLineaSalida(
                id=x.id,
                orden=x.orden,
                codigo_cliente=x.codigo_cliente,
                descripcion_cliente=x.descripcion_cliente,
                producto=ProductoSalida.model_validate(x.producto) if x.producto else None,
                cantidad_oc=x.cantidad_oc,
                precio_oc=x.precio_oc,
                total_linea_oc=x.total_linea_oc,
                total_calculado=dominio.total_calculado(x.cantidad_oc, x.precio_oc),
                cantidad_confirmada=x.cantidad_confirmada,
                cantidad_alistada=x.cantidad_alistada,
                cantidad_merma=x.cantidad_merma,
                cantidad_devuelta=x.cantidad_devuelta,
                disponible=(
                    disponibles.get((p.ubicacion_id, x.producto_id), CERO)
                    if en_revision and x.producto_id
                    else None
                ),
                disponible_depositos=(
                    sum(
                        (
                            v
                            for (ub, prod), v in disponibles.items()
                            if ub in depositos and prod == x.producto_id
                        ),
                        CERO,
                    )
                    if en_revision and x.producto_id
                    else None
                ),
                precio_anterior=anterior[0] if anterior else None,
                precio_anterior_fecha=anterior[1] if anterior else None,
                precio_anterior_pedido=anterior[2] if anterior else None,
                lotes=[
                    LoteSalida(
                        lote_id=t.lote_id,
                        codigo=t.lote.codigo,
                        vencimiento=t.lote.vencimiento,
                        cantidad=t.cantidad,
                        devuelta=t.devuelta,
                    )
                    for t in x.lotes
                ],
                costo_unitario=x.costo_unitario if ver_costos else None,
                costo_total=x.costo_total if ver_costos else None,
                ingreso=x.ingreso,
                ganancia=x.ganancia if ver_costos else None,
                margen=margen,
                confianza=x.confianza,
            )
        )

    mermas = db.scalars(
        select(Ajuste).where(Ajuste.empresa_id == ctx.empresa_id, Ajuste.pedido_id == p.id)
    )
    devoluciones = db.scalars(
        select(Devolucion).where(Devolucion.pedido_id == p.id).order_by(Devolucion.numero)
    )
    por_id = {x.id: x for x in p.lineas}
    return PedidoDetalle(
        **resumen(p, ctx).model_dump(),
        emisor=p.emisor,
        observaciones=p.observaciones,
        detalle_lineas=lineas,
        detalle_documentos=[
            DocumentoSalida(
                id=d.archivo.id,
                nombre=d.archivo.nombre_original,
                tipo_mime=d.archivo.tipo_mime,
                tamano=d.archivo.tamano,
            )
            for d in _documentos_activos(p)
        ],
        eventos=[
            EventoSalida(
                tipo=e.tipo,
                usuario_nombre=e.usuario.nombre_completo,
                fecha=e.fecha,
                detalle=e.detalle,
            )
            for e in p.eventos
        ],
        validaciones=validaciones,
        mermas=[AjusteRef(id=a.id, numero=a.numero, estado=a.estado) for a in mermas],
        devoluciones=[
            DevolucionSalida(
                id=d.id,
                numero=d.numero,
                fecha=d.fecha,
                motivo=d.motivo,
                usuario_nombre=d.usuario.nombre_completo,
                lineas=[
                    DevolucionLineaSalida(
                        linea_id=dl.pedido_linea_id,
                        descripcion=por_id[dl.pedido_linea_id].descripcion_cliente,
                        cantidad=dl.cantidad,
                    )
                    for dl in d.lineas
                ],
            )
            for d in devoluciones
        ],
        anulacion_motivo=p.anulacion_motivo,
        anulado_desde=p.anulado_desde,
        receptor_nombre=p.receptor_nombre,
        entrega_observacion=p.entrega_observacion,
        constancia_foto_id=p.constancia_foto_id,
        constancia_firma_id=p.constancia_firma_id,
        entregado_at=p.entregado_at,
        ingreso=p.ingreso,
        costo=p.costo if ver_costos else None,
        confianza=p.confianza,
        lectura=LecturaSalida.model_validate(ultima, from_attributes=True)
        if (ultima := lectura.ultima(db, p.id))
        else None,
    )


def precision_lectura(db: Session, ctx: Contexto) -> list[PrecisionLectura]:
    """Precisión de la lectura automática por formato (lo que no hubo que corregir)."""
    filas = db.execute(
        select(
            Lectura.plantilla,
            func.count(),
            func.count(Lectura.precision),
            func.avg(Lectura.precision),
            func.avg(Lectura.confianza),
        )
        .where(Lectura.empresa_id == ctx.empresa_id, Lectura.estado == EstadoLectura.COMPLETADA)
        .group_by(Lectura.plantilla)
        .order_by(Lectura.plantilla)
    )
    return [
        PrecisionLectura(
            plantilla=plantilla or "—",
            lecturas=n,
            confirmadas=confirmadas,
            precision_promedio=round(precision, 2) if precision is not None else None,
            confianza_promedio=round(confianza, 2) if confianza is not None else None,
        )
        for plantilla, n, confirmadas, precision, confianza in filas
    ]


def reservado_por_pedidos(
    db: Session, empresa_id: uuid.UUID
) -> dict[tuple[uuid.UUID, uuid.UUID], Decimal]:
    """Lo que deberían sumar los comprometidos: pedidos CONFIRMADOS (para la verificación)."""
    filas = db.execute(
        select(
            Pedido.ubicacion_id,
            PedidoLinea.producto_id,
            func.sum(PedidoLinea.cantidad_confirmada),
        )
        .join(Pedido, Pedido.id == PedidoLinea.pedido_id)
        .where(
            and_(
                Pedido.empresa_id == empresa_id,
                Pedido.estado == EstadoPedido.CONFIRMADO,
                PedidoLinea.producto_id.is_not(None),
                PedidoLinea.cantidad_confirmada > 0,
            )
        )
        .group_by(Pedido.ubicacion_id, PedidoLinea.producto_id)
    )
    return {(ub, prod): cant for ub, prod, cant in filas if prod is not None}
