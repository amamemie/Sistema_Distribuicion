"""Tareas en segundo plano de pedidos (worker Celery)."""

import uuid

from app.modules.pedidos import lectura
from app.workers.celery_app import celery_app


@celery_app.task(name="pedidos.leer_oc")  # type: ignore[untyped-decorator]
def leer_oc(lectura_id: str) -> None:
    lectura.procesar(uuid.UUID(lectura_id))
