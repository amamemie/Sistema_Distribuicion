from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import modelos as _modelos  # noqa: F401  (registra todos los modelos)
from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import registrar_manejadores
from app.core.logging import configurar_logging, middleware_registro
from app.modules.catalogo.api import router as catalogo_router
from app.modules.clientes.api import router as clientes_router
from app.modules.compras.api import router as compras_router
from app.modules.identidad.api import router as identidad_router
from app.modules.inventario.api import router as inventario_router
from app.modules.organizacion.api import router as organizacion_router
from app.modules.proveedores.api import router as proveedores_router


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

    for router in (
        identidad_router,
        organizacion_router,
        catalogo_router,
        proveedores_router,
        clientes_router,
        compras_router,
        inventario_router,
    ):
        api.include_router(router)
    app.include_router(api)
    return app


app = crear_app()
