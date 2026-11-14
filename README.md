# Sistema de Inventario, Pedidos y Rentabilidad

Sistema web para una distribuidora que compra en unidades grandes, almacena en depósitos,
fracciona en sucursales y despacha pedidos a supermercados. Controla el stock por ubicación, los
pedidos que llegan en órdenes de compra (OC), quién hizo cada operación y cuánto se ganó.

> **Estado:** Fase 0 completada (base del sistema: usuarios, roles, permisos, ubicaciones,
> auditoría). Ver el [plan por fases](docs/arquitectura.md#plan-por-fases).

## Requisitos

- Docker con Docker Compose (v2)
- Para desarrollar sin Docker: Python 3.13 + [uv](https://docs.astral.sh/uv/), Node.js 24, PostgreSQL 17

## Puesta en marcha

```bash
cp .env.example .env              # y cambie las claves
docker compose up -d --build
docker compose exec backend python -m app.cli inicializar
```

Abra `http://localhost:8080` (o `http://IP-DE-ESTE-EQUIPO:8080` desde otro dispositivo de la red)
e ingrese con `DUENO_CORREO` / `DUENO_PASSWORD` del `.env`.

### Datos de prueba (solo desarrollo)

```bash
docker compose exec backend python -m app.cli demo
```

Crea 2 depósitos, 2 sucursales y estos usuarios (contraseña `Demo-12345`):

| Correo | Rol |
|---|---|
| `admin@example.com` | Administrador |
| `encargado@example.com` | Encargado |

## Desarrollo

```bash
# Base de datos y Redis en Docker
docker compose up -d db redis

# Backend
cd backend
uv sync
export DATABASE_URL=postgresql+psycopg://inventario:CLAVE@localhost:5433/inventario
uv run alembic upgrade head
DUENO_CORREO=dueno@example.com DUENO_PASSWORD=Clave-segura-123 uv run python -m app.cli inicializar
uv run uvicorn app.main:app --reload          # http://localhost:8000/api/docs

# Frontend (otra terminal)
cd frontend
npm install
npm run dev                                   # http://localhost:5173
```

### Pruebas y calidad

```bash
# Backend: necesita una base de pruebas vacía (se recrea en cada corrida)
docker compose exec db createdb -U inventario inventario_test
cd backend
TEST_DATABASE_URL=postgresql+psycopg://inventario:CLAVE@localhost:5433/inventario_test uv run pytest
uv run ruff format --check . && uv run ruff check . && uv run mypy app tests

# Frontend
cd frontend
npm run lint && npm run typecheck && npm test && npm run build
```

La integración continua (`.github/workflows/ci.yml`) ejecuta lo mismo en cada push.

## Variables de entorno

Todas están documentadas en [`.env.example`](.env.example). Las más importantes:

| Variable | Uso |
|---|---|
| `POSTGRES_PASSWORD` | Clave de la base de datos |
| `ENTORNO` | `desarrollo` o `produccion` (en producción no se pueden cargar datos demo) |
| `COOKIE_SEGURA` | `true` cuando se sirve por HTTPS |
| `DUENO_CORREO`, `DUENO_PASSWORD` | Usuario dueño creado por `inicializar` |
| `PUERTO_WEB` | Puerto del sistema en este equipo (por defecto 8080) |

## Respaldos

```bash
scripts/respaldo.sh        # crea respaldos/inventario_FECHA.sql.gz y borra los de más de 30 días
```

Prográmelo a diario con `cron` y copie la carpeta `respaldos/` fuera del equipo. El script
explica cómo restaurar.

## Estructura

```
backend/        API (FastAPI), migraciones (Alembic), pruebas
frontend/       Aplicación web / PWA (React + TypeScript)
infra/          Caddy y Dockerfile del servidor web
scripts/        Utilidades (respaldos)
docs/           Arquitectura, decisiones de negocio y ADRs
```

## Documentación

- [Arquitectura y modelo de datos](docs/arquitectura.md)
- [Decisiones de negocio](docs/decisiones-negocio.md)
- [ADRs](docs/adr/): stack, despliegue en oficina, lectura de OC sin costo
- [Especificación](PROMPT_sistema_inventario.md)
- API interactiva: `/api/docs`
