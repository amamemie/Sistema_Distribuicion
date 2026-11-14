import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.schemas import Pagina
from app.modules.identidad import servicios
from app.modules.identidad.contexto import Contexto
from app.modules.identidad.dependencias import (
    COOKIE_CSRF,
    COOKIE_SESION,
    datos_cliente,
    requiere,
    sesion_actual,
    usuario_actual,
)
from app.modules.identidad.models import Auditoria, Rol, Sesion, Usuario
from app.modules.identidad.schemas import (
    AuditoriaSalida,
    CambioPasswordEntrada,
    LoginEntrada,
    PermisoSalida,
    RestablecerPasswordEntrada,
    RolActualizacion,
    RolEntrada,
    RolSalida,
    UsuarioActualizacion,
    UsuarioEntrada,
    UsuarioSalida,
    UsuarioYo,
)

router = APIRouter()


def _usuario_yo(usuario: Usuario) -> UsuarioYo:
    base = UsuarioSalida.model_validate(usuario).model_dump()
    return UsuarioYo(**base, permisos=sorted(usuario.permisos))


def _rol_salida(rol: Rol) -> RolSalida:
    return RolSalida(
        id=rol.id,
        nombre=rol.nombre,
        descripcion=rol.descripcion,
        es_sistema=rol.es_sistema,
        permisos=sorted(p.codigo for p in rol.permisos),
    )


# ---------------------------------------------------------------- autenticación


@router.post("/auth/login", response_model=UsuarioYo, tags=["Autenticación"])
def login(
    datos: LoginEntrada, request: Request, response: Response, db: Session = Depends(get_db)
) -> UsuarioYo:
    ip, user_agent = datos_cliente(request)
    sesion, token = servicios.iniciar_sesion(db, datos.correo, datos.password, ip, user_agent)
    s = get_settings()
    duracion = s.sesion_duracion_horas * 3600
    response.set_cookie(
        COOKIE_SESION,
        token,
        max_age=duracion,
        httponly=True,
        secure=s.cookie_segura,
        samesite="lax",
        path="/",
    )
    # Legible por el frontend, que la reenvía en la cabecera X-CSRF-Token.
    response.set_cookie(
        COOKIE_CSRF,
        sesion.csrf_token,
        max_age=duracion,
        httponly=False,
        secure=s.cookie_segura,
        samesite="lax",
        path="/",
    )
    return _usuario_yo(sesion.usuario)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT, tags=["Autenticación"])
def logout(
    response: Response, sesion: Sesion = Depends(sesion_actual), db: Session = Depends(get_db)
) -> None:
    servicios.cerrar_sesion(db, sesion)
    response.delete_cookie(COOKIE_SESION, path="/")
    response.delete_cookie(COOKIE_CSRF, path="/")


@router.get("/auth/yo", response_model=UsuarioYo, tags=["Autenticación"])
def yo(ctx: Contexto = Depends(usuario_actual)) -> UsuarioYo:
    return _usuario_yo(ctx.usuario)


@router.post(
    "/auth/cambiar-password", status_code=status.HTTP_204_NO_CONTENT, tags=["Autenticación"]
)
def cambiar_password(
    datos: CambioPasswordEntrada,
    ctx: Contexto = Depends(usuario_actual),
    sesion: Sesion = Depends(sesion_actual),
    db: Session = Depends(get_db),
) -> None:
    servicios.cambiar_password_propio(db, ctx, sesion, datos.password_actual, datos.password_nueva)


# ---------------------------------------------------------------- usuarios


@router.get("/usuarios", response_model=list[UsuarioSalida], tags=["Usuarios"])
def listar_usuarios(
    ctx: Contexto = Depends(requiere("usuarios.ver")), db: Session = Depends(get_db)
) -> list[Usuario]:
    return servicios.listar_usuarios(db, ctx)


@router.post(
    "/usuarios",
    response_model=UsuarioSalida,
    status_code=status.HTTP_201_CREATED,
    tags=["Usuarios"],
)
def crear_usuario(
    datos: UsuarioEntrada,
    ctx: Contexto = Depends(requiere("usuarios.gestionar")),
    db: Session = Depends(get_db),
) -> Usuario:
    return servicios.crear_usuario(db, ctx, datos)


@router.patch("/usuarios/{usuario_id}", response_model=UsuarioSalida, tags=["Usuarios"])
def actualizar_usuario(
    usuario_id: uuid.UUID,
    datos: UsuarioActualizacion,
    ctx: Contexto = Depends(requiere("usuarios.gestionar")),
    db: Session = Depends(get_db),
) -> Usuario:
    return servicios.actualizar_usuario(db, ctx, usuario_id, datos)


@router.post(
    "/usuarios/{usuario_id}/restablecer-password",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Usuarios"],
)
def restablecer_password(
    usuario_id: uuid.UUID,
    datos: RestablecerPasswordEntrada,
    ctx: Contexto = Depends(requiere("usuarios.gestionar")),
    db: Session = Depends(get_db),
) -> None:
    servicios.restablecer_password(db, ctx, usuario_id, datos.password)


# ---------------------------------------------------------------- roles y permisos


@router.get("/permisos", response_model=list[PermisoSalida], tags=["Roles"])
def listar_permisos(
    _: Contexto = Depends(requiere("roles.ver")), db: Session = Depends(get_db)
) -> list[PermisoSalida]:
    return [PermisoSalida.model_validate(p) for p in servicios.listar_permisos(db)]


@router.get("/roles", response_model=list[RolSalida], tags=["Roles"])
def listar_roles(
    ctx: Contexto = Depends(requiere("roles.ver")), db: Session = Depends(get_db)
) -> list[RolSalida]:
    return [_rol_salida(r) for r in servicios.listar_roles(db, ctx)]


@router.post(
    "/roles", response_model=RolSalida, status_code=status.HTTP_201_CREATED, tags=["Roles"]
)
def crear_rol(
    datos: RolEntrada,
    ctx: Contexto = Depends(requiere("roles.gestionar")),
    db: Session = Depends(get_db),
) -> RolSalida:
    return _rol_salida(servicios.crear_rol(db, ctx, datos))


@router.patch("/roles/{rol_id}", response_model=RolSalida, tags=["Roles"])
def actualizar_rol(
    rol_id: uuid.UUID,
    datos: RolActualizacion,
    ctx: Contexto = Depends(requiere("roles.gestionar")),
    db: Session = Depends(get_db),
) -> RolSalida:
    return _rol_salida(servicios.actualizar_rol(db, ctx, rol_id, datos))


# ---------------------------------------------------------------- auditoría


@router.get("/auditoria", response_model=Pagina[AuditoriaSalida], tags=["Auditoría"])
def listar_auditoria(
    entidad: str | None = None,
    entidad_id: str | None = None,
    usuario_id: uuid.UUID | None = None,
    accion: str | None = None,
    desde: datetime | None = None,
    hasta: datetime | None = None,
    pagina: int = Query(1, ge=1),
    tamano: int = Query(50, ge=1, le=200),
    ctx: Contexto = Depends(requiere("auditoria.ver")),
    db: Session = Depends(get_db),
) -> Pagina[AuditoriaSalida]:
    filtros = [Auditoria.empresa_id == ctx.empresa_id]
    if entidad:
        filtros.append(Auditoria.entidad == entidad)
    if entidad_id:
        filtros.append(Auditoria.entidad_id == entidad_id)
    if usuario_id:
        filtros.append(Auditoria.usuario_id == usuario_id)
    if accion:
        filtros.append(Auditoria.accion.startswith(accion))
    if desde:
        filtros.append(Auditoria.fecha >= desde)
    if hasta:
        filtros.append(Auditoria.fecha <= hasta)

    total = db.scalar(select(func.count()).select_from(Auditoria).where(*filtros)) or 0
    filas = db.scalars(
        select(Auditoria)
        .where(*filtros)
        .order_by(Auditoria.id.desc())
        .offset((pagina - 1) * tamano)
        .limit(tamano)
    )
    items = [
        AuditoriaSalida(
            id=a.id,
            fecha=a.fecha,
            usuario_id=a.usuario_id,
            usuario_nombre=a.usuario.nombre_completo if a.usuario else None,
            accion=a.accion,
            entidad=a.entidad,
            entidad_id=a.entidad_id,
            antes=a.antes,
            despues=a.despues,
            ip=a.ip,
        )
        for a in filas
    ]
    return Pagina(items=items, total=total, pagina=pagina, tamano=tamano)
