# ADR 0001 — Stack tecnológico

- **Estado:** aceptada (2026-11-14)

## Contexto

Sistema de gestión con un núcleo transaccional (inventario, pedidos) y componentes de visión y ML
(lectura de órdenes de compra, emparejamiento de productos, pronóstico). Lo mantiene una sola
persona. Los repartidores usan celulares Android de gama media con conexión irregular.

## Decisión

| Capa | Elección |
|---|---|
| Backend | Python 3.13 · FastAPI · SQLAlchemy 2 (síncrono) · Alembic · Pydantic v2 |
| Base de datos | PostgreSQL 17 (`pg_trgm` y `pgvector` cuando se necesiten) |
| Tareas en segundo plano | Celery + Redis |
| Frontend | React 19 · TypeScript · Vite · Tailwind 4 · TanStack Query · React Router · React Hook Form + Zod |
| PWA | vite-plugin-pwa (Workbox) |
| Autenticación | Sesión en cookie `httpOnly` + token CSRF por sesión · Argon2 |
| Calidad | ruff, mypy (estricto), pytest · oxlint, tsc, vitest |
| Infraestructura | Docker Compose · Caddy |

## Razones

- **Un solo lenguaje de backend.** La lectura de documentos (pdfplumber, OpenCV, PaddleOCR) y el
  ML (statsmodels, scikit-learn) viven en Python. Evita mantener PHP + Python.
- **SPA + API en lugar de Inertia:** la PWA debe funcionar con mala conexión (cola de subida de
  fotos), lo que requiere un frontend desacoplado.
- **SQLAlchemy síncrono:** con 4–5 usuarios no hace falta código asíncrono; el síncrono es más
  simple de leer, depurar y probar. FastAPI ejecuta los endpoints síncronos en un pool de hilos.
- **Sesiones con cookie en lugar de JWT:** frontend y API comparten dominio; las sesiones se pueden
  revocar al instante (desactivar usuario, cambiar contraseña) y el token no queda expuesto a JS.
- **Monolito modular:** un solo despliegue, con módulos de dominio separados para crecer hacia
  finanzas sin reescribir.

## Alternativas descartadas

- **Laravel + Inertia + React:** excelente para CRUD, pero obliga a un segundo backend en Python
  para IA/ML y encaja mal con una PWA tolerante a fallos de red.
- **Microservicios:** sin volumen ni equipo que los justifique.
