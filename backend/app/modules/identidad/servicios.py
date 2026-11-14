"""Casos de uso de identidad: sesiones, usuarios y roles.

Cada función que modifica datos registra auditoría y hace commit al final (una transacción).
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import (
    Conflicto,
    DemasiadosIntentos,
    NoAutenticado,
    NoEncontrado,
    ReglaNegocio,
)
from app.core.security import hash_password, hash_token, nuevo_token, verificar_password
from app.modules.identidad import auditoria
from app.modules.identidad.contexto import Contexto
from app.modules.identidad.models import IntentoLogin, Permiso, Rol, Sesion, Usuario
from app.modules.identidad.permisos import CODIGOS, ROL_DUENO
from app.modules.identidad.schemas import (
    RolActualizacion,
    RolEntrada,
    UsuarioActualizacion,
    UsuarioEntrada,
)
from app.modules.organizacion.models import Ubicacion

# ---------------------------------------------------------------- sesiones


def _ahora() -> datetime:
    return datetime.now(UTC)


def _verificar_limite_intentos(db: Session, correo: str, ip: str | None) -> None:
    s = get_settings()
    desde = _ahora() - timedelta(minutes=s.login_ventana_minutos)
    fallidos_correo = db.scalar(
        select(func.count()).where(
            IntentoLogin.correo == correo,
            IntentoLogin.exitoso.is_(False),
            IntentoLogin.fecha > desde,
        )
    )
    fallidos_ip = 0
    if ip:
        fallidos_ip = (
            db.scalar(
                select(func.count()).where(
                    IntentoLogin.ip == ip,
                    IntentoLogin.exitoso.is_(False),
                    IntentoLogin.fecha > desde,
                )
            )
            or 0
        )
    if (fallidos_correo or 0) >= s.login_max_intentos or fallidos_ip >= s.login_max_intentos * 4:
        raise DemasiadosIntentos(
            f"Demasiados intentos fallidos. Espere {s.login_ventana_minutos} minutos e intente "
            "de nuevo."
        )


def iniciar_sesion(
    db: Session, correo: str, password: str, ip: str | None, user_agent: str | None
) -> tuple[Sesion, str]:
    """Devuelve la sesión creada y el token en claro (solo viaja en la cookie)."""
    _verificar_limite_intentos(db, correo, ip)
    usuario = db.scalar(select(Usuario).where(Usuario.correo == correo))
    valido = verificar_password(usuario.password_hash if usuario else None, password)

    if not valido or usuario is None:
        db.add(IntentoLogin(correo=correo, ip=ip, exitoso=False))
        db.commit()
        raise NoAutenticado("Correo o contraseña incorrectos.")
    if not usuario.activo:
        db.add(IntentoLogin(correo=correo, ip=ip, exitoso=False))
        db.commit()
        raise NoAutenticado("La cuenta está desactivada. Consulte con el administrador.")

    token = nuevo_token()
    sesion = Sesion(
        usuario_id=usuario.id,
        token_hash=hash_token(token),
        csrf_token=nuevo_token(),
        expira_at=_ahora() + timedelta(hours=get_settings().sesion_duracion_horas),
        ip=ip,
        user_agent=user_agent,
    )
    db.add(sesion)
    db.add(IntentoLogin(correo=correo, ip=ip, exitoso=True))
    usuario.ultimo_acceso = _ahora()
    auditoria.registrar(
        db,
        accion="sesion.iniciar",
        entidad="usuario",
        entidad_id=usuario.id,
        empresa_id=usuario.empresa_id,
        usuario_id=usuario.id,
        ip=ip,
        user_agent=user_agent,
    )
    db.commit()
    db.refresh(sesion)
    return sesion, token


def cerrar_sesion(db: Session, sesion: Sesion) -> None:
    sesion.revocada_at = _ahora()
    db.commit()


def _revocar_sesiones(db: Session, usuario_id: uuid.UUID) -> None:
    db.execute(
        update(Sesion)
        .where(Sesion.usuario_id == usuario_id, Sesion.revocada_at.is_(None))
        .values(revocada_at=_ahora())
    )


def cambiar_password_propio(
    db: Session, ctx: Contexto, sesion_actual: Sesion, actual: str, nueva: str
) -> None:
    usuario = ctx.usuario
    if not verificar_password(usuario.password_hash, actual):
        raise ReglaNegocio("La contraseña actual no es correcta.")
    usuario.password_hash = hash_password(nueva)
    # Cierra las demás sesiones del usuario; mantiene la actual.
    db.execute(
        update(Sesion)
        .where(
            Sesion.usuario_id == usuario.id,
            Sesion.revocada_at.is_(None),
            Sesion.id != sesion_actual.id,
        )
        .values(revocada_at=_ahora())
    )
    auditoria.registrar_ctx(
        db, ctx, accion="usuario.cambiar_password", entidad="usuario", entidad_id=usuario.id
    )
    db.commit()


# ---------------------------------------------------------------- usuarios


def _foto_usuario(u: Usuario) -> dict[str, Any]:
    """Estado auditable del usuario (sin la contraseña)."""
    return {
        "nombre": u.nombre,
        "apellido": u.apellido,
        "correo": u.correo,
        "telefono": u.telefono,
        "activo": u.activo,
        "roles": sorted(r.nombre for r in u.roles),
        "ubicaciones": sorted(ub.nombre for ub in u.ubicaciones),
        "ubicacion_predeterminada_id": u.ubicacion_predeterminada_id,
    }


def listar_usuarios(db: Session, ctx: Contexto) -> list[Usuario]:
    return list(
        db.scalars(
            select(Usuario)
            .where(Usuario.empresa_id == ctx.empresa_id)
            .order_by(Usuario.nombre, Usuario.apellido)
        )
    )


def obtener_usuario(db: Session, ctx: Contexto, usuario_id: uuid.UUID) -> Usuario:
    usuario = db.get(Usuario, usuario_id)
    if usuario is None or usuario.empresa_id != ctx.empresa_id:
        raise NoEncontrado("El usuario no existe.")
    return usuario


def _cargar_roles(db: Session, ctx: Contexto, ids: list[uuid.UUID]) -> list[Rol]:
    roles = list(db.scalars(select(Rol).where(Rol.id.in_(ids), Rol.empresa_id == ctx.empresa_id)))
    if len(roles) != len(set(ids)):
        raise ReglaNegocio("Uno o más roles no existen.")
    return roles


def _cargar_ubicaciones(db: Session, ctx: Contexto, ids: list[uuid.UUID]) -> list[Ubicacion]:
    if not ids:
        return []
    ubicaciones = list(
        db.scalars(
            select(Ubicacion).where(Ubicacion.id.in_(ids), Ubicacion.empresa_id == ctx.empresa_id)
        )
    )
    if len(ubicaciones) != len(set(ids)):
        raise ReglaNegocio("Una o más ubicaciones no existen.")
    return ubicaciones


def _validar_predeterminada(usuario: Usuario) -> None:
    pred = usuario.ubicacion_predeterminada_id
    if pred is not None and pred not in {u.id for u in usuario.ubicaciones}:
        raise ReglaNegocio("La ubicación predeterminada debe estar entre las asignadas.")


def _correo_disponible(db: Session, correo: str, excepto: uuid.UUID | None = None) -> None:
    consulta = select(Usuario.id).where(Usuario.correo == correo)
    if excepto:
        consulta = consulta.where(Usuario.id != excepto)
    if db.scalar(consulta) is not None:
        raise Conflicto("Ya existe un usuario con ese correo.")


def _duenos_activos(db: Session, empresa_id: uuid.UUID) -> set[uuid.UUID]:
    filas = db.scalars(
        select(Usuario.id)
        .join(Usuario.roles)
        .where(
            Usuario.empresa_id == empresa_id,
            Usuario.activo.is_(True),
            Rol.nombre == ROL_DUENO,
            Rol.es_sistema.is_(True),
        )
    )
    return set(filas)


def crear_usuario(db: Session, ctx: Contexto, datos: UsuarioEntrada) -> Usuario:
    _correo_disponible(db, datos.correo)
    usuario = Usuario(
        empresa_id=ctx.empresa_id,
        nombre=datos.nombre.strip(),
        apellido=datos.apellido.strip(),
        correo=datos.correo,
        telefono=datos.telefono,
        password_hash=hash_password(datos.password),
        roles=_cargar_roles(db, ctx, datos.rol_ids),
        ubicaciones=_cargar_ubicaciones(db, ctx, datos.ubicacion_ids),
        ubicacion_predeterminada_id=datos.ubicacion_predeterminada_id,
    )
    _validar_predeterminada(usuario)
    db.add(usuario)
    db.flush()
    auditoria.registrar_ctx(
        db,
        ctx,
        accion="usuario.crear",
        entidad="usuario",
        entidad_id=usuario.id,
        despues=_foto_usuario(usuario),
    )
    db.commit()
    return usuario


def actualizar_usuario(
    db: Session, ctx: Contexto, usuario_id: uuid.UUID, datos: UsuarioActualizacion
) -> Usuario:
    usuario = obtener_usuario(db, ctx, usuario_id)
    antes = _foto_usuario(usuario)
    cambios = datos.model_dump(exclude_unset=True)

    if cambios.get("activo") is False and usuario.id == ctx.usuario.id:
        raise ReglaNegocio("No puede desactivar su propia cuenta.")
    if "correo" in cambios and cambios["correo"] is not None:
        _correo_disponible(db, cambios["correo"], excepto=usuario.id)

    for campo in ("nombre", "apellido", "correo", "telefono", "activo"):
        if campo in cambios and (cambios[campo] is not None or campo == "telefono"):
            setattr(usuario, campo, cambios[campo])
    if datos.rol_ids is not None:
        usuario.roles = _cargar_roles(db, ctx, datos.rol_ids)
    if datos.ubicacion_ids is not None:
        usuario.ubicaciones = _cargar_ubicaciones(db, ctx, datos.ubicacion_ids)
    if "ubicacion_predeterminada_id" in cambios:
        usuario.ubicacion_predeterminada_id = datos.ubicacion_predeterminada_id
    elif usuario.ubicacion_predeterminada_id not in {u.id for u in usuario.ubicaciones}:
        usuario.ubicacion_predeterminada_id = None
    _validar_predeterminada(usuario)

    db.flush()
    if not _duenos_activos(db, ctx.empresa_id):
        raise ReglaNegocio("Debe quedar al menos un usuario activo con el rol Dueño.")
    if not usuario.activo:
        _revocar_sesiones(db, usuario.id)

    despues = _foto_usuario(usuario)
    if despues != antes:
        auditoria.registrar_ctx(
            db,
            ctx,
            accion="usuario.actualizar",
            entidad="usuario",
            entidad_id=usuario.id,
            antes=antes,
            despues=despues,
        )
    db.commit()
    return usuario


def restablecer_password(db: Session, ctx: Contexto, usuario_id: uuid.UUID, nueva: str) -> None:
    usuario = obtener_usuario(db, ctx, usuario_id)
    usuario.password_hash = hash_password(nueva)
    _revocar_sesiones(db, usuario.id)
    auditoria.registrar_ctx(
        db, ctx, accion="usuario.restablecer_password", entidad="usuario", entidad_id=usuario.id
    )
    db.commit()


# ---------------------------------------------------------------- roles


def _foto_rol(r: Rol) -> dict[str, Any]:
    return {
        "nombre": r.nombre,
        "descripcion": r.descripcion,
        "permisos": sorted(p.codigo for p in r.permisos),
    }


def listar_permisos(db: Session) -> list[Permiso]:
    return list(db.scalars(select(Permiso).order_by(Permiso.modulo, Permiso.codigo)))


def listar_roles(db: Session, ctx: Contexto) -> list[Rol]:
    return list(
        db.scalars(
            select(Rol)
            .where(Rol.empresa_id == ctx.empresa_id)
            .order_by(Rol.es_sistema.desc(), Rol.nombre)
        )
    )


def _cargar_permisos(db: Session, codigos: list[str]) -> list[Permiso]:
    desconocidos = set(codigos) - CODIGOS
    if desconocidos:
        raise ReglaNegocio(f"Permisos desconocidos: {', '.join(sorted(desconocidos))}.")
    if not codigos:
        return []
    return list(db.scalars(select(Permiso).where(Permiso.codigo.in_(codigos))))


def _nombre_rol_disponible(
    db: Session, ctx: Contexto, nombre: str, excepto: uuid.UUID | None = None
) -> None:
    consulta = select(Rol.id).where(
        Rol.empresa_id == ctx.empresa_id, func.lower(Rol.nombre) == nombre.lower()
    )
    if excepto:
        consulta = consulta.where(Rol.id != excepto)
    if db.scalar(consulta) is not None:
        raise Conflicto("Ya existe un rol con ese nombre.")


def crear_rol(db: Session, ctx: Contexto, datos: RolEntrada) -> Rol:
    nombre = datos.nombre.strip()
    _nombre_rol_disponible(db, ctx, nombre)
    rol = Rol(
        empresa_id=ctx.empresa_id,
        nombre=nombre,
        descripcion=datos.descripcion,
        permisos=_cargar_permisos(db, datos.permisos),
    )
    db.add(rol)
    db.flush()
    auditoria.registrar_ctx(
        db, ctx, accion="rol.crear", entidad="rol", entidad_id=rol.id, despues=_foto_rol(rol)
    )
    db.commit()
    return rol


def actualizar_rol(db: Session, ctx: Contexto, rol_id: uuid.UUID, datos: RolActualizacion) -> Rol:
    rol = db.get(Rol, rol_id)
    if rol is None or rol.empresa_id != ctx.empresa_id:
        raise NoEncontrado("El rol no existe.")
    if rol.es_sistema:
        raise ReglaNegocio(f"El rol {rol.nombre} es del sistema y no se puede modificar.")
    antes = _foto_rol(rol)
    if datos.nombre is not None:
        _nombre_rol_disponible(db, ctx, datos.nombre.strip(), excepto=rol.id)
        rol.nombre = datos.nombre.strip()
    if "descripcion" in datos.model_fields_set:
        rol.descripcion = datos.descripcion
    if datos.permisos is not None:
        rol.permisos = _cargar_permisos(db, datos.permisos)
    despues = _foto_rol(rol)
    if despues != antes:
        auditoria.registrar_ctx(
            db,
            ctx,
            accion="rol.actualizar",
            entidad="rol",
            entidad_id=rol.id,
            antes=antes,
            despues=despues,
        )
    db.commit()
    return rol
