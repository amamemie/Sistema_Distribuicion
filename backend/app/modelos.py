"""Importa todos los modelos para que SQLAlchemy y Alembic los conozcan.

Al crear un módulo nuevo con tablas, agréguelo aquí.
"""

from app.core import eventos  # noqa: F401
from app.modules.catalogo import models as catalogo  # noqa: F401
from app.modules.clientes import models as clientes  # noqa: F401
from app.modules.compras import models as compras  # noqa: F401
from app.modules.identidad import models as identidad  # noqa: F401
from app.modules.inventario import models as inventario  # noqa: F401
from app.modules.organizacion import models as organizacion  # noqa: F401
from app.modules.proveedores import models as proveedores  # noqa: F401
