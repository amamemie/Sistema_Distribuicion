# CLAUDE.md

Sistema de inventario, pedidos y rentabilidad para una distribuidora de La Paz (Bolivia) que
abastece a supermercados. Proyecto freelance real, en producción para un cliente.

## Fuentes de verdad (leer antes de cambiar comportamiento de negocio)

1. `docs/decisiones-negocio.md`: respuestas del cliente; **prevalece** sobre la especificación.
2. `PROMPT_sistema_inventario.md`: especificación completa.
3. `docs/arquitectura.md` y `docs/adr/`: arquitectura, modelo de datos, plan por fases.

No inventes reglas de negocio. Si algo es ambiguo o contradictorio, pregunta.

## Stack

- Backend (`backend/`): Python 3.13, FastAPI, SQLAlchemy 2 (síncrono), Alembic, Pydantic v2,
  Celery + Redis. Dependencias con `uv`.
- Frontend (`frontend/`): React 19, TypeScript, Vite, Tailwind 4, TanStack Query, React Router,
  React Hook Form + Zod, PWA.
- PostgreSQL 17. Todo se levanta con Docker Compose; Caddy sirve el frontend y hace de proxy de `/api`.

## Comandos

```bash
# Todo el sistema
docker compose up -d --build
docker compose exec backend python -m app.cli inicializar   # permisos, roles, dueño
docker compose exec backend python -m app.cli demo          # datos de prueba (no producción)

# Backend (desde backend/)
uv sync
uv run ruff format . && uv run ruff check . && uv run mypy app tests
TEST_DATABASE_URL=postgresql+psycopg://USUARIO:CLAVE@localhost:5433/inventario_test uv run pytest
uv run alembic revision --autogenerate -m "descripcion"   # revisar SIEMPRE el archivo generado
uv run uvicorn app.main:app --reload                      # API en :8000

# Frontend (desde frontend/)
npm run dev        # :5173, con proxy de /api hacia :8000
npm run lint && npm run typecheck && npm test && npm run build
```

Antes de dar una tarea por terminada: formato, lint, tipos y pruebas en verde, en backend y frontend.

## Reglas del código

- **Idioma:** dominio, interfaz, mensajes de error y commits en español. Los identificadores van
  sin tildes ni ñ (`anio`, `ubicacion`). Términos técnicos del framework en inglés.
- **Terminología:** Depósito / Sucursal (de la empresa) = `Ubicacion.tipo`; Cadena y
  SucursalCliente (del supermercado). Nunca uses "sucursal" a secas para el cliente.
- **Módulos** en `backend/app/modules/<modulo>/` con `models.py`, `schemas.py`, `servicios.py` y
  `api.py`. Las rutas son delgadas; la lógica va en servicios, la lógica pura en `dominio.py`.
- **Una transacción por caso de uso:** el servicio valida, modifica, audita
  (`auditoria.registrar_ctx`) y hace `commit` al final. Nunca hagas commit a medias.
- **Inventario:** el stock solo cambia a través del servicio de inventario, con bloqueo de fila.
  El libro de movimientos es inmutable: las correcciones se hacen con movimientos de reverso.
- **Nada se borra físicamente:** se desactiva o se anula con motivo. La tabla `auditoria` tiene
  un trigger que impide UPDATE/DELETE.
- **Dinero y cantidades:** `Decimal`/`NUMERIC`, nunca `float`. Costo y precio por unidad base.
- **Multiempresa:** toda tabla de negocio usa el mixin `DeEmpresa` y toda consulta filtra por
  `ctx.empresa_id`.
- **Permisos:** se definen en `app/modules/identidad/permisos.py` y se exigen con
  `Depends(requiere("permiso"))`. Los costos y ganancias requieren `costos.ver`.
- **Errores:** lanza `ReglaNegocio`, `NoEncontrado`, `Conflicto`… (`app/core/errors.py`) con
  mensajes en español aptos para el usuario final.
- **Migraciones:** siempre con Alembic. Nunca edites una migración ya aplicada en producción.
- **Pruebas:** cada regla de negocio nueva lleva su prueba. Las pruebas usan PostgreSQL real
  (`TEST_DATABASE_URL`), con una transacción revertida por prueba.
- **Frontend:** llamadas a la API con `api()` de `src/lib/api.ts` (gestiona cookie y CSRF). Tipos
  de respuesta en `src/lib/tipos.ts`. Diseño mobile-first.

## Flujo de trabajo

- Commits pequeños por funcionalidad, con Conventional Commits en español (`feat:`, `fix:`,
  `docs:`, `test:`, `refactor:`, `chore:`).
- Al terminar cada fase: qué se hizo, cómo probarlo, qué sigue, pendientes y riesgos.
- Nunca subas `.env` ni secretos. Las claves van en variables de entorno.
