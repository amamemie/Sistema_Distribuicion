"""Plan de reposición en dos niveles (spec 3.5 y 4.3).

- Sucursal: se repone desde el depósito que la abastece, que se deduce de las transferencias
  registradas (el origen más frecuente); si no hay historial, el depósito con más stock.
- Depósito: su demanda es la de las sucursales que abastece; se repone comprando al proveedor
  (el de la última compra del producto o, si no hay, uno de los asociados al producto).
"""

import math
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_FLOOR, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from app.core.tiempo import hoy
from app.modules.alertas import dominio
from app.modules.alertas.models import Confianza, Pronostico
from app.modules.alertas.parametros import Parametros
from app.modules.catalogo.models import LimiteStock, Presentacion, Producto
from app.modules.compras.models import Compra, CompraLinea, EstadoCompra
from app.modules.inventario.models import EstadoDocumento, StockUbicacion, Transferencia
from app.modules.organizacion.models import TipoUbicacion, Ubicacion
from app.modules.proveedores.models import Proveedor, proveedor_producto

CERO = Decimal(0)
_ORDEN_CONFIANZA = {Confianza.BAJA: 0, Confianza.MEDIA: 1, Confianza.ALTA: 2}


@dataclass
class FilaPlan:
    ubicacion: Ubicacion
    producto: Producto
    fisico: Decimal
    disponible: Decimal
    demanda_semanal: Decimal
    desviacion_semanal: Decimal
    confianza: Confianza
    metodo: str
    semanas: int
    plan: dominio.Plan
    minimo: Decimal | None
    maximo: Decimal | None
    origen: Ubicacion | None = None  # sucursal: depósito que la abastece
    proveedor: Proveedor | None = None  # depósito: a quién comprar
    dias_reposicion: int = 0
    ultimo_costo: Decimal | None = None
    presentaciones: list[tuple[str, Decimal]] = field(default_factory=list)

    @property
    def con_demanda(self) -> bool:
        return self.demanda_semanal > 0 or self.minimo is not None


@dataclass
class Planificacion:
    sucursales: list[FilaPlan]
    depositos: list[FilaPlan]

    def todas(self) -> list[FilaPlan]:
        return self.sucursales + self.depositos


def _origenes(db: Session, empresa_id: uuid.UUID) -> dict[uuid.UUID, uuid.UUID]:
    """Depósito que abastece a cada sucursal: el origen más frecuente de sus transferencias."""
    conteo: dict[uuid.UUID, Counter[uuid.UUID]] = defaultdict(Counter)
    origen = aliased(Ubicacion)
    for destino_id, origen_id, veces in db.execute(
        select(Transferencia.destino_id, Transferencia.origen_id, func.count())
        .join(origen, origen.id == Transferencia.origen_id)
        .where(
            Transferencia.empresa_id == empresa_id,
            Transferencia.estado != EstadoDocumento.ANULADA,
            origen.tipo == TipoUbicacion.DEPOSITO,
        )
        .group_by(Transferencia.destino_id, Transferencia.origen_id)
    ):
        conteo[destino_id][origen_id] += veces
    return {destino: c.most_common(1)[0][0] for destino, c in conteo.items()}


def planificar(db: Session, empresa_id: uuid.UUID, p: Parametros) -> Planificacion:
    ubicaciones = {
        u.id: u
        for u in db.scalars(
            select(Ubicacion).where(Ubicacion.empresa_id == empresa_id, Ubicacion.activo.is_(True))
        )
    }
    productos = {
        x.id: x
        for x in db.scalars(
            select(Producto).where(Producto.empresa_id == empresa_id, Producto.activo.is_(True))
        )
    }
    presentaciones: dict[uuid.UUID, list[tuple[str, Decimal]]] = defaultdict(list)
    for pres in db.scalars(
        select(Presentacion).where(
            Presentacion.producto_id.in_(productos), Presentacion.activo.is_(True)
        )
    ):
        presentaciones[pres.producto_id].append((pres.nombre, pres.factor))
    saldos = {
        (s.ubicacion_id, s.producto_id): s
        for s in db.scalars(select(StockUbicacion).where(StockUbicacion.empresa_id == empresa_id))
    }
    limites = {
        (lim.ubicacion_id, lim.producto_id): lim
        for lim in db.scalars(select(LimiteStock).where(LimiteStock.producto_id.in_(productos)))
    }
    pronosticos = {
        (x.ubicacion_id, x.producto_id): x
        for x in db.scalars(select(Pronostico).where(Pronostico.empresa_id == empresa_id))
    }
    origenes = _origenes(db, empresa_id)
    depositos = [u for u in ubicaciones.values() if u.tipo == TipoUbicacion.DEPOSITO]

    def disponible(ub: uuid.UUID, prod: uuid.UUID) -> Decimal:
        s = saldos.get((ub, prod))
        return (s.fisico - s.comprometido) if s else CERO

    def fila(
        ub: Ubicacion,
        prod: Producto,
        demanda: Decimal,
        desvio: Decimal,
        confianza: Confianza,
        metodo: str,
        semanas: int,
        dias_rep: int,
        cobertura: int,
    ) -> FilaPlan:
        s = saldos.get((ub.id, prod.id))
        lim = limites.get((ub.id, prod.id))
        disp = disponible(ub.id, prod.id)
        return FilaPlan(
            ubicacion=ub,
            producto=prod,
            fisico=s.fisico if s else CERO,
            disponible=disp,
            demanda_semanal=demanda,
            desviacion_semanal=desvio,
            confianza=confianza,
            metodo=metodo,
            semanas=semanas,
            plan=dominio.planificar(
                demanda_semanal=demanda,
                desviacion_semanal=desvio,
                disponible=disp,
                dias_reposicion=dias_rep,
                dias_cobertura=cobertura,
                minimo=lim.minimo if lim else None,
                maximo=lim.maximo if lim else None,
            ),
            minimo=lim.minimo if lim else None,
            maximo=lim.maximo if lim else None,
            dias_reposicion=dias_rep,
            presentaciones=presentaciones.get(prod.id, []),
        )

    # --- sucursales
    filas_suc: list[FilaPlan] = []
    for ub in ubicaciones.values():
        if ub.tipo != TipoUbicacion.SUCURSAL:
            continue
        for prod in productos.values():
            pr = pronosticos.get((ub.id, prod.id))
            if pr is None and (ub.id, prod.id) not in saldos and (ub.id, prod.id) not in limites:
                continue
            f = fila(
                ub,
                prod,
                pr.demanda_semanal if pr else CERO,
                pr.desviacion_semanal if pr else CERO,
                Confianza(pr.confianza) if pr else Confianza.BAJA,
                pr.metodo if pr else "sin ventas",
                pr.semanas if pr else 0,
                p.dias_reposicion_sucursal,
                p.cobertura_sucursal_dias,
            )
            origen_id = origenes.get(ub.id)
            if origen_id is None and depositos:
                origen_id = max(depositos, key=lambda d: disponible(d.id, prod.id)).id
            f.origen = ubicaciones.get(origen_id) if origen_id else None
            filas_suc.append(f)

    # --- depósitos: demanda de las sucursales que abastecen
    agregado: dict[tuple[uuid.UUID, uuid.UUID], list[FilaPlan]] = defaultdict(list)
    for f in filas_suc:
        if f.origen is not None:
            agregado[(f.origen.id, f.producto.id)].append(f)
    proveedores = _proveedores(db, empresa_id, list(productos))
    filas_dep: list[FilaPlan] = []
    for dep in depositos:
        for prod in productos.values():
            hijas = agregado.get((dep.id, prod.id), [])
            if not hijas and (dep.id, prod.id) not in saldos and (dep.id, prod.id) not in limites:
                continue
            demanda = sum((h.demanda_semanal for h in hijas), CERO)
            desvio = Decimal(math.sqrt(sum(float(h.desviacion_semanal) ** 2 for h in hijas)))
            confianza = min(
                (h.confianza for h in hijas),
                key=lambda c: _ORDEN_CONFIANZA[c],
                default=Confianza.BAJA,
            )
            proveedor, costo = proveedores.get(prod.id, (None, None))
            dias = (
                proveedor.dias_entrega
                if proveedor and proveedor.dias_entrega is not None
                else p.dias_entrega_proveedor
            )
            f = fila(
                dep,
                prod,
                demanda,
                desvio,
                confianza,
                "suma de sucursales" if hijas else "sin ventas",
                min((h.semanas for h in hijas), default=0),
                dias,
                p.cobertura_deposito_dias,
            )
            f.proveedor, f.ultimo_costo = proveedor, costo
            filas_dep.append(f)
    return Planificacion(filas_suc, filas_dep)


def _proveedores(
    db: Session, empresa_id: uuid.UUID, productos: list[uuid.UUID]
) -> dict[uuid.UUID, tuple[Proveedor, Decimal | None]]:
    """Proveedor y costo de la última compra de cada producto; si nunca se compró, el primer
    proveedor asociado al producto."""
    resultado: dict[uuid.UUID, tuple[Proveedor, Decimal | None]] = {}
    ultima = (
        select(
            CompraLinea.producto_id,
            Compra.proveedor_id,
            CompraLinea.costo_unitario_base,
            func.row_number()
            .over(
                partition_by=CompraLinea.producto_id,
                order_by=(Compra.fecha.desc(), Compra.numero.desc()),
            )
            .label("n"),
        )
        .join(Compra, Compra.id == CompraLinea.compra_id)
        .where(Compra.empresa_id == empresa_id, Compra.estado == EstadoCompra.REGISTRADA)
        .subquery()
    )
    filas = db.execute(
        select(ultima.c.producto_id, Proveedor, ultima.c.costo_unitario_base)
        .join(Proveedor, Proveedor.id == ultima.c.proveedor_id)
        .where(ultima.c.n == 1)
    ).all()
    for prod_id, proveedor, costo in filas:
        resultado[prod_id] = (proveedor, costo)
    for prod_id, proveedor in db.execute(
        select(proveedor_producto.c.producto_id, Proveedor)
        .join(Proveedor, Proveedor.id == proveedor_producto.c.proveedor_id)
        .where(
            proveedor_producto.c.producto_id.in_(productos),
            Proveedor.activo.is_(True),
        )
        .order_by(Proveedor.nombre)
    ).all():
        resultado.setdefault(prod_id, (proveedor, None))
    return resultado


# ================================================================ sugerencias


@dataclass(frozen=True)
class SugerenciaTransferencia:
    fila: FilaPlan
    origen_disponible: Decimal
    cantidad: Decimal  # en unidad base
    presentacion: str
    cantidad_presentacion: Decimal
    insuficiente: bool  # el depósito no alcanza para llegar al objetivo


def sugerir_transferencias(plan: Planificacion) -> list[SugerenciaTransferencia]:
    disponibles = {(f.ubicacion.id, f.producto.id): f.disponible for f in plan.depositos}
    sugerencias = []
    for f in plan.sucursales:
        if not f.con_demanda or f.disponible > f.plan.punto_reorden or f.origen is None:
            continue
        falta = f.plan.objetivo - f.disponible
        if falta <= 0:
            continue
        en_origen = max(disponibles.get((f.origen.id, f.producto.id), CERO), CERO)
        cantidad, presentacion, n = dominio.redondear_a_presentacion(falta, f.presentaciones)
        insuficiente = cantidad > en_origen
        if insuficiente:
            cantidad = en_origen.to_integral_value(rounding=ROUND_FLOOR)
            presentacion, n = "unidad", cantidad
        sugerencias.append(
            SugerenciaTransferencia(f, en_origen, cantidad, presentacion, n, insuficiente)
        )
    return sorted(
        sugerencias,
        key=lambda s: (s.fila.plan.cobertura_dias or Decimal(0), s.fila.producto.nombre),
    )


@dataclass(frozen=True)
class SugerenciaCompra:
    fila: FilaPlan
    fecha: date  # cuándo comprar (hoy = ya)
    cantidad: Decimal
    presentacion: str
    cantidad_presentacion: Decimal


def sugerir_compras(plan: Planificacion, horizonte_dias: int = 14) -> list[SugerenciaCompra]:
    """Qué comprar ya y qué tocará comprar en los próximos días, por depósito."""
    sugerencias = []
    hoy_ = hoy()
    for f in plan.depositos:
        if not f.con_demanda:
            continue
        diaria = f.plan.demanda_diaria
        if f.disponible <= f.plan.punto_reorden:
            fecha, falta = hoy_, f.plan.objetivo - f.disponible
        elif diaria > 0:
            dias = int((f.disponible - f.plan.punto_reorden) / diaria)
            if dias > horizonte_dias:
                continue
            fecha, falta = hoy_ + timedelta(days=dias), f.plan.objetivo - f.plan.punto_reorden
        else:
            continue
        if falta <= 0:
            continue
        cantidad, presentacion, n = dominio.redondear_a_presentacion(falta, f.presentaciones)
        sugerencias.append(SugerenciaCompra(f, fecha, cantidad, presentacion, n))
    return sorted(sugerencias, key=lambda s: (s.fecha, s.fila.producto.nombre))
