"""Cola de tareas en segundo plano: lectura de documentos, alertas y pronóstico de demanda.

Las tareas periódicas las dispara el servicio `beat` (docker-compose).
"""

from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

s = get_settings()
celery_app = Celery(
    "inventario",
    broker=s.redis_url,
    backend=s.redis_url,
    include=["app.modules.pedidos.tareas", "app.modules.alertas.tareas"],
)
celery_app.conf.update(
    timezone=s.zona_horaria,
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_ignore_result=True,
    beat_schedule={
        "revisar-alertas": {"task": "alertas.evaluar", "schedule": crontab(minute="*/10")},
        # Reentrenamiento semanal del pronóstico (spec 4.3): lunes de madrugada.
        "pronostico-semanal": {
            "task": "alertas.pronosticar",
            "schedule": crontab(minute=0, hour=3, day_of_week="mon"),
        },
    },
)

# Los modelos deben estar registrados antes de que una tarea use la base de datos.
from app import modelos as _modelos  # noqa: E402, F401


@celery_app.task(name="sistema.ping")  # type: ignore[untyped-decorator]
def ping() -> str:
    return "pong"
