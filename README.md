[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

# Schemio

Transforme scripts SQL em diagramas entidade-relacionamento (ER) de forma automática, visual e intuitiva.  
Automatically transform SQL scripts into intuitive and visual entity-relationship (ER) diagrams.

---

## 📌 Status atual | Current status

Este projeto está na fase de **Domínios (Fases 2–3)**: o parsing de SQL já funciona de ponta a ponta
(multi-dialeto: PostgreSQL, MySQL, SQLite, SQL Server), com detecção de tabelas, chaves primárias e
estrangeiras, relacionamentos (explícitos, inferidos e N:N) e avisos estruturais, tudo exposto via
`POST /api/schema/parse`. Também já existem autenticação JWT (`/api/auth/*`) e projetos salvos
(`/api/projects`). A visualização do diagrama é o objetivo da Fase 4.
This project is in its **Domains (Phases 2–3)** phase: SQL parsing works end-to-end (multi-dialect:
PostgreSQL, MySQL, SQLite, SQL Server), extracting tables, primary/foreign keys, relationships
(explicit, inferred, and N:N) and structural warnings through `POST /api/schema/parse`. JWT
authentication (`/api/auth/*`) and saved projects (`/api/projects`) are also implemented. The
diagram visualization is the goal of Phase 4.

O roteiro completo (parsing multi-dialeto, autenticação, projetos salvos, exportação, etc.) está documentado
em `docs/superpowers/specs/`.  
The full roadmap (multi-dialect SQL parsing, authentication, saved projects, export, etc.) is documented in
`docs/superpowers/specs/`.

### O que já existe | What exists today

- Monorepo pnpm (`apps/web`, `apps/api`, `packages/ui`, `packages/api-client`)  
  pnpm workspace monorepo (`apps/web`, `apps/api`, `packages/ui`, `packages/api-client`)
- Frontend em Vite + React com health-check e estado de retry  
  Vite + React frontend with a health check and retry state
- Backend em FastAPI + SQLAlchemy, com Postgres via Neon  
  FastAPI + SQLAlchemy backend, using Postgres via Neon
- Parsing de SQL multi-dialeto com relacionamentos e avisos estruturais  
  Multi-dialect SQL parsing with relationships and structural warnings
- Autenticação JWT (access + refresh com rotação e detecção de reuso) e projetos salvos  
  JWT auth (access + refresh with rotation and reuse detection) and saved projects
- Migrations com Alembic  
  Alembic migrations
- Deploy contínuo na Vercel (frontend estático + função Python serverless)  
  Continuous deployment on Vercel (static frontend + Python serverless function)
- Cliente TypeScript (`packages/api-client`) gerado a partir do schema OpenAPI da API  
  TypeScript client (`packages/api-client`) generated from the API's OpenAPI schema

### O que está planejado | What's planned

- Visualização do diagrama e exportação (PNG/SVG/PDF)  
  Diagram visualization and export (PNG/SVG/PDF)
- Suporte a schemas múltiplos (namespaces) no parsing  
  Multi-schema (namespace) support in parsing

Consulte `docs/superpowers/specs/` para os detalhes de design de cada fase.  
See `docs/superpowers/specs/` for the design details of each phase.

---

## 🛠️ Tecnologias | Technologies

- [Vite](https://vitejs.dev/) + [React](https://react.dev/) (`apps/web`)
- [TypeScript](https://www.typescriptlang.org/)
- [FastAPI](https://fastapi.tiangolo.com/) + [SQLAlchemy](https://www.sqlalchemy.org/) (`apps/api`)
- [PostgreSQL](https://www.postgresql.org/) via [Neon](https://neon.tech/)
- [Vercel](https://vercel.com/) (deploy)

---

## Development

This is a pnpm monorepo:

- `apps/web` — Vite + React frontend
- `apps/api` — FastAPI backend
- `packages/ui` — shared React components
- `packages/api-client` — TS types generated from the API's OpenAPI schema

### Setup

```bash
pnpm install
cd apps/api && python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"
```

Create `apps/api/.env` with:

```bash
DATABASE_URL=postgresql://user:pass@host/db
JWT_SECRET=at-least-32-characters-long-secret
CORS_ALLOW_ORIGINS=["http://localhost:5173"]
```

`JWT_SECRET` is required to be at least 32 characters. Then apply the migrations:

```bash
cd apps/api && alembic upgrade head
```

### Run locally

```bash
# terminal 1
cd apps/api && uvicorn src.main:app --reload

# terminal 2
pnpm --filter web dev
```

### Test

```bash
pnpm --filter web test
cd apps/api && pytest
```

### Updating the generated API client

`packages/api-client` is generated from `apps/api`'s real OpenAPI schema and must never drift from it
(CI enforces this, see `.github/workflows/ci.yml`). After changing any API route or schema, regenerate it:

```bash
cd apps/api && python scripts/export_openapi.py
cd packages/api-client && pnpm generate
```

Commit the resulting changes to `packages/api-client/openapi.json` and `packages/api-client/src/schema.ts`.

---

## 📄 Licença | License

Este projeto está sob a licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.  
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
