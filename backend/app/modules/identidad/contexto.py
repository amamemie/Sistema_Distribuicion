import uuid
from dataclasses import dataclass

from app.modules.identidad.models import Usuario


@dataclass(frozen=True)
class Contexto:
    """Quién ejecuta la operación y desde dónde. Se pasa a los servicios para auditar."""

    usuario: Usuario
    ip: str | None
    user_agent: str | None

    @property
    def empresa_id(self) -> uuid.UUID:
        return self.usuario.empresa_id

    def puede(self, permiso: str) -> bool:
        return permiso in self.usuario.permisos
