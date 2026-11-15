"""Casos de uso de finanzas: cobros, gastos, pagos a proveedores, impuestos y parámetros.

Cada caso de uso valida, modifica, audita y hace commit al final (una transacción).
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import eventos
from app.core.errors import Conflicto, NoEncontrado, ReglaNegocio
from app.core.tiempo import ahora, hoy
from app.modules.clientes.models import Cadena
from app.modules.compras.models import Compra, CondicionPago, EstadoCompra
from app.modules.documentos import servicios as documentos
from app.modules.documentos.models import Archivo
from app.modules.finanzas import cuentas, impuestos, parametros
from app.modules.finanzas.models import (
    CATEGORIAS_INICIALES,
    CategoriaGasto,
    Cobro,
    CobroDetalle,
    EstadoRegistro,
    Gasto,
)
from app.modules.finanzas.parametros import ParametrosFinanzas
from app.modules.finanzas.schemas import (
    CategoriaGastoEntrada,
    CategoriaGastoSalida,
    CobroDetalleCompleto,
    CobroDetalleSalida,
    CobroEntrada,
    CobroResumen,
    CompraPorPagar,
    CuentaSalida,
    GastoEntrada,
    GastoSalida,
    ImpuestoMes,
    PaginaGastos,
    PorCobrar,
    Ref,
    ResumenCadenaSalida,
    TotalCategoria,
)
from app.modules.identidad import auditoria
from app.modules.identidad.contexto import Contexto
from app.modules.organizacion import servicios as ubicaciones
from app.modules.pedidos.models import Pedido

CERO = Decimal(0)


def _bs(valor: Decimal) -> str:
    return f"Bs {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _texto(valor: str | None) -> str | None:
    return (valor or "").strip() or None


# ================================================================ por cobrar


def _cuenta_salida(c: cuentas.Cuenta, al: date) -> CuentaSalida:
    return CuentaSalida(
        pedido_id=c.pedido_id,
        numero=c.numero,
        numero_oc=c.numero_oc,
        cadena=Ref(id=c.cadena_id, nombre=c.cadena),
        sucursal=c.sucursal,
        fecha=c.fecha,
        vencimiento=c.vencimiento,
        monto=c.monto,
        cobrado=c.cobrado,
        diferencia=c.diferencia,
        saldo=c.saldo,
        estado=c.estado,
        dias_vencida=c.dias_vencida(al),
    )


def por_cobrar(
    db: Session, ctx: Contexto, *, cadena_id: uuid.UUID | None, todas: bool
) -> PorCobrar:
    """Saldos por cadena y cuentas pendientes (o todas, con `todas`)."""
    p = parametros.leer(db, ctx.empresa_id)
    al = hoy()
    lista = cuentas.cuentas(db, ctx.empresa_id, p.dias_credito, cadena_id=cadena_id)
    resumen = cuentas.por_cadena(lista, al)
    inicio = al.replace(day=1)
    cobrado_mes = db.scalar(
        select(func.coalesce(func.sum(Cobro.monto), 0)).where(
            Cobro.empresa_id == ctx.empresa_id,
            Cobro.estado == EstadoRegistro.REGISTRADO,
            Cobro.fecha >= inicio,
            *([Cobro.cadena_id == cadena_id] if cadena_id else []),
        )
    )
    return PorCobrar(
        total_pendiente=sum((r.pendiente for r in resumen), CERO),
        total_vencido=sum((r.vencido for r in resumen), CERO),
        cobrado_mes=cobrado_mes or CERO,
        cadenas=[
            ResumenCadenaSalida(
                cadena=Ref(id=r.cadena_id, nombre=r.cadena),
                pedidos_pendientes=r.pedidos_pendientes,
                pendiente=r.pendiente,
                vencido=r.vencido,
                a_favor=r.a_favor,
                mas_antiguo=r.mas_antiguo,
            )
            for r in resumen
        ],
        cuentas=[
            _cuenta_salida(c, al)
            for c in sorted(lista, key=lambda c: (c.fecha, c.numero), reverse=todas)
            if todas or c.saldo != 0
        ],
    )


# ================================================================ cobros


def _cadena(db: Session, ctx: Contexto, cadena_id: uuid.UUID) -> Cadena:
    cadena = db.get(Cadena, cadena_id)
    if cadena is None or cadena.empresa_id != ctx.empresa_id:
        raise NoEncontrado("La cadena no existe.")
    return cadena


def _bloquear_pedidos(db: Session, ctx: Contexto, ids: list[uuid.UUID]) -> None:
    """Bloquea los pedidos para que dos cobros simultáneos no paguen dos veces lo mismo."""
    encontrados = set(
        db.scalars(
            select(Pedido.id)
            .where(Pedido.id.in_(ids), Pedido.empresa_id == ctx.empresa_id)
            .order_by(Pedido.id)
            .with_for_update()
        )
    )
    if faltan := set(ids) - encontrados:
        raise NoEncontrado(f"{len(faltan)} pedido(s) del cobro no existen.")


def registrar_cobro(db: Session, ctx: Contexto, datos: CobroEntrada) -> Cobro:
    cadena = _cadena(db, ctx, datos.cadena_id)
    if datos.fecha > hoy():
        raise ReglaNegocio("La fecha del cobro no puede ser futura.")
    ids = [d.pedido_id for d in datos.detalles]
    if len(set(ids)) != len(ids):
        raise ReglaNegocio("Un pedido aparece dos veces en el cobro.")
    referencia = _texto(datos.referencia)
    if referencia and db.scalar(
        select(Cobro.numero).where(
            Cobro.empresa_id == ctx.empresa_id,
            Cobro.cadena_id == cadena.id,
            func.upper(Cobro.referencia) == referencia.upper(),
            Cobro.estado == EstadoRegistro.REGISTRADO,
        )
    ):
        raise Conflicto(
            f"Ya se registró una transferencia de {cadena.nombre} con el N.º de operación "
            f"{referencia}."
        )
    _bloquear_pedidos(db, ctx, ids)
    p = parametros.leer(db, ctx.empresa_id)
    por_pedido = {
        c.pedido_id: c for c in cuentas.cuentas(db, ctx.empresa_id, p.dias_credito, pedido_ids=ids)
    }

    detalles: list[CobroDetalle] = []
    for orden, d in enumerate(datos.detalles, start=1):
        cuenta = por_pedido.get(d.pedido_id)
        if cuenta is None:
            pedido = db.get(Pedido, d.pedido_id)
            numero = f"#{pedido.numero}" if pedido else ""
            raise ReglaNegocio(f"El pedido {numero} no está entregado: todavía no se puede cobrar.")
        if cuenta.cadena_id != cadena.id:
            raise ReglaNegocio(
                f"El pedido #{cuenta.numero} es de {cuenta.cadena}, no de {cadena.nombre}."
            )
        if cuenta.saldo <= 0:
            raise ReglaNegocio(f"El pedido #{cuenta.numero} ya está cobrado.")
        if d.monto > cuenta.saldo:
            raise ReglaNegocio(
                f"Al pedido #{cuenta.numero} se le aplican {_bs(d.monto)} pero solo debe "
                f"{_bs(cuenta.saldo)}."
            )
        diferencia = CERO
        motivo = _texto(d.motivo_diferencia)
        if d.cerrar_diferencia and d.monto < cuenta.saldo:
            if not motivo or len(motivo) < 3:
                raise ReglaNegocio(
                    f"Pedido #{cuenta.numero}: indique por qué se pagó menos (el motivo de la "
                    "diferencia)."
                )
            diferencia = cuenta.saldo - d.monto
        if d.monto + diferencia <= 0:
            raise ReglaNegocio(f"Pedido #{cuenta.numero}: el monto aplicado debe ser mayor a cero.")
        detalles.append(
            CobroDetalle(
                pedido_id=d.pedido_id,
                orden=orden,
                monto=d.monto,
                diferencia=diferencia,
                motivo_diferencia=motivo if diferencia > 0 else None,
            )
        )
    aplicado = sum((d.monto for d in detalles), CERO)
    if aplicado != datos.monto:
        raise ReglaNegocio(
            f"Lo aplicado a los pedidos ({_bs(aplicado)}) no coincide con el monto de la "
            f"transferencia ({_bs(datos.monto)})."
        )
    cobro = Cobro(
        empresa_id=ctx.empresa_id,
        cadena_id=cadena.id,
        fecha=datos.fecha,
        monto=datos.monto,
        banco=_texto(datos.banco),
        referencia=referencia,
        observaciones=_texto(datos.observaciones),
        usuario_id=ctx.usuario.id,
        detalles=detalles,
    )
    db.add(cobro)
    db.flush()
    _auditar_cobro(db, ctx, cobro, cadena, "cobro.registrar")
    db.commit()
    db.refresh(cobro)
    return cobro


def cerrar_saldo(db: Session, ctx: Contexto, pedido_id: uuid.UUID, motivo: str) -> Cobro:
    """Da por cerrado lo que falta cobrar de un pedido sin transferencia (error reconocido,
    D-28). Queda como un cobro de Bs 0 con la diferencia y su motivo; se puede anular."""
    _bloquear_pedidos(db, ctx, [pedido_id])
    p = parametros.leer(db, ctx.empresa_id)
    lista = cuentas.cuentas(db, ctx.empresa_id, p.dias_credito, pedido_ids=[pedido_id])
    if not lista:
        raise ReglaNegocio("El pedido no está entregado: no tiene saldo por cobrar.")
    cuenta = lista[0]
    if cuenta.saldo <= 0:
        raise ReglaNegocio(f"El pedido #{cuenta.numero} no tiene saldo pendiente.")
    cadena = _cadena(db, ctx, cuenta.cadena_id)
    cobro = Cobro(
        empresa_id=ctx.empresa_id,
        cadena_id=cadena.id,
        fecha=hoy(),
        monto=CERO,
        observaciones=f"Cierre de saldo del pedido #{cuenta.numero}",
        usuario_id=ctx.usuario.id,
        detalles=[
            CobroDetalle(
                pedido_id=pedido_id,
                orden=1,
                monto=CERO,
                diferencia=cuenta.saldo,
                motivo_diferencia=motivo.strip(),
            )
        ],
    )
    db.add(cobro)
    db.flush()
    _auditar_cobro(db, ctx, cobro, cadena, "cobro.cerrar_saldo")
    db.commit()
    db.refresh(cobro)
    return cobro


def _auditar_cobro(db: Session, ctx: Contexto, cobro: Cobro, cadena: Cadena, accion: str) -> None:
    datos = {
        "numero": cobro.numero,
        "cadena": cadena.nombre,
        "fecha": cobro.fecha,
        "monto": cobro.monto,
        "referencia": cobro.referencia,
        "pedidos": {
            str(d.pedido_id): {"monto": d.monto, "diferencia": d.diferencia} for d in cobro.detalles
        },
    }
    auditoria.registrar_ctx(
        db, ctx, accion=accion, entidad="cobro", entidad_id=cobro.id, despues=datos
    )
    eventos.publicar(
        db,
        empresa_id=ctx.empresa_id,
        tipo="CobroRegistrado",
        agregado="cobro",
        agregado_id=cobro.id,
        datos=datos,
    )


def obtener_cobro(db: Session, ctx: Contexto, cobro_id: uuid.UUID) -> Cobro:
    cobro = db.get(Cobro, cobro_id)
    if cobro is None or cobro.empresa_id != ctx.empresa_id:
        raise NoEncontrado("El cobro no existe.")
    return cobro


def anular_cobro(db: Session, ctx: Contexto, cobro_id: uuid.UUID, motivo: str) -> Cobro:
    cobro = obtener_cobro(db, ctx, cobro_id)
    if cobro.estado == EstadoRegistro.ANULADO:
        raise ReglaNegocio("El cobro ya está anulado.")
    _bloquear_pedidos(db, ctx, [d.pedido_id for d in cobro.detalles])
    cobro.estado = EstadoRegistro.ANULADO
    cobro.anulacion_motivo = motivo.strip()
    cobro.anulado_por_id = ctx.usuario.id
    cobro.anulado_at = ahora()
    auditoria.registrar_ctx(
        db,
        ctx,
        accion="cobro.anular",
        entidad="cobro",
        entidad_id=cobro.id,
        antes={"estado": EstadoRegistro.REGISTRADO},
        despues={"estado": cobro.estado, "motivo": cobro.anulacion_motivo},
    )
    eventos.publicar(
        db,
        empresa_id=ctx.empresa_id,
        tipo="CobroAnulado",
        agregado="cobro",
        agregado_id=cobro.id,
        datos={"numero": cobro.numero},
    )
    db.commit()
    return cobro


def adjuntar_comprobante_cobro(
    db: Session, ctx: Contexto, cobro_id: uuid.UUID, contenido: bytes, nombre: str | None
) -> Cobro:
    cobro = obtener_cobro(db, ctx, cobro_id)
    if cobro.estado == EstadoRegistro.ANULADO:
        raise ReglaNegocio("El cobro está anulado.")
    anterior = cobro.comprobante_id
    cobro.comprobante_id = documentos.guardar(db, ctx, contenido, nombre).id
    auditoria.registrar_ctx(
        db,
        ctx,
        accion="cobro.comprobante",
        entidad="cobro",
        entidad_id=cobro.id,
        antes={"comprobante_id": anterior},
        despues={"comprobante_id": cobro.comprobante_id},
    )
    db.commit()
    db.refresh(cobro)
    return cobro


def listar_cobros(
    db: Session,
    ctx: Contexto,
    *,
    cadena_id: uuid.UUID | None,
    desde: date | None,
    hasta: date | None,
    pagina: int,
    tamano: int,
) -> tuple[list[CobroResumen], int]:
    filtros = [Cobro.empresa_id == ctx.empresa_id]
    if cadena_id:
        filtros.append(Cobro.cadena_id == cadena_id)
    if desde:
        filtros.append(Cobro.fecha >= desde)
    if hasta:
        filtros.append(Cobro.fecha <= hasta)
    total = db.scalar(select(func.count()).select_from(Cobro).where(*filtros)) or 0
    cobros = db.scalars(
        select(Cobro)
        .where(*filtros)
        .order_by(Cobro.fecha.desc(), Cobro.numero.desc())
        .offset((pagina - 1) * tamano)
        .limit(tamano)
    )
    return [cobro_resumen(c) for c in cobros], total


def cobro_resumen(c: Cobro) -> CobroResumen:
    return CobroResumen(
        id=c.id,
        numero=c.numero,
        cadena=Ref(id=c.cadena.id, nombre=c.cadena.nombre),
        fecha=c.fecha,
        monto=c.monto,
        diferencias=sum((d.diferencia for d in c.detalles), CERO),
        banco=c.banco,
        referencia=c.referencia,
        estado=c.estado,
        es_cierre=c.monto == 0,
        pedidos=len(c.detalles),
        usuario_nombre=c.usuario.nombre_completo,
        created_at=c.created_at,
    )


def cobro_detalle(db: Session, c: Cobro) -> CobroDetalleCompleto:
    pedidos = {
        p.id: p
        for p in db.scalars(select(Pedido).where(Pedido.id.in_([d.pedido_id for d in c.detalles])))
    }
    return CobroDetalleCompleto(
        **cobro_resumen(c).model_dump(),
        observaciones=c.observaciones,
        comprobante_id=c.comprobante_id,
        comprobante_nombre=c.comprobante.nombre_original if c.comprobante else None,
        anulacion_motivo=c.anulacion_motivo,
        anulado_at=c.anulado_at,
        detalles=[
            CobroDetalleSalida(
                pedido_id=d.pedido_id,
                pedido_numero=pedidos[d.pedido_id].numero,
                numero_oc=pedidos[d.pedido_id].numero_oc,
                sucursal=s.nombre if (s := pedidos[d.pedido_id].sucursal_cliente) else None,
                monto=d.monto,
                diferencia=d.diferencia,
                motivo_diferencia=d.motivo_diferencia,
            )
            for d in c.detalles
        ],
    )


# ================================================================ categorías de gasto


def asegurar_categorias(db: Session, empresa_id: uuid.UUID) -> None:
    """Crea las categorías iniciales (D-31) si la empresa no tiene ninguna (sin commit)."""
    if db.scalar(select(func.count()).where(CategoriaGasto.empresa_id == empresa_id)):
        return
    for nombre, factura in CATEGORIAS_INICIALES:
        db.add(CategoriaGasto(empresa_id=empresa_id, nombre=nombre, factura_habitual=factura))
    db.flush()


def _categoria_salida(c: CategoriaGasto) -> CategoriaGastoSalida:
    return CategoriaGastoSalida(
        id=c.id, nombre=c.nombre, factura_habitual=c.factura_habitual, activo=c.activo
    )


def listar_categorias(db: Session, ctx: Contexto) -> list[CategoriaGastoSalida]:
    return [
        _categoria_salida(c)
        for c in db.scalars(
            select(CategoriaGasto)
            .where(CategoriaGasto.empresa_id == ctx.empresa_id)
            .order_by(CategoriaGasto.activo.desc(), CategoriaGasto.nombre)
        )
    ]


def _nombre_libre(
    db: Session, ctx: Contexto, nombre: str, excepto: uuid.UUID | None = None
) -> None:
    otra = db.scalar(
        select(CategoriaGasto.id).where(
            CategoriaGasto.empresa_id == ctx.empresa_id,
            func.lower(CategoriaGasto.nombre) == nombre.lower(),
        )
    )
    if otra and otra != excepto:
        raise Conflicto(f"Ya existe la categoría «{nombre}».")


def crear_categoria(
    db: Session, ctx: Contexto, datos: CategoriaGastoEntrada
) -> CategoriaGastoSalida:
    nombre = datos.nombre.strip()
    _nombre_libre(db, ctx, nombre)
    categoria = CategoriaGasto(
        empresa_id=ctx.empresa_id,
        nombre=nombre,
        factura_habitual=datos.factura_habitual,
        activo=datos.activo,
    )
    db.add(categoria)
    db.flush()
    auditoria.registrar_ctx(
        db,
        ctx,
        accion="categoria_gasto.crear",
        entidad="categoria_gasto",
        entidad_id=categoria.id,
        despues=datos.model_dump(),
    )
    db.commit()
    return _categoria_salida(categoria)


def editar_categoria(
    db: Session, ctx: Contexto, categoria_id: uuid.UUID, datos: CategoriaGastoEntrada
) -> CategoriaGastoSalida:
    categoria = _obtener_categoria(db, ctx, categoria_id)
    nombre = datos.nombre.strip()
    _nombre_libre(db, ctx, nombre, excepto=categoria.id)
    antes = _categoria_salida(categoria).model_dump(exclude={"id"})
    categoria.nombre = nombre
    categoria.factura_habitual = datos.factura_habitual
    categoria.activo = datos.activo
    auditoria.registrar_ctx(
        db,
        ctx,
        accion="categoria_gasto.editar",
        entidad="categoria_gasto",
        entidad_id=categoria.id,
        antes=antes,
        despues=datos.model_dump(),
    )
    db.commit()
    return _categoria_salida(categoria)


def _obtener_categoria(db: Session, ctx: Contexto, categoria_id: uuid.UUID) -> CategoriaGasto:
    categoria = db.get(CategoriaGasto, categoria_id)
    if categoria is None or categoria.empresa_id != ctx.empresa_id:
        raise NoEncontrado("La categoría de gasto no existe.")
    return categoria


# ================================================================ gastos


def registrar_gasto(db: Session, ctx: Contexto, datos: GastoEntrada) -> Gasto:
    if datos.fecha > hoy():
        raise ReglaNegocio("La fecha del gasto no puede ser futura.")
    categoria = _obtener_categoria(db, ctx, datos.categoria_id)
    if not categoria.activo:
        raise ReglaNegocio(f"La categoría «{categoria.nombre}» está inactiva.")
    ubicacion = ubicaciones.obtener(db, ctx, datos.ubicacion_id) if datos.ubicacion_id else None
    gasto = Gasto(
        empresa_id=ctx.empresa_id,
        fecha=datos.fecha,
        categoria_id=categoria.id,
        ubicacion_id=ubicacion.id if ubicacion else None,
        beneficiario=_texto(datos.beneficiario),
        descripcion=_texto(datos.descripcion),
        monto=datos.monto,
        con_factura=datos.con_factura,
        numero_factura=_texto(datos.numero_factura) if datos.con_factura else None,
        usuario_id=ctx.usuario.id,
    )
    db.add(gasto)
    db.flush()
    auditoria.registrar_ctx(
        db,
        ctx,
        accion="gasto.registrar",
        entidad="gasto",
        entidad_id=gasto.id,
        despues={
            "numero": gasto.numero,
            "fecha": gasto.fecha,
            "categoria": categoria.nombre,
            "ubicacion": ubicacion.nombre if ubicacion else None,
            "beneficiario": gasto.beneficiario,
            "monto": gasto.monto,
            "con_factura": gasto.con_factura,
        },
    )
    eventos.publicar(
        db,
        empresa_id=ctx.empresa_id,
        tipo="GastoRegistrado",
        agregado="gasto",
        agregado_id=gasto.id,
        datos={"numero": gasto.numero, "monto": gasto.monto, "categoria": categoria.nombre},
    )
    db.commit()
    db.refresh(gasto)
    return gasto


def obtener_gasto(db: Session, ctx: Contexto, gasto_id: uuid.UUID) -> Gasto:
    gasto = db.get(Gasto, gasto_id)
    if gasto is None or gasto.empresa_id != ctx.empresa_id:
        raise NoEncontrado("El gasto no existe.")
    return gasto


def anular_gasto(db: Session, ctx: Contexto, gasto_id: uuid.UUID, motivo: str) -> Gasto:
    gasto = obtener_gasto(db, ctx, gasto_id)
    if gasto.estado == EstadoRegistro.ANULADO:
        raise ReglaNegocio("El gasto ya está anulado.")
    gasto.estado = EstadoRegistro.ANULADO
    gasto.anulacion_motivo = motivo.strip()
    gasto.anulado_por_id = ctx.usuario.id
    gasto.anulado_at = ahora()
    auditoria.registrar_ctx(
        db,
        ctx,
        accion="gasto.anular",
        entidad="gasto",
        entidad_id=gasto.id,
        antes={"estado": EstadoRegistro.REGISTRADO},
        despues={"estado": gasto.estado, "motivo": gasto.anulacion_motivo},
    )
    eventos.publicar(
        db,
        empresa_id=ctx.empresa_id,
        tipo="GastoAnulado",
        agregado="gasto",
        agregado_id=gasto.id,
        datos={"numero": gasto.numero},
    )
    db.commit()
    return gasto


def adjuntar_comprobante_gasto(
    db: Session, ctx: Contexto, gasto_id: uuid.UUID, contenido: bytes, nombre: str | None
) -> Gasto:
    gasto = obtener_gasto(db, ctx, gasto_id)
    if gasto.estado == EstadoRegistro.ANULADO:
        raise ReglaNegocio("El gasto está anulado.")
    anterior = gasto.comprobante_id
    gasto.comprobante_id = documentos.guardar(db, ctx, contenido, nombre).id
    auditoria.registrar_ctx(
        db,
        ctx,
        accion="gasto.comprobante",
        entidad="gasto",
        entidad_id=gasto.id,
        antes={"comprobante_id": anterior},
        despues={"comprobante_id": gasto.comprobante_id},
    )
    db.commit()
    db.refresh(gasto)
    return gasto


def gasto_salida(g: Gasto) -> GastoSalida:
    return GastoSalida(
        id=g.id,
        numero=g.numero,
        fecha=g.fecha,
        categoria=Ref(id=g.categoria.id, nombre=g.categoria.nombre),
        ubicacion=Ref(id=g.ubicacion.id, nombre=g.ubicacion.nombre) if g.ubicacion else None,
        beneficiario=g.beneficiario,
        descripcion=g.descripcion,
        monto=g.monto,
        con_factura=g.con_factura,
        numero_factura=g.numero_factura,
        comprobante_id=g.comprobante_id,
        comprobante_nombre=g.comprobante.nombre_original if g.comprobante else None,
        estado=g.estado,
        anulacion_motivo=g.anulacion_motivo,
        usuario_nombre=g.usuario.nombre_completo,
        created_at=g.created_at,
    )


def listar_gastos(
    db: Session,
    ctx: Contexto,
    *,
    desde: date | None,
    hasta: date | None,
    categoria_id: uuid.UUID | None,
    ubicacion_id: uuid.UUID | None,
    buscar: str | None,
    pagina: int,
    tamano: int,
) -> PaginaGastos:
    filtros = [Gasto.empresa_id == ctx.empresa_id]
    if desde:
        filtros.append(Gasto.fecha >= desde)
    if hasta:
        filtros.append(Gasto.fecha <= hasta)
    if categoria_id:
        filtros.append(Gasto.categoria_id == categoria_id)
    if ubicacion_id:
        filtros.append(Gasto.ubicacion_id == ubicacion_id)
    if buscar and (texto := buscar.strip()):
        patron = f"%{texto}%"
        filtros.append(Gasto.beneficiario.ilike(patron) | Gasto.descripcion.ilike(patron))
    total = db.scalar(select(func.count()).select_from(Gasto).where(*filtros)) or 0
    gastos = db.scalars(
        select(Gasto)
        .where(*filtros)
        .order_by(Gasto.fecha.desc(), Gasto.numero.desc())
        .offset((pagina - 1) * tamano)
        .limit(tamano)
    )
    vigentes = [*filtros, Gasto.estado == EstadoRegistro.REGISTRADO]
    por_categoria = [
        TotalCategoria(categoria=Ref(id=cid, nombre=nombre), total=suma)
        for cid, nombre, suma in db.execute(
            select(CategoriaGasto.id, CategoriaGasto.nombre, func.sum(Gasto.monto))
            .join(CategoriaGasto, CategoriaGasto.id == Gasto.categoria_id)
            .where(*vigentes)
            .group_by(CategoriaGasto.id, CategoriaGasto.nombre)
            .order_by(func.sum(Gasto.monto).desc())
        )
    ]
    return PaginaGastos(
        items=[gasto_salida(g) for g in gastos],
        total=total,
        pagina=pagina,
        tamano=tamano,
        suma=sum((x.total for x in por_categoria), CERO),
        por_categoria=por_categoria,
    )


def archivo_de(db: Session, ctx: Contexto, archivo_id: uuid.UUID) -> Archivo:
    """Comprobante de un cobro o de un gasto (solo esos; los demás archivos tienen su ruta)."""
    usado = db.scalar(
        select(func.count()).where(
            Cobro.comprobante_id == archivo_id, Cobro.empresa_id == ctx.empresa_id
        )
    ) or db.scalar(
        select(func.count()).where(
            Gasto.comprobante_id == archivo_id, Gasto.empresa_id == ctx.empresa_id
        )
    )
    if not usado:
        raise NoEncontrado("El comprobante no existe.")
    return documentos.obtener(db, ctx, archivo_id)


# ================================================================ por pagar


def por_pagar(db: Session, ctx: Contexto) -> list[CompraPorPagar]:
    """Compras a crédito todavía sin pagar (son raras: casi todo es al contado, D-29)."""
    al = hoy()
    compras = db.scalars(
        select(Compra)
        .where(
            Compra.empresa_id == ctx.empresa_id,
            Compra.estado == EstadoCompra.REGISTRADA,
            Compra.condicion_pago == CondicionPago.CREDITO,
            Compra.fecha_pago.is_(None),
        )
        .order_by(Compra.fecha_vencimiento.nulls_last(), Compra.fecha)
    )
    return [
        CompraPorPagar(
            id=c.id,
            numero=c.numero,
            fecha=c.fecha,
            proveedor=Ref(id=c.proveedor.id, nombre=c.proveedor.nombre),
            numero_documento=c.numero_documento,
            total=c.total,
            fecha_vencimiento=c.fecha_vencimiento,
            dias_para_vencer=(c.fecha_vencimiento - al).days if c.fecha_vencimiento else None,
        )
        for c in compras
    ]


def pagar_compra(db: Session, ctx: Contexto, compra_id: uuid.UUID, fecha: date) -> Compra:
    compra = db.get(Compra, compra_id)
    if compra is None or compra.empresa_id != ctx.empresa_id:
        raise NoEncontrado("La compra no existe.")
    if compra.estado == EstadoCompra.ANULADA:
        raise ReglaNegocio("La compra está anulada.")
    if compra.fecha_pago is not None:
        raise ReglaNegocio(f"La compra #{compra.numero} ya está pagada.")
    if fecha > hoy():
        raise ReglaNegocio("La fecha del pago no puede ser futura.")
    if fecha < compra.fecha:
        raise ReglaNegocio("La fecha del pago no puede ser anterior a la de la compra.")
    compra.fecha_pago = fecha
    compra.pago_registrado_por_id = ctx.usuario.id
    auditoria.registrar_ctx(
        db,
        ctx,
        accion="compra.pagar",
        entidad="compra",
        entidad_id=compra.id,
        antes={"fecha_pago": None},
        despues={"fecha_pago": fecha, "total": compra.total},
    )
    eventos.publicar(
        db,
        empresa_id=ctx.empresa_id,
        tipo="CompraPagada",
        agregado="compra",
        agregado_id=compra.id,
        datos={"numero": compra.numero, "total": compra.total, "fecha": fecha},
    )
    db.commit()
    return compra


# ================================================================ impuestos y parámetros


def impuestos_mensuales(db: Session, ctx: Contexto, desde: date, hasta: date) -> list[ImpuestoMes]:
    if hasta < desde:
        raise ReglaNegocio("La fecha «hasta» no puede ser anterior a «desde».")
    if (hasta - desde).days > 3660:
        raise ReglaNegocio("El rango de fechas es demasiado grande (máximo 10 años).")
    return impuestos.mensual(db, ctx.empresa_id, parametros.leer(db, ctx.empresa_id), desde, hasta)


def guardar_parametros(
    db: Session, ctx: Contexto, nuevos: ParametrosFinanzas
) -> ParametrosFinanzas:
    antes = parametros.leer(db, ctx.empresa_id)
    parametros.guardar(db, ctx.empresa_id, nuevos)
    auditoria.registrar_ctx(
        db,
        ctx,
        accion="finanzas.parametros",
        entidad="empresa",
        entidad_id=ctx.empresa_id,
        antes=antes.model_dump(mode="json"),
        despues=nuevos.model_dump(mode="json"),
    )
    db.commit()
    return nuevos
