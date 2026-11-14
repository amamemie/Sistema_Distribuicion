"""Cola de tareas en segundo plano.

En fases siguientes aquí se registran: lectura de OC, alertas, reportes pesados y
reentrenamiento de modelos.
"""

from celery import Celery

from app.core.config import get_settings

s = get_settings()
celery_app = Celery("inventario", broker=s.redis_url, backend=s.redis_url)
celery_app.conf.update(
    timezone=s.zona_horaria,
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)


@celery_app.task(name="sistema.ping")  # type: ignore[untyped-decorator]
def ping() -> str:
    return "pong"
