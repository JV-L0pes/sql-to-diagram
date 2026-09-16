# Foundation — Monorepo, DDD/FSD Skeleton, CI (Phase 1 of 5)

## Context

`sql-to-diagram` is a June 2025 personal project (Next.js SPA, no backend) that
converts pasted SQL into an ER diagram. It is being revamped end to end. The
full roadmap is:

1. **Foundation** (this spec) — monorepo, app skeletons, lint/test/CI, DB
   connectivity, no features yet.
2. **Schema Design domain** — real multi-dialect SQL parsing (sqlglot),
   relationship detection, normalization/naming validation.
3. **Identity & Projects domain** — auth (JWT), saved projects, DB schema.
4. **Frontend/UI** — shadcn + "Ink" design system (adapted from
   github.com/JV-L0pes/JV-L0pes_Portfolio), SQL editor, diagram canvas,
   PNG/SVG export.
5. **NoSQL/Mongo** — "coming soon" placeholder only.

Phases 2-5 each get their own spec once Foundation is implemented. This
document covers **Phase 1 only**: the skeleton everything else is built on.

### Why a rewrite instead of incremental changes

The current `src/lib/sqlParser.ts` is a hand-rolled regex parser (not the
`sql-parser-cst` dependency it lists, which is unused and doesn't support
SQL Server anyway). Parsing, relationship-inference heuristics, and UI are
all tangled in two files with zero tests. Given the target architecture
(modular monolith, DDD bounded contexts, FSD frontend, two runtimes
TS+Python), continuing to patch the existing structure is not viable —
Foundation replaces the project layout wholesale while the current app
keeps working until Phase 2 lands the new parser behind the new API.

## Goals

- Establish the monorepo layout, tooling, and CI that every later phase
  builds on.
- Stand up **both** runtimes end-to-end with a trivial vertical slice
  (a "hello world" call from `apps/web` to `apps/api` and back), proving
  the deploy path on Vercel works, before any real feature is built.
- Leave no ambiguity for later phases about where code goes (bounded
  context boundaries, layer boundaries, package boundaries).

## Non-goals (explicitly deferred to later phases)

- Real SQL parsing/relationship detection (Phase 2).
- Auth, user accounts, saved projects (Phase 3).
- New visual design, shadcn components, diagram rendering (Phase 4).
- Any NoSQL/Mongo work (Phase 5).
- Removing the current `src/` Next.js app's *behavior* — it can be deleted
  once Phase 4 ships a replacement UI; Foundation does not need to keep it
  running, but does not need to port its features either.

## Architecture

### Monorepo layout

```
sql-to-diagram/
├── apps/
│   ├── web/                       # Vite + React SPA
│   │   └── src/
│   │       ├── app/               # composition root: providers, router, global styles
│   │       ├── pages/             # route-level components
│   │       ├── widgets/           # composed UI blocks (multi-feature)
│   │       ├── features/          # single user actions (e.g. convert-sql)
│   │       ├── entities/          # UI-facing domain concepts (TableCard, etc.)
│   │       └── shared/            # generic UI kit, hooks, lib utilities
│   └── api/                       # FastAPI app
│       └── src/
│           ├── schema_design/     # bounded context (Phase 2 lives here)
│           │   ├── domain/
│           │   ├── application/
│           │   ├── infrastructure/
│           │   └── interfaces/    # FastAPI routers + Pydantic schemas
│           ├── identity/          # bounded context (Phase 3 lives here)
│           │   ├── domain/
│           │   ├── application/
│           │   ├── infrastructure/
│           │   └── interfaces/
│           ├── shared_kernel/     # cross-context: settings, DB session, error types
│           └── main.py            # FastAPI app factory, router registration
├── packages/
│   ├── ui/                        # shared shadcn-based React components + Ink theme tokens
│   └── api-client/                # TS types generated from apps/api's OpenAPI schema
├── docs/
│   └── superpowers/specs/
├── .github/workflows/ci.yml
├── pnpm-workspace.yaml
├── biome.json
├── eslint.config.mjs              # react-hooks + jsx-a11y only
├── pyproject.toml                 # ruff config (root, applies to apps/api)
└── vercel.ts
```

Each bounded context under `apps/api/src/` follows the same four layers:

- `domain/` — entities, value objects, domain services. No FastAPI, no
  SQLAlchemy imports here.
- `application/` — use cases (e.g. `ParseSqlSchema`, `RegisterUser`)
  orchestrating domain objects. Depends on domain, not on infrastructure
  concretions (uses ports/interfaces).
- `infrastructure/` — SQLAlchemy models/repositories, external library
  adapters (sqlglot wrapper lands here in Phase 2). Implements the ports
  application defines.
- `interfaces/` — FastAPI routers, Pydantic request/response schemas.
  Translates HTTP <-> application layer. No business logic here.

`shared_kernel/` holds only what genuinely has no owning context: app
settings, the DB session/engine, and a common error-response shape. It
must stay small — if two contexts want to share a domain concept, that's
a sign that concept belongs in one of them with the other depending on
its public interface, not a growing shared kernel.

### Why two packages, not one `packages/core`

The original brainstorm proposed a TS `packages/core` for parsing domain
logic. That's superseded: parsing was moved to `apps/api` (Python,
sqlglot) so there is a single source of truth instead of duplicating
complex multi-dialect logic in two languages — see "Key decisions"
below. `packages/api-client` replaces it as the TS-side contract: it is
*generated*, not hand-written, so it can never drift from what the API
actually returns.

### Data flow (the Foundation vertical slice)

```
apps/web  --GET /api/health-->  apps/api (interfaces/health.py)
apps/web  <--{"status":"ok","db":"ok"}--  apps/api
```

`apps/api`'s health check queries the DB (`SELECT 1` against the Neon
connection) so a green check proves both the app boot path and DB
connectivity, not just that the process started.

### Deployment

- **Target**: Vercel (paid Hobby/Pro tier acceptable per user; free tier
  may hit Python function limits — verify during implementation).
- `apps/web` builds as a static Vite SPA.
- `apps/api` deploys as a Vercel Python Function (FastAPI ASGI app),
  configured via `vercel.ts` rewrites (`/api/*` → `apps/api`).
- **Database**: Neon Postgres via Vercel Marketplace integration
  (`vercel integration add neon`), which auto-provisions `DATABASE_URL`.
  A separate Neon **branch** is used for local development (no local
  Postgres, no Docker).
- Docker is removed entirely in this phase: `Dockerfile`, `Dockerfile.dev`,
  `docker-compose.yml`, `docker/`, and the `Makefile` targets that call
  them. Vercel does not run arbitrary containers, so they serve no
  purpose in the new deploy path.

### Tooling

| Concern | Tool | Scope |
|---|---|---|
| Package/workspace manager | pnpm workspaces | whole repo (TS side) |
| TS build/dev server | Vite | `apps/web` |
| TS lint + format | Biome | whole repo (TS/JSON/CSS) |
| TS React-specific lint | ESLint (`eslint-plugin-react-hooks`, `eslint-plugin-jsx-a11y` only) | `apps/web`, `packages/ui` |
| TS test runner | Vitest + React Testing Library | `apps/web`, `packages/ui` |
| Python package manager | pip + `pyproject.toml` (or uv if faster — decide at implementation time) | `apps/api` |
| Python lint + format | Ruff | `apps/api` |
| Python test runner | pytest | `apps/api` |
| Python web framework | FastAPI | `apps/api` |
| Python ORM/migrations | SQLAlchemy + Alembic | `apps/api` |
| CI | GitHub Actions, two parallel jobs (`web`, `api`) | whole repo |

### Testing strategy for this phase

Foundation ships minimal but real tests to prove the harness works —
not feature coverage (there's no feature yet):

- `apps/api`: one pytest unit test for a trivial domain-layer function
  (proves the domain layer is importable and testable in isolation, with
  zero FastAPI/DB dependency), one integration test hitting `/api/health`
  via `TestClient` against a real (Neon dev branch) DB connection.
- `apps/web`: one Vitest unit test, one Testing Library component test
  for a trivial shared component, one test that the app can call
  `/api/health` and render its result (msw or a thin fetch mock — decided
  at implementation time).
- CI fails the build if lint, tests, or `vite build` / `uvicorn` import
  fail.

### Error handling

- `apps/api` defines one JSON error shape in `shared_kernel` (e.g.
  `{ "error": { "code": str, "message": str, "details"?: object } }`)
  used by all contexts, so `apps/web` has one error-parsing path.
  Domain/application layers raise typed exceptions; `interfaces/` maps
  them to HTTP status codes. No bare `except: pass` / silent
  `console.error`-style swallowing anywhere — this was a concrete bug
  class in the current code (`sqlParser.ts` swallows parse errors and
  returns an empty schema).
- Config/env errors (missing `DATABASE_URL`, etc.) fail fast at startup,
  not on first request.

## Key decisions (recap, already agreed with the user)

- **Parsing runs in the backend (Python/sqlglot), not the browser.** The
  current UI is click-to-convert (not live-as-you-type), so the
  round-trip cost is irrelevant, and sqlglot's dialect coverage
  (including T-SQL) is materially better than any TS alternative. The
  `/api/schema/parse` endpoint (Phase 2) is public — no auth required —
  since only saving/loading projects needs a logged-in user.
- **Auth is self-rolled JWT** (email+password, bcrypt/argon2 hashing) in
  FastAPI — no third-party auth provider.
- **DB is Postgres via Neon**, chosen per Vercel's own marketplace
  guidance for relational data on Vercel.
- **Visual design** adapts the "Ink" editorial system from the user's
  portfolio (monochrome paper/ink palette + single gold accent, Archivo +
  Martian Mono typefaces, no gradients/shadows/glassmorphism) — detailed
  in the Phase 4 spec, not this one.

## Open questions for implementation time (not blocking this spec)

- Exact Vercel Python function config (`vercel.ts` rewrite syntax for a
  FastAPI ASGI app) — verify against current Vercel Python docs when
  implementing, since this is a fast-moving area.
- pip vs uv for Python dependency management — pick whichever the
  implementer finds simpler to wire into CI; doesn't affect architecture.
- Whether `apps/web` needs a fetch-mocking library (msw) for the health
  check test, or a simpler manual mock suffices — trivial either way.
