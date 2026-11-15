"""Tareas programadas: revisión de alertas cada 10 minutos y pronóstico semanal."""

import logging

from sqlalchemy import select

from app.core.db import SessionLocal
from app.modules.alertas import pronostico, reglas
from app.modules.organizacion.models import Empresa
from app.workers.celery_app import celery_app

log = logging.getLogger(__name__)


def _empresas() -> list[object]:
    with SessionLocal() as db:
        return list(db.scalars(select(Empresa.id).where(Empresa.activo.is_(True))))


@celery_app.task(name="alertas.evaluar")  # type: ignore[untyped-decorator]
def evaluar() -> None:
    for empresa_id in _empresas():
        with SessionLocal() as db:
            try:
                r = reglas.evaluar(db, empresa_id)  # type: ignore[arg-type]
                log.info("Alertas de %s: %s", empresa_id, r)
            except Exception:
                log.exception("Falló la revisión de alertas de %s", empresa_id)


@celery_app.task(name="alertas.pronosticar")  # type: ignore[untyped-decorator]
def pronosticar() -> None:
    for empresa_id in _empresas():
        with SessionLocal() as db:
            try:
                n = pronostico.recalcular(db, empresa_id)  # type: ignore[arg-type]
                reglas.evaluar(db, empresa_id)  # type: ignore[arg-type]
                log.info("Pronóstico de %s: %s productos", empresa_id, n)
            except Exception:
                log.exception("Falló el pronóstico de %s", empresa_id)
