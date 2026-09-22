[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

# Schemio

Transforme scripts SQL em diagramas entidade-relacionamento (ER) de forma automática, visual e intuitiva.  
Automatically transform SQL scripts into intuitive and visual entity-relationship (ER) diagrams.

---

## 📌 Status atual | Current status

Este projeto está na fase de **Fundação (Phase 1)**: um monorepo pnpm com um "vertical slice" de health-check
já funcionando de ponta a ponta (frontend → API → banco de dados, com deploy real). A funcionalidade de
converter SQL em diagrama ainda não existe — ela é o objetivo da Fase 2.  
This project is in its **Foundation (Phase 1)** phase: a pnpm monorepo with a health-check vertical slice
already working end-to-end (frontend → API → database, with a real deployment). The actual SQL-to-diagram
feature does not exist yet — that is the goal of Phase 2.

O roteiro completo (parsing multi-dialeto, autenticação, projetos salvos, exportação, etc.) está documentado
em `docs/superpowers/specs/`.  
The full roadmap (multi-dialect SQL parsing, authentication, saved projects, export, etc.) is documented in
`docs/superpowers/specs/`.

### O que já existe | What exists today

- Monorepo pnpm (`apps/web`, `apps/api`, `packages/ui`, `packages/api-client`)  
  pnpm workspace monorepo (`apps/web`, `apps/api`, `packages/ui`, `packages/api-client`)
- Frontend em Vite + React que chama um endpoint `/api/health`  
  Vite + React frontend that calls an `/api/health` endpoint
- Backend em FastAPI + SQLAlchemy, com Postgres via Neon  
  FastAPI + SQLAlchemy backend, using Postgres via Neon
- Deploy contínuo na Vercel (frontend estático + função Python serverless)  
  Continuous deployment on Vercel (static frontend + Python serverless function)
- Cliente TypeScript (`packages/api-client`) gerado a partir do schema OpenAPI da API  
  TypeScript client (`packages/api-client`) generated from the API's OpenAPI schema

### O que está planejado | What's planned

- Parsing de múltiplos dialetos SQL (PostgreSQL, MySQL, SQL Server) e detecção de chaves primárias/estrangeiras  
  Multi-dialect SQL parsing (PostgreSQL, MySQL, SQL Server) and primary/foreign key detection
- Autenticação e projetos salvos  
  Authentication and saved projects
- Visualização do diagrama e exportação (PNG/SVG/PDF)  
  Diagram visualization and export (PNG/SVG/PDF)

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

Create `apps/api/.env` with a Neon connection string (see `docs/superpowers/specs/2026-09-16-foundation-design.md`).

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
