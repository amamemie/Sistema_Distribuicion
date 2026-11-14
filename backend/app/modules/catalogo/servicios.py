import uuid
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import Conflicto, NoEncontrado, ReglaNegocio
from app.modules.catalogo.models import Categoria, LimiteStock, Marca, Presentacion, Producto
from app.modules.catalogo.schemas import (
    LimiteEntrada,
    NombreActualizacion,
    NombreEntrada,
    PresentacionActualizacion,
    PresentacionEntrada,
    ProductoActualizacion,
    ProductoEntrada,
)
from app.modules.identidad import auditoria
from app.modules.identidad.contexto import Contexto
from app.modules.organizacion import servicios as ubicaciones

# ---------------------------------------------------------------- categorías y marcas

_ENTIDAD = {Categoria: ("categoria", "categoría"), Marca: ("marca", "marca")}


def listar_simples[T: (Categoria, Marca)](db: Session, ctx: Contexto, modelo: type[T]) -> list[T]:
    return list(
        db.scalars(
            select(modelo).where(modelo.empresa_id == ctx.empresa_id).order_by(modelo.nombre)
        )
    )


def _nombre_libre[T: (Categoria, Marca)](
    db: Session, ctx: Contexto, modelo: type[T], nombre: str, excepto: uuid.UUID | None = None
) -> None:
    consulta = select(modelo.id).where(
        modelo.empresa_id == ctx.empresa_id, func.lower(modelo.nombre) == nombre.lower()
    )
    if excepto:
        consulta = consulta.where(modelo.id != excepto)
    if db.scalar(consulta):
        raise Conflicto(f"Ya existe una {_ENTIDAD[modelo][1]} con ese nombre.")


def crear_simple[T: (Categoria, Marca)](
    db: Session, ctx: Contexto, modelo: type[T], datos: NombreEntrada
) -> T:
    nombre = datos.nombre.strip()
    _nombre_libre(db, ctx, modelo, nombre)
    obj = modelo(empresa_id=ctx.empresa_id, nombre=nombre)
    db.add(obj)
    db.flush()
    entidad = _ENTIDAD[modelo][0]
    auditoria.registrar_ctx(
        db,
        ctx,
        accion=f"{entidad}.crear",
        entidad=entidad,
        entidad_id=obj.id,
        despues={"nombre": nombre},
    )
    db.commit()
    return obj


def actualizar_simple[T: (Categoria, Marca)](
    db: Session, ctx: Contexto, modelo: type[T], obj_id: uuid.UUID, datos: NombreActualizacion
) -> T:
    obj = db.get(modelo, obj_id)
    if obj is None or obj.empresa_id != ctx.empresa_id:
        raise NoEncontrado(f"La {_ENTIDAD[modelo][1]} no existe.")
    antes = {"nombre": obj.nombre, "activo": obj.activo}
    if datos.nombre is not None:
        _nombre_libre(db, ctx, modelo, datos.nombre.strip(), excepto=obj.id)
        obj.nombre = datos.nombre.strip()
    if datos.activo is not None:
        obj.activo = datos.activo
    despues = {"nombre": obj.nombre, "activo": obj.activo}
    if despues != antes:
        entidad = _ENTIDAD[modelo][0]
        auditoria.registrar_ctx(
            db,
            ctx,
            accion=f"{entidad}.actualizar",
            entidad=entidad,
            entidad_id=obj.id,
            antes=antes,
            despues=despues,
        )
    db.commit()
    return obj


# ---------------------------------------------------------------- productos


def _foto(p: Producto) -> dict[str, Any]:
    return {
        "sku": p.sku,
        "nombre": p.nombre,
        "descripcion": p.descripcion,
        "categoria_id": p.categoria_id,
        "marca_id": p.marca_id,
        "unidad_base": p.unidad_base,
        "codigo_barras": p.codigo_barras,
        "controla_vencimiento": p.controla_vencimiento,
        "activo": p.activo,
    }


def obtener_producto(db: Session, ctx: Contexto, producto_id: uuid.UUID) -> Producto:
    producto = db.get(Producto, producto_id)
    if producto is None or producto.empresa_id != ctx.empresa_id:
        raise NoEncontrado("El producto no existe.")
    return producto


def producto_operable(db: Session, ctx: Contexto, producto_id: uuid.UUID) -> Producto:
    producto = obtener_producto(db, ctx, producto_id)
    if not producto.activo:
        raise ReglaNegocio(f"El producto «{producto.nombre}» está desactivado.")
    return producto


def presentacion_de(producto: Producto, presentacion_id: uuid.UUID | None) -> Presentacion | None:
    """Valida que la presentación pertenezca al producto. None = unidad base."""
    if presentacion_id is None:
        return None
    for p in producto.presentaciones:
        if p.id == presentacion_id:
            if not p.activo:
                raise ReglaNegocio(f"La presentación «{p.nombre}» está desactivada.")
            return p
    raise ReglaNegocio(f"La presentación indicada no pertenece a «{producto.nombre}».")


def listar_productos(
    db: Session,
    ctx: Contexto,
    *,
    buscar: str | None,
    categoria_id: uuid.UUID | None,
    activo: bool | None,
    pagina: int,
    tamano: int,
) -> tuple[list[Producto], int]:
    filtros = [Producto.empresa_id == ctx.empresa_id]
    if buscar:
        patron = f"%{buscar.strip()}%"
        filtros.append(
            or_(
                Producto.nombre.ilike(patron),
                Producto.sku.ilike(patron),
                Producto.codigo_barras == buscar.strip(),
            )
        )
    if categoria_id:
        filtros.append(Producto.categoria_id == categoria_id)
    if activo is not None:
        filtros.append(Producto.activo.is_(activo))
    total = db.scalar(select(func.count()).select_from(Producto).where(*filtros)) or 0
    items = list(
        db.scalars(
            select(Producto)
            .where(*filtros)
            .order_by(Producto.nombre)
            .offset((pagina - 1) * tamano)
            .limit(tamano)
        )
    )
    return items, total


def _validar_referencias(
    db: Session, ctx: Contexto, categoria_id: uuid.UUID | None, marca_id: uuid.UUID | None
) -> None:
    if categoria_id is not None:
        cat = db.get(Categoria, categoria_id)
        if cat is None or cat.empresa_id != ctx.empresa_id:
            raise ReglaNegocio("La categoría no existe.")
    if marca_id is not None:
        marca = db.get(Marca, marca_id)
        if marca is None or marca.empresa_id != ctx.empresa_id:
            raise ReglaNegocio("La marca no existe.")


def _sku_libre(db: Session, ctx: Contexto, sku: str, excepto: uuid.UUID | None = None) -> None:
    consulta = select(Producto.id).where(
        Producto.empresa_id == ctx.empresa_id, func.lower(Producto.sku) == sku.lower()
    )
    if excepto:
        consulta = consulta.where(Producto.id != excepto)
    if db.scalar(consulta):
        raise Conflicto(f"Ya existe un producto con el SKU {sku}.")


def _validar_presentaciones_unicas(nombres: list[str]) -> None:
    normalizados = [n.strip().lower() for n in nombres]
    if len(set(normalizados)) != len(normalizados):
        raise ReglaNegocio("Hay presentaciones con el mismo nombre.")


def crear_producto(db: Session, ctx: Contexto, datos: ProductoEntrada) -> Producto:
    sku = datos.sku.strip().upper()
    _sku_libre(db, ctx, sku)
    _validar_referencias(db, ctx, datos.categoria_id, datos.marca_id)
    _validar_presentaciones_unicas([p.nombre for p in datos.presentaciones])
    producto = Producto(
        empresa_id=ctx.empresa_id,
        sku=sku,
        nombre=datos.nombre.strip(),
        descripcion=datos.descripcion,
        categoria_id=datos.categoria_id,
        marca_id=datos.marca_id,
        unidad_base=datos.unidad_base.strip().lower(),
        codigo_barras=datos.codigo_barras,
        controla_vencimiento=datos.controla_vencimiento,
        presentaciones=[
            Presentacion(nombre=p.nombre.strip(), factor=p.factor, codigo_barras=p.codigo_barras)
            for p in datos.presentaciones
        ],
    )
    db.add(producto)
    db.flush()
    auditoria.registrar_ctx(
        db,
        ctx,
        accion="producto.crear",
        entidad="producto",
        entidad_id=producto.id,
        despues={
            **_foto(producto),
            "presentaciones": [
                {"nombre": p.nombre, "factor": p.factor} for p in datos.presentaciones
            ],
        },
    )
    db.commit()
    db.refresh(producto)
    return producto


def actualizar_producto(
    db: Session, ctx: Contexto, producto_id: uuid.UUID, datos: ProductoActualizacion
) -> Producto:
    producto = obtener_producto(db, ctx, producto_id)
    antes = _foto(producto)
    cambios = datos.model_dump(exclude_unset=True)
    if cambios.get("sku"):
        cambios["sku"] = cambios["sku"].strip().upper()
        _sku_libre(db, ctx, cambios["sku"], excepto=producto.id)
    if cambios.get("categoria_id") is None:
        cambios.pop("categoria_id", None)
    _validar_referencias(db, ctx, cambios.get("categoria_id"), cambios.get("marca_id"))
    if cambios.get("unidad_base"):
        cambios["unidad_base"] = cambios["unidad_base"].strip().lower()
    anulables = {"descripcion", "marca_id", "codigo_barras"}
    for campo, valor in cambios.items():
        if valor is not None or campo in anulables:
            setattr(producto, campo, valor)
    despues = _foto(producto)
    if despues != antes:
        auditoria.registrar_ctx(
            db,
            ctx,
            accion="producto.actualizar",
            entidad="producto",
            entidad_id=producto.id,
            antes=antes,
            despues=despues,
        )
    db.commit()
    db.refresh(producto)
    return producto


def agregar_presentacion(
    db: Session, ctx: Contexto, producto_id: uuid.UUID, datos: PresentacionEntrada
) -> Presentacion:
    producto = obtener_producto(db, ctx, producto_id)
    _validar_presentaciones_unicas([p.nombre for p in producto.presentaciones] + [datos.nombre])
    presentacion = Presentacion(
        producto_id=producto.id,
        nombre=datos.nombre.strip(),
        factor=datos.factor,
        codigo_barras=datos.codigo_barras,
    )
    db.add(presentacion)
    db.flush()
    auditoria.registrar_ctx(
        db,
        ctx,
        accion="presentacion.crear",
        entidad="presentacion",
        entidad_id=presentacion.id,
        despues={"producto": producto.sku, "nombre": presentacion.nombre, "factor": datos.factor},
    )
    db.commit()
    return presentacion


def actualizar_presentacion(
    db: Session, ctx: Contexto, presentacion_id: uuid.UUID, datos: PresentacionActualizacion
) -> Presentacion:
    presentacion = db.get(Presentacion, presentacion_id)
    if presentacion is None or presentacion.producto.empresa_id != ctx.empresa_id:
        raise NoEncontrado("La presentación no existe.")
    antes = {
        "nombre": presentacion.nombre,
        "factor": presentacion.factor,
        "activo": presentacion.activo,
        "codigo_barras": presentacion.codigo_barras,
    }
    cambios = datos.model_dump(exclude_unset=True)
    if cambios.get("nombre"):
        otros = [p.nombre for p in presentacion.producto.presentaciones if p.id != presentacion.id]
        _validar_presentaciones_unicas([*otros, cambios["nombre"]])
        cambios["nombre"] = cambios["nombre"].strip()
    for campo, valor in cambios.items():
        if valor is not None or campo == "codigo_barras":
            setattr(presentacion, campo, valor)
    despues = {
        "nombre": presentacion.nombre,
        "factor": presentacion.factor,
        "activo": presentacion.activo,
        "codigo_barras": presentacion.codigo_barras,
    }
    if despues != antes:
        # El factor histórico queda congelado en cada movimiento; cambiarlo no altera el pasado.
        auditoria.registrar_ctx(
            db,
            ctx,
            accion="presentacion.actualizar",
            entidad="presentacion",
            entidad_id=presentacion.id,
            antes=antes,
            despues=despues,
        )
    db.commit()
    return presentacion


def limites_de(db: Session, producto_id: uuid.UUID) -> list[LimiteStock]:
    return list(db.scalars(select(LimiteStock).where(LimiteStock.producto_id == producto_id)))


def guardar_limites(
    db: Session, ctx: Contexto, producto_id: uuid.UUID, limites: list[LimiteEntrada]
) -> list[LimiteStock]:
    producto = obtener_producto(db, ctx, producto_id)
    actuales = {lim.ubicacion_id: lim for lim in limites_de(db, producto.id)}
    antes = {str(k): [v.minimo, v.maximo] for k, v in actuales.items()}
    for entrada in limites:
        ubicaciones.obtener(db, ctx, entrada.ubicacion_id)
        if (
            entrada.minimo is not None
            and entrada.maximo is not None
            and entrada.maximo < entrada.minimo
        ):
            raise ReglaNegocio("El stock máximo no puede ser menor que el mínimo.")
        limite = actuales.get(entrada.ubicacion_id)
        if limite is None:
            limite = LimiteStock(producto_id=producto.id, ubicacion_id=entrada.ubicacion_id)
            db.add(limite)
            actuales[entrada.ubicacion_id] = limite
        limite.minimo = entrada.minimo
        limite.maximo = entrada.maximo
    db.flush()
    despues = {str(k): [v.minimo, v.maximo] for k, v in actuales.items()}
    if despues != antes:
        auditoria.registrar_ctx(
            db,
            ctx,
            accion="producto.limites",
            entidad="producto",
            entidad_id=producto.id,
            antes=antes,
            despues=despues,
        )
    db.commit()
    return list(actuales.values())
