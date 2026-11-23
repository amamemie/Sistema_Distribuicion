<div align="center">

# Inventory · Orders · Profitability

**A full-stack operations system for a wholesale distributor that supplies supermarkets in La Paz, Bolivia.**

Stock across warehouses and branches · supermarket orders read automatically from PDFs and photos ·
real profit per order · receivables and taxes · demand forecasting and restock alerts.

[**▶ Live demo**](https://amamemie.github.io/Sistema_Distribuicion/) ·
[Screenshots](#screenshots) ·
[Tech stack](#tech-stack) ·
[Run it locally](#getting-started) ·
[Documentación en español](docs/README.es.md)

![Home dashboard — dark theme](docs/screenshots/home-dark.png)

</div>

---

## The problem

The client buys cleaning products (gloves, bags, cloths…) in bulk, stores them in warehouses,
splits them into smaller packs at branch locations and delivers to supermarket chains such as
Hipermaxi. Before this system, everything lived in notebooks and spreadsheets:

- Nobody knew **exactly how much stock** there was, or where.
- Supermarket orders arrive as **receiving notes (PDF or paper)** and were retyped by hand, with errors.
- There was no way to know **how much each order actually earned**.
- It was hard to track **which supermarket owed what**, and since when.
- No one was warned when a product was **about to run out**.

## What it does

| Area | Highlights |
|---|---|
| **Inventory** | Stock per location (warehouses and branches), lots with expiry dates (FEFO), weighted-average cost, transfers, adjustments with approval, physical counts and a full stock card (kardex). Stock only changes through an append-only movement ledger. |
| **Orders** | Upload a supermarket receiving note (PDF, photo or gallery) and the system **reads it automatically** — order number, store, products, quantities and prices — then a person reviews, confirms (reserves stock), picks and delivers it with proof of delivery (photo/signature). Works offline on phones and uploads when the signal returns. |
| **Profitability** | Cost is frozen when an order is picked, so every order shows its real revenue, cost, profit and margin, including returns and shrinkage. |
| **Reports** | Profit, products, customers, inventory value and turnover, shrinkage, purchase prices and user activity — with charts and **Excel / PDF export**. |
| **Alerts & forecasting** | Checks every 10 minutes: low stock, out of stock, expiring lots, unusual prices or quantities, low margins, overdue payments. A weekly **demand forecast** picks the best method per product from its own sales history and suggests what to transfer to each branch and what to buy. |
| **Finance** | Receivables per supermarket chain (paid by monthly bank transfer, applied oldest-first), expenses, credit purchases, **VAT (IVA 13 %) and IT (3 %)**, income statement and cash flow. |
| **Security** | Roles and granular permissions (e.g. staff never see costs), multi-location access, CSRF-protected cookie sessions, Argon2 passwords and a **tamper-proof audit log** of who did what and when. |
| **Experience** | Mobile-first PWA, **light and dark themes**, **English and Spanish**, a 3D scene on the login and home screens, keyboard and screen-reader accessible. |

## Screenshots

> All screenshots use **sample data** from the demo — no real company data.

| | |
|---|---|
| ![Sign-in screen with 3D scene](docs/screenshots/login-dark.png) | ![Home dashboard, light theme](docs/screenshots/home-light.png) |
| **Sign in** — 3D scene of packages travelling between warehouses and branches | **Home** — today's work, receivables and quick actions |
| ![Orders list](docs/screenshots/orders.png) | ![Receivables per supermarket chain](docs/screenshots/receivables-dark.png) |
| **Orders** — from receiving note to delivery, with margin per order | **Receivables** — what each supermarket chain owes, overdue amounts |
| ![Profit report](docs/screenshots/reports.png) | ![Restocking plan](docs/screenshots/restocking-dark.png) |
| **Reports** — charts, period comparison, Excel/PDF export | **Restocking** — forecast, safety stock and reorder point per product |

<p align="center"><img src="docs/screenshots/mobile-home.png" alt="Home on a phone" width="300"></p>

## Live demo

**👉 [amamemie.github.io/Sistema_Distribuicion](https://amamemie.github.io/Sistema_Distribuicion/)**

The demo is the real frontend running **without a backend**: API responses recorded from a test
instance with sample data are served in the browser. You can open every screen, switch language
and theme, and try it on your phone — changes are not saved and file exports are disabled.

## Tech stack

| Layer | Technologies |
|---|---|
| **Frontend** | React 19, TypeScript, Vite, Tailwind CSS 4, TanStack Query, React Router, React Hook Form + Zod, i18next, Motion, three.js / React Three Fiber, PWA (Workbox) |
| **Backend** | Python 3.13, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2 |
| **Background jobs** | Celery + Redis (document reading, alerts every 10 min, weekly forecast) |
| **Database** | PostgreSQL 17 (exact `NUMERIC` money, row locking, immutable ledger and audit triggers) |
| **Document reading** | Local OCR (RapidOCR / ONNX Runtime) + pdfplumber, with per-chain templates — **no paid AI service** |
| **Reports** | openpyxl (Excel) and fpdf2 (PDF) generated server-side from one report model |
| **Infrastructure** | Docker Compose, Caddy (HTTPS + reverse proxy), Tailscale Funnel for public HTTPS from an office PC |
| **Quality** | pytest against a real PostgreSQL (140+ backend + frontend tests), Ruff, mypy, oxlint, Vitest, GitHub Actions CI |

## How it works

```mermaid
flowchart LR
  subgraph Browser["Browser / phone (PWA)"]
    UI["React app<br/>ES · EN · light/dark"]
  end
  UI -- "HTTPS /api" --> Caddy
  Caddy["Caddy<br/>static files + reverse proxy"] --> API["FastAPI<br/>business services"]
  API --> DB[("PostgreSQL<br/>ledger · audit · data")]
  API -- "queue" --> Redis[(Redis)]
  Redis --> Worker["Celery worker<br/>OCR · alerts · forecast"]
  Beat["Celery beat<br/>schedules"] --> Redis
  Worker --> DB
  API --> Files[("Uploaded files<br/>notes · receipts")]
  Worker --> Files
```

**Design principles**

- **One transaction per use case.** Each service validates, changes data, writes the audit entry
  and commits once — never half-done.
- **Stock is never edited directly.** Every change is a movement in an append-only ledger
  (protected by a database trigger). Corrections are reversing movements, and a verification
  endpoint recomputes all balances from the ledger.
- **Nothing is physically deleted.** Records are voided with a reason; the audit log cannot be
  updated or deleted, not even by the application.
- **Concurrency-safe.** Stock and receivables use row locks, so two people can never sell the same
  units or apply the same payment twice (covered by tests).
- **Domain events (outbox).** Purchases, deliveries, payments and expenses publish events, ready
  for a future double-entry accounting module.
- **Zero running cost.** Local OCR instead of a paid API, free hosting options, daily backups.

## Getting started

Requirements: Docker with Docker Compose v2.

```bash
git clone https://github.com/amamemie/Sistema_Distribuicion.git
cd Sistema_Distribuicion
cp .env.example .env                       # set your own passwords
docker compose up -d --build
docker compose exec backend python -m app.cli inicializar   # permissions, roles, owner user
docker compose exec backend python -m app.cli demo          # optional sample data (not for production)
```

Open `http://localhost:8080` and sign in with `DUENO_CORREO` / `DUENO_PASSWORD` from your `.env`.

### Development

```bash
# Backend (backend/)
uv sync
uv run uvicorn app.main:app --reload           # API on :8000, docs at /docs
TEST_DATABASE_URL=postgresql+psycopg://USER:PASS@localhost:5433/inventario_test uv run pytest

# Frontend (frontend/)
npm ci
npm run dev                                     # :5173, proxies /api to :8000
npm run lint && npm run typecheck && npm test && npm run build
npm run build:demo                              # static demo for GitHub Pages
```

## Project structure

```
backend/
  app/modules/<module>/   models · schemas · services · api   (inventory, orders, purchases,
                          finance, reports, alerts, identity…)
  migrations/             Alembic migrations
  tests/                  pytest against real PostgreSQL
frontend/
  src/pages/              screens          src/components/   shared UI, 3D scene
  src/i18n/               translations     src/demo/          sample data for the live demo
docs/                     architecture, business decisions, design system, deployment guides
scripts/                  backups, server install, move-to-another-PC
```

## Documentation

The project documentation is written in Spanish (the client's language):

- [Architecture and data model](docs/arquitectura.md) · [Business decisions](docs/decisiones-negocio.md) · [Architecture decision records](docs/adr/)
- [Design system](docs/DESIGN.md) · [Languages / i18n](docs/idiomas.md)
- Deployment: [free Oracle Cloud server](docs/despliegue-oracle.md) · [Windows office PC](docs/instalacion-oficina-windows.md)
- [Full Spanish README](docs/README.es.md) (setup, environment variables, backups)

## Status

In production for the client. Built in phases: foundation → inventory → orders and automatic
reading → reports → alerts and forecasting → finance → redesign (themes, 3D, i18n).

Next: translating server-generated texts (report titles, alerts, API errors) to English, reading
templates for more supermarket chains, and electronic invoicing with Bolivia's tax service (SIN).
