import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import ColumnElement, exists, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.errors import NoEncontrado, ReglaNegocio
from app.core.schemas import Pagina
from app.core.tiempo import ahora
from app.modules.alertas import parametros, pronostico, reglas, reposicion
from app.modules.alertas.models import Alerta, AlertaLeida, EstadoAlerta, Pronostico, Severidad
from app.modules.alertas.parametros import Parametros
from app.modules.alertas.schemas import (
    AlertaSalida,
    FilaReposicion,
    PronosticoSalida,
    Referencia,
    ResultadoEvaluacion,
    ResumenAlertas,
    SugerenciaCompraSalida,
    SugerenciaTransferenciaSalida,
)
from app.modules.catalogo.models import Producto
from app.modules.identidad import auditoria
from app.modules.identidad.contexto import Contexto
from app.modules.identidad.models import Usuario
from app.modules.organizacion.models import Ubicacion

# ================================================================ alertas


def _visibles(ctx: Contexto) -> list[ColumnElement[bool]]:
    """Cada alerta exige un permiso; las de una ubicación, además, acceso a esa ubicación."""
    condiciones: list[ColumnElement[bool]] = [
        Alerta.empresa_id == ctx.empresa_id,
        Alerta.permiso.in_(sorted(ctx.usuario.permisos)),
    ]
    if not ctx.puede("ubicaciones.todas"):
        propias = [u.id for u in ctx.usuario.ubicaciones]
        condiciones.append(or_(Alerta.ubicacion_id.is_(None), Alerta.ubicacion_id.in_(propias)))
    return condiciones


def _leida(ctx: Contexto) -> ColumnElement[bool]:
    return exists().where(
        AlertaLeida.alerta_id == Alerta.id, AlertaLeida.usuario_id == ctx.usuario.id
    )


def listar(
    db: Session,
    ctx: Contexto,
    *,
    estado: EstadoAlerta | None,
    severidad: Severidad | None,
    tipo: str | None,
    solo_no_leidas: bool,
    pagina: int,
    tamano: int,
) -> Pagina[AlertaSalida]:
    condiciones = _visibles(ctx)
    if estado:
        condiciones.append(Alerta.estado == estado)
    if severidad:
        condiciones.append(Alerta.severidad == severidad)
    if tipo:
        condiciones.append(Alerta.tipo == tipo)
    if solo_no_leidas:
        condiciones.append(~_leida(ctx))
    total = db.scalar(select(func.count()).select_from(Alerta).where(*condiciones)) or 0
    orden_severidad = func.array_position(["CRITICA", "AVISO", "INFO"], Alerta.severidad)
    filas = db.execute(
        select(Alerta, _leida(ctx), Ubicacion.nombre, Producto.nombre, Usuario.nombre)
        .outerjoin(Ubicacion, Ubicacion.id == Alerta.ubicacion_id)
        .outerjoin(Producto, Producto.id == Alerta.producto_id)
        .outerjoin(Usuario, Usuario.id == Alerta.resuelta_por_id)
        .where(*condiciones)
        .order_by(Alerta.estado, orden_severidad, Alerta.creada_at.desc())
        .offset((pagina - 1) * tamano)
        .limit(tamano)
    ).all()
    return Pagina(
        items=[
            AlertaSalida(
                id=a.id,
                tipo=a.tipo,
                severidad=a.severidad,
                titulo=a.titulo,
                mensaje=a.mensaje,
                enlace=a.enlace,
                ubicacion=ub,
                producto=prod,
                datos=a.datos
                if ctx.puede("costos.ver")
                else {k: v for k, v in a.datos.items() if k != "valor"},
                auto_resolver=a.auto_resolver,
                estado=a.estado,
                creada_at=a.creada_at,
                resuelta_at=a.resuelta_at,
                resuelta_por=usuario,
                leida=leida,
            )
            for a, leida, ub, prod, usuario in filas
        ],
        total=total,
        pagina=pagina,
        tamano=tamano,
    )


def resumen(db: Session, ctx: Contexto) -> ResumenAlertas:
    activas = [*_visibles(ctx), Alerta.estado == EstadoAlerta.ACTIVA]
    no_leidas = (
        db.scalar(select(func.count()).select_from(Alerta).where(*activas, ~_leida(ctx))) or 0
    )
    criticas = (
        db.scalar(
            select(func.count())
            .select_from(Alerta)
            .where(*activas, Alerta.severidad == Severidad.CRITICA)
        )
        or 0
    )
    return ResumenAlertas(no_leidas=no_leidas, criticas=criticas)


def marcar_leidas(db: Session, ctx: Contexto, ids: list[uuid.UUID] | None) -> int:
    condiciones = [*_visibles(ctx), ~_leida(ctx)]
    if ids is None:
        condiciones.append(Alerta.estado == EstadoAlerta.ACTIVA)
    else:
        condiciones.append(Alerta.id.in_(ids))
    pendientes = list(db.scalars(select(Alerta.id).where(*condiciones)))
    if pendientes:
        db.execute(
            pg_insert(AlertaLeida)
            .values([{"alerta_id": i, "usuario_id": ctx.usuario.id} for i in pendientes])
            .on_conflict_do_nothing()
        )
    db.commit()
    return len(pendientes)


def atender(db: Session, ctx: Contexto, alerta_id: uuid.UUID) -> None:
    """Marca como atendida una alerta de evento (margen bajo, anomalía…). Las de estado se
    resuelven solas al corregir la causa."""
    alerta = db.scalar(select(Alerta).where(*_visibles(ctx), Alerta.id == alerta_id))
    if alerta is None:
        raise NoEncontrado("La alerta no existe.")
    if alerta.auto_resolver:
        raise ReglaNegocio(
            "Esta alerta se cierra sola cuando se corrige la causa (por ejemplo, al reponer stock)."
        )
    if alerta.estado == EstadoAlerta.RESUELTA:
        raise ReglaNegocio("La alerta ya fue atendida.")
    alerta.estado, alerta.resuelta_at, alerta.resuelta_por_id = (
        EstadoAlerta.RESUELTA,
        ahora(),
        ctx.usuario.id,
    )
    db.execute(
        pg_insert(AlertaLeida)
        .values(alerta_id=alerta.id, usuario_id=ctx.usuario.id)
        .on_conflict_do_nothing()
    )
    auditoria.registrar_ctx(
        db,
        ctx,
        accion="alerta.atender",
        entidad="alerta",
        entidad_id=alerta.id,
        despues={"tipo": alerta.tipo, "titulo": alerta.titulo},
    )
    db.commit()


def evaluar_ahora(
    db: Session, ctx: Contexto, *, recalcular_pronostico: bool
) -> ResultadoEvaluacion:
    hay = db.scalar(
        select(func.count()).select_from(Pronostico).where(Pronostico.empresa_id == ctx.empresa_id)
    )
    cantidad = pronostico.recalcular(db, ctx.empresa_id) if recalcular_pronostico or not hay else 0
    r = reglas.evaluar(db, ctx.empresa_id)
    return ResultadoEvaluacion(**r, pronosticos=cantidad)


# ================================================================ parámetros


def leer_parametros(db: Session, ctx: Contexto) -> Parametros:
    return parametros.leer(db, ctx.empresa_id)


def guardar_parametros(db: Session, ctx: Contexto, nuevos: Parametros) -> Parametros:
    antes = parametros.leer(db, ctx.empresa_id)
    parametros.guardar(db, ctx.empresa_id, nuevos)
    auditoria.registrar_ctx(
        db,
        ctx,
        accion="configuracion.alertas",
        entidad="empresa",
        entidad_id=ctx.empresa_id,
        antes=antes.model_dump(),
        despues=nuevos.model_dump(),
    )
    db.commit()
    reglas.evaluar(db, ctx.empresa_id)  # los avisos reflejan enseguida los nuevos umbrales
    return nuevos


# ================================================================ reposición


def _fila(f: reposicion.FilaPlan) -> dict[str, Any]:
    return {
        "ubicacion": Referencia(id=f.ubicacion.id, nombre=f.ubicacion.nombre),
        "producto": Referencia(id=f.producto.id, nombre=f.producto.nombre),
        "sku": f.producto.sku,
        "unidad": f.producto.unidad_base,
        "disponible": f.disponible,
        "demanda_semanal": f.demanda_semanal,
        "cobertura_dias": f.plan.cobertura_dias,
        "stock_seguridad": f.plan.stock_seguridad,
        "punto_reorden": f.plan.punto_reorden,
        "objetivo": f.plan.objetivo,
        "confianza": f.confianza,
        "metodo": f.metodo,
        "semanas": f.semanas,
        "con_limites": f.minimo is not None or f.maximo is not None,
    }


def _plan(db: Session, ctx: Contexto) -> reposicion.Planificacion:
    return reposicion.planificar(db, ctx.empresa_id, parametros.leer(db, ctx.empresa_id))


def transferencias(db: Session, ctx: Contexto) -> list[SugerenciaTransferenciaSalida]:
    resultado = []
    for s in reposicion.sugerir_transferencias(_plan(db, ctx)):
        origen = s.fila.origen
        assert origen is not None  # sin origen no se sugiere
        resultado.append(
            SugerenciaTransferenciaSalida(
                **_fila(s.fila),
                origen=Referencia(id=origen.id, nombre=origen.nombre),
                origen_disponible=s.origen_disponible,
                cantidad=s.cantidad,
                presentacion=s.presentacion,
                cantidad_presentacion=s.cantidad_presentacion,
                insuficiente=s.insuficiente,
            )
        )
    return resultado


def compras(db: Session, ctx: Contexto) -> list[SugerenciaCompraSalida]:
    ver_costos = ctx.puede("costos.ver")
    return [
        SugerenciaCompraSalida(
            **_fila(s.fila),
            proveedor=Referencia(id=s.fila.proveedor.id, nombre=s.fila.proveedor.nombre)
            if s.fila.proveedor
            else None,
            dias_entrega=s.fila.dias_reposicion,
            fecha=s.fecha,
            cantidad=s.cantidad,
            presentacion=s.presentacion,
            cantidad_presentacion=s.cantidad_presentacion,
            costo_estimado=(
                (s.cantidad * s.fila.ultimo_costo).quantize(Decimal("0.01"))
                if ver_costos and s.fila.ultimo_costo is not None
                else None
            ),
        )
        for s in reposicion.sugerir_compras(_plan(db, ctx))
    ]


def plan_completo(db: Session, ctx: Contexto) -> list[FilaReposicion]:
    plan = _plan(db, ctx)
    return [FilaReposicion(**_fila(f)) for f in plan.todas()]


def pronostico_de(db: Session, ctx: Contexto, producto_id: uuid.UUID) -> list[PronosticoSalida]:
    filas = db.execute(
        select(Pronostico, Ubicacion.nombre, Producto.nombre)
        .join(Ubicacion, Ubicacion.id == Pronostico.ubicacion_id)
        .join(Producto, Producto.id == Pronostico.producto_id)
        .where(Pronostico.empresa_id == ctx.empresa_id, Pronostico.producto_id == producto_id)
        .order_by(Ubicacion.nombre)
    ).all()
    return [
        PronosticoSalida(
            producto=Referencia(id=p.producto_id, nombre=prod),
            ubicacion=Referencia(id=p.ubicacion_id, nombre=ub),
            metodo=p.metodo,
            confianza=p.confianza,
            semanas=p.semanas,
            demanda_semanal=p.demanda_semanal,
            error_medio=p.error_medio,
            historial=p.historial,
            calculado_at=p.calculado_at,
        )
        for p, ub, prod in filas
    ]
