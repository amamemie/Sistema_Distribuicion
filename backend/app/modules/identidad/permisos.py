"""Catálogo de permisos y roles iniciales.

Los permisos se definen en código (la aplicación los consulta), pero los roles viven en la
base de datos: el dueño puede crear roles nuevos (p. ej. "Contador") combinando permisos.
Para añadir un permiso: agréguelo aquí y ejecute `python -m app.cli inicializar`.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class DefPermiso:
    codigo: str
    modulo: str
    descripcion: str


PERMISOS: tuple[DefPermiso, ...] = (
    # Administración
    DefPermiso("usuarios.ver", "Administración", "Ver usuarios"),
    DefPermiso("usuarios.gestionar", "Administración", "Crear, editar y desactivar usuarios"),
    DefPermiso("roles.ver", "Administración", "Ver roles y permisos"),
    DefPermiso("roles.gestionar", "Administración", "Crear y editar roles"),
    DefPermiso("ubicaciones.gestionar", "Administración", "Crear y editar depósitos y sucursales"),
    DefPermiso(
        "ubicaciones.todas",
        "Administración",
        "Operar en todas las ubicaciones (sin estar asignado a ellas)",
    ),
    DefPermiso("configuracion.gestionar", "Administración", "Cambiar la configuración general"),
    DefPermiso("auditoria.ver", "Administración", "Consultar la bitácora de auditoría"),
    # Catálogo y terceros
    DefPermiso("catalogo.ver", "Catálogo", "Ver productos y presentaciones"),
    DefPermiso("catalogo.gestionar", "Catálogo", "Crear y editar productos y presentaciones"),
    DefPermiso("proveedores.gestionar", "Catálogo", "Crear y editar proveedores"),
    DefPermiso("clientes.gestionar", "Catálogo", "Crear y editar cadenas y sus sucursales"),
    # Inventario
    DefPermiso("inventario.ver", "Inventario", "Consultar stock y kardex"),
    DefPermiso("compras.registrar", "Inventario", "Registrar compras e ingresos"),
    DefPermiso("inventario.transferir", "Inventario", "Transferir mercadería entre ubicaciones"),
    DefPermiso("inventario.ajustar", "Inventario", "Registrar ajustes (merma, rotura, conteo)"),
    DefPermiso(
        "inventario.aprobar_ajuste", "Inventario", "Aprobar ajustes de inventario sensibles"
    ),
    # Pedidos
    DefPermiso("pedidos.escanear", "Pedidos", "Cargar órdenes de compra y revisar lo extraído"),
    DefPermiso("pedidos.confirmar", "Pedidos", "Confirmar pedidos (reserva stock)"),
    DefPermiso("pedidos.alistar", "Pedidos", "Marcar pedidos como alistados (descuenta stock)"),
    DefPermiso("pedidos.entregar", "Pedidos", "Marcar pedidos como entregados"),
    DefPermiso("pedidos.anular", "Pedidos", "Anular pedidos no entregados"),
    DefPermiso("pedidos.ver_todos", "Pedidos", "Ver pedidos de otros usuarios"),
    # Información sensible
    DefPermiso("costos.ver", "Rentabilidad", "Ver costos, ganancias y márgenes"),
    DefPermiso("reportes.operativos", "Reportes", "Ver reportes operativos"),
    DefPermiso("reportes.rentabilidad", "Reportes", "Ver reportes de ganancias y márgenes"),
)

CODIGOS = frozenset(p.codigo for p in PERMISOS)

ROL_DUENO = "Dueño"
ROL_ADMINISTRADOR = "Administrador"
ROL_ENCARGADO = "Encargado"

# El Dueño siempre recibe todos los permisos; no hace falta listarlos.
ROLES_INICIALES: dict[str, tuple[str, frozenset[str]]] = {
    ROL_ADMINISTRADOR: (
        "Gestiona compras, transferencias, ajustes, catálogo y pedidos.",
        frozenset(
            {
                "usuarios.ver",
                "ubicaciones.todas",
                "catalogo.ver",
                "catalogo.gestionar",
                "proveedores.gestionar",
                "clientes.gestionar",
                "inventario.ver",
                "compras.registrar",
                "inventario.transferir",
                "inventario.ajustar",
                "pedidos.escanear",
                "pedidos.confirmar",
                "pedidos.alistar",
                "pedidos.entregar",
                "pedidos.anular",
                "pedidos.ver_todos",
                "reportes.operativos",
            }
        ),
    ),
    ROL_ENCARGADO: (
        "Escanea órdenes de compra, alista y entrega pedidos. No ve costos ni ganancias.",
        frozenset(
            {
                "catalogo.ver",
                "inventario.ver",
                "pedidos.escanear",
                "pedidos.confirmar",
                "pedidos.alistar",
                "pedidos.entregar",
            }
        ),
    ),
}
