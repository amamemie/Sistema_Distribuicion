"""Datos iniciales idempotentes: permisos, roles base, empresa y usuario dueño."""

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.modules.identidad import auditoria
from app.modules.identidad.models import Permiso, Rol, Usuario
from app.modules.identidad.permisos import PERMISOS, ROL_DUENO, ROLES_INICIALES
from app.modules.organizacion.models import Empresa


def sincronizar_permisos(db: Session) -> None:
    existentes = {p.codigo: p for p in db.scalars(select(Permiso))}
    for definicion in PERMISOS:
        permiso = existentes.get(definicion.codigo)
        if permiso is None:
            db.add(
                Permiso(
                    codigo=definicion.codigo,
                    modulo=definicion.modulo,
                    descripcion=definicion.descripcion,
                )
            )
        else:
            permiso.modulo = definicion.modulo
            permiso.descripcion = definicion.descripcion
    db.flush()


def asegurar_roles(db: Session, empresa: Empresa) -> dict[str, Rol]:
    """Crea los roles base si faltan y mantiene al Dueño con todos los permisos."""
    todos = list(db.scalars(select(Permiso)))
    por_codigo = {p.codigo: p for p in todos}
    roles = {r.nombre: r for r in db.scalars(select(Rol).where(Rol.empresa_id == empresa.id))}

    dueno = roles.get(ROL_DUENO)
    if dueno is None:
        dueno = Rol(
            empresa_id=empresa.id,
            nombre=ROL_DUENO,
            descripcion="Acceso total. Rol del sistema.",
            es_sistema=True,
        )
        db.add(dueno)
        roles[ROL_DUENO] = dueno
    dueno.permisos = todos

    for nombre, (descripcion, codigos) in ROLES_INICIALES.items():
        if nombre not in roles:
            rol = Rol(
                empresa_id=empresa.id,
                nombre=nombre,
                descripcion=descripcion,
                permisos=[por_codigo[c] for c in sorted(codigos)],
            )
            db.add(rol)
            roles[nombre] = rol
    db.flush()
    return roles


def inicializar(
    db: Session,
    *,
    nombre_empresa: str,
    correo_dueno: str,
    password_dueno: str,
    nombre_dueno: str = "Dueño",
    apellido_dueno: str = "",
) -> Empresa:
    sincronizar_permisos(db)
    empresa = db.scalar(select(Empresa).order_by(Empresa.created_at))
    if empresa is None:
        empresa = Empresa(nombre=nombre_empresa)
        db.add(empresa)
        db.flush()
    roles = asegurar_roles(db, empresa)

    try:
        correo = validate_email(correo_dueno.strip(), check_deliverability=False).normalized.lower()
    except EmailNotValidError as error:
        raise ValueError(f"Correo del dueño inválido: {error}") from error
    if db.scalar(select(Usuario).where(Usuario.correo == correo)) is None:
        dueno = Usuario(
            empresa_id=empresa.id,
            nombre=nombre_dueno,
            apellido=apellido_dueno,
            correo=correo,
            password_hash=hash_password(password_dueno),
            roles=[roles[ROL_DUENO]],
        )
        db.add(dueno)
        db.flush()
        auditoria.registrar(
            db,
            accion="usuario.crear",
            entidad="usuario",
            entidad_id=dueno.id,
            empresa_id=empresa.id,
            despues={"correo": correo, "roles": [ROL_DUENO], "origen": "inicializacion"},
        )
    db.commit()
    return empresa
