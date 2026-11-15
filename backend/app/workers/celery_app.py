"""Cola de tareas en segundo plano.

En fases siguientes aquí se registran: lectura de OC, alertas, reportes pesados y
reentrenamiento de modelos.
"""

from celery import Celery

from app.core.config import get_settings

s = get_settings()
celery_app = Celery(
    "inventario",
    broker=s.redis_url,
    backend=s.redis_url,
    include=["app.modules.pedidos.tareas"],
)
celery_app.conf.update(
    timezone=s.zona_horaria,
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_ignore_result=True,
)

# Los modelos deben estar registrados antes de que una tarea use la base de datos.
from app import modelos as _modelos  # noqa: E402, F401


@celery_app.task(name="sistema.ping")  # type: ignore[untyped-decorator]
def ping() -> str:
    return "pong"
