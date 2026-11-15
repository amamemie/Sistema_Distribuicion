from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración leída de variables de entorno (o de un archivo .env)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_nombre: str = "Sistema de Inventario"
    entorno: Literal["desarrollo", "pruebas", "produccion"] = "desarrollo"
    zona_horaria: str = "America/La_Paz"

    database_url: str = "postgresql+psycopg://inventario:inventario@localhost:5432/inventario"
    redis_url: str = "redis://localhost:6379/0"

    # Sesiones
    sesion_duracion_horas: int = 12
    cookie_segura: bool = False  # True en producción (solo HTTPS)

    # Protección de inicio de sesión
    login_max_intentos: int = 5
    login_ventana_minutos: int = 15

    # Solo necesario si el frontend se sirve desde otro origen
    cors_origenes: list[str] = []

    # Archivos subidos (OC, constancias de entrega). En Docker es un volumen respaldado.
    archivos_dir: str = "/datos/archivos"
    archivo_max_mb: int = 15
    # Lectura automática de OC (local, sin costo). Se puede apagar si el equipo es muy lento.
    lectura_automatica: bool = True

    log_nivel: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
