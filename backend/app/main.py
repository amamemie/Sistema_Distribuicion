from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import registrar_manejadores
from app.core.logging import configurar_logging, middleware_registro
from app.modules.identidad.api import router as identidad_router
from app.modules.organizacion.api import router as organizacion_router


def crear_app() -> FastAPI:
    s = get_settings()
    configurar_logging(s.log_nivel)
    app = FastAPI(
        title=s.app_nombre,
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )
    app.middleware("http")(middleware_registro)
    if s.cors_origenes:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=s.cors_origenes,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    registrar_manejadores(app)

    api = APIRouter(prefix="/api")

    @api.get("/salud", tags=["Sistema"])
    def salud(db: Session = Depends(get_db)) -> dict[str, str]:
        db.execute(text("SELECT 1"))
        return {"estado": "ok"}

    api.include_router(identidad_router)
    api.include_router(organizacion_router)
    app.include_router(api)
    return app


app = crear_app()
