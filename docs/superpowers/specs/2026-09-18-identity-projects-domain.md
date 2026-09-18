# Identity & Projects Domain (Phase 3 of 5)

## Context

Phases 1-2 built the monorepo (`apps/web` + `apps/api`), CI/deploy, and a
public, stateless `schema_design` bounded context (real multi-dialect SQL
parsing). This phase adds the `identity` bounded context, scaffolded but
empty since Phase 1: user accounts (JWT auth) and saved projects (a named
SQL script + dialect a user can come back to).

## Goals

- Let a user register, log in, and stay logged in via short-lived access
  tokens + longer-lived, revocable refresh tokens.
- Let a logged-in user save, list, view, update, and delete named SQL
  "projects" (name + SQL text + dialect) — the only content saved; parsing
  still runs on demand via the existing `schema_design` endpoint when a
  project is opened, not duplicated/cached here.
- Keep `schema_design`'s public parsing endpoint exactly as-is — no auth
  requirement added to it. Auth is additive, scoped entirely to new
  `/api/auth/*` and `/api/projects/*` endpoints.

## Non-goals (explicitly deferred)

- Any frontend UI (login form, project list) — Phase 4.
- Email verification, password reset via email — no email-sending
  provider exists in this project yet; deferred to a future phase if
  needed.
- Caching a project's parsed schema result — re-parsing on open is cheap
  (Phase 2's endpoint) and avoids storing data that can drift from what
  the current parser would produce.
- OAuth/social login, MFA, roles/permissions beyond simple ownership.
- Any change to `schema_design`'s public, unauthenticated `/api/schema/parse`.

## Architecture

```
apps/api/src/identity/
├── domain/
│   ├── user.py             # User entity (id, email, password_hash, created_at)
│   ├── project.py          # Project entity (id, user_id, name, sql, dialect, created_at, updated_at)
│   └── errors.py           # EmailAlreadyRegisteredError, InvalidCredentialsError,
│                            # InvalidRefreshTokenError, ProjectNotFoundError
├── application/
│   ├── register_user.py
│   ├── authenticate_user.py    # login: verify credentials, issue token pair
│   ├── refresh_access_token.py # rotate: verify+revoke old refresh token, issue new pair
│   ├── logout.py                # revoke a refresh token
│   ├── create_project.py
│   ├── list_projects.py
│   ├── get_project.py
│   ├── update_project.py
│   └── delete_project.py
├── infrastructure/
│   ├── models.py            # SQLAlchemy ORM: UserModel, ProjectModel, RefreshTokenModel
│   ├── user_repository.py
│   ├── project_repository.py
│   ├── password_hasher.py   # argon2 wrapper: hash(), verify()
│   └── jwt_service.py       # encode/decode access tokens (HS256, shared_kernel settings secret)
└── interfaces/
    ├── schemas.py           # Pydantic request/response models
    ├── dependencies.py      # get_current_user: Bearer-token FastAPI dependency
    ├── auth_router.py       # /api/auth/register, /login, /refresh, /logout
    └── projects_router.py   # /api/projects (GET list, POST create, GET/PUT/DELETE {id})
```

Same four-layer discipline as `schema_design`: `domain/` has zero
FastAPI/SQLAlchemy/argon2/jwt-library imports — it only knows `User`,
`Project`, and the rules around them (e.g. "a project belongs to exactly
one user"). `infrastructure/` is the only layer touching SQLAlchemy,
argon2, and the JWT library.

## Database Schema (Alembic migration)

```sql
users (
  id            UUID PRIMARY KEY,
  email         VARCHAR(255) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  created_at    TIMESTAMP NOT NULL DEFAULT now()
)

projects (
  id         UUID PRIMARY KEY,
  user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name       VARCHAR(200) NOT NULL,
  sql        TEXT NOT NULL,
  dialect    VARCHAR(20) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT now(),
  updated_at TIMESTAMP NOT NULL DEFAULT now()
)

refresh_tokens (
  id          UUID PRIMARY KEY,
  user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash  VARCHAR(255) NOT NULL,  -- SHA-256 of the raw token; raw token never stored
  expires_at  TIMESTAMP NOT NULL,
  revoked_at  TIMESTAMP NULL,
  created_at  TIMESTAMP NOT NULL DEFAULT now()
)
```

`refresh_tokens` stores a hash of the token, not the raw value (same
principle as password hashing — a DB leak shouldn't hand out usable
tokens). Lookup on refresh: hash the incoming raw token, query by
`token_hash`, check `revoked_at IS NULL AND expires_at > now()`.

## API Contract

```
POST /api/auth/register
{ "email": "user@example.com", "password": "..." }
201 { "id": "<uuid>", "email": "user@example.com" }
409 (email already registered) — error_body("email_already_registered", ...)

POST /api/auth/login
{ "email": "...", "password": "..." }
200 { "access_token": "...", "refresh_token": "...", "token_type": "bearer" }
401 (bad credentials) — error_body("invalid_credentials", ...)

POST /api/auth/refresh
{ "refresh_token": "..." }
200 { "access_token": "...", "refresh_token": "...", "token_type": "bearer" }
401 (expired/revoked/unknown token) — error_body("invalid_refresh_token", ...)

POST /api/auth/logout
{ "refresh_token": "..." }
204 No Content

GET    /api/projects            (Bearer auth)  -> 200 [ProjectSummary...]
POST   /api/projects            (Bearer auth)  -> 201 Project
GET    /api/projects/{id}       (Bearer auth)  -> 200 Project | 404
PUT    /api/projects/{id}       (Bearer auth)  -> 200 Project | 404
DELETE /api/projects/{id}       (Bearer auth)  -> 204 | 404

ProjectSummary: { id, name, dialect, updated_at }
Project:        { id, name, sql, dialect, created_at, updated_at }
```

All `/api/projects/*` routes require `Authorization: Bearer <access_token>`
(missing/invalid/expired token → 401). A project that doesn't exist, OR
exists but belongs to a different user, both return 404 — never 403 —
so an attacker can't distinguish "not found" from "not yours" (standard
anti-enumeration practice).

## Auth Flow Details

- **Access token**: JWT, HS256, signed with a secret from `shared_kernel.settings` (new `jwt_secret: str` field — fails fast at startup if missing, same pattern as `database_url`). 30-minute expiry. Payload: `{"sub": "<user_id>", "exp": ...}`. Verified per-request by the `get_current_user` dependency; no DB lookup needed for access-token validation (stateless, fast).
- **Refresh token**: opaque random string (not a JWT — no need for it to be self-describing, and an opaque token is easier to revoke by DB lookup), 30-day expiry, rotated on every use (old one marked `revoked_at = now()`, a new one issued) — this limits the damage of a stolen refresh token to one use before detection (reusing a revoked token is a signal of compromise, though this phase doesn't add active alerting on that signal — just correctness: a revoked token's refresh attempt returns 401).
- **Password hashing**: `argon2-cffi`, default parameters (OWASP-recommended defaults are fine at this project's scale — no custom tuning).
- **Logout**: revokes the specific refresh token passed in; does not revoke the current access token (it simply expires within 30 minutes — accepted tradeoff, avoids needing an access-token blocklist for a personal-scale project).

## Error Handling

- Domain-layer exceptions (`EmailAlreadyRegisteredError`, `InvalidCredentialsError`, `InvalidRefreshTokenError`, `ProjectNotFoundError`) are raised by `application/` use cases and caught specifically at the `interfaces/` router layer, each mapped to its documented HTTP status via the shared `error_body()` shape — same pattern `schema_design` already established in Phase 2 (typed exceptions, no bare `except`, no silent fallback).
- Password/token values are never logged or included in any error message.

## Testing

- **Unit**: `PasswordHasher.hash()`/`.verify()` round-trip and wrong-password rejection; `JwtService.encode()`/`.decode()` round-trip and expired/tampered-token rejection; domain entity/exception behavior.
- **Integration** (`TestClient` + the existing SQLite override pattern from Phases 1-2, no real Neon needed): full register → login → access a protected route → refresh → logout flow; project CRUD including the ownership check (user A cannot GET/PUT/DELETE user B's project — asserted via two distinct test users in the same test).
- Given/When/Then style per the project's established testing convention (see Phase 2's spec/plan for the pattern).

## Key Decisions

- **Refresh tokens are DB-backed and revocable**, not stateless JWTs, so logout and compromise-response are actually possible — the cost (one extra table, one DB query per refresh) is worth it for a real auth system, unlike Phase 2's health-check tests which deliberately avoided DB dependency for CI simplicity (that tradeoff doesn't apply here, since these endpoints are inherently DB-backed already).
- **No caching of parsed schema on a saved project** — keeps `Project` a thin, simple record and avoids a second source of truth that could drift from what `schema_design`'s parser currently produces; re-parsing on open is cheap.
- **argon2 over bcrypt** — current OWASP first recommendation.
- **404, not 403, for "not yours"** — prevents project-ID enumeration revealing which IDs exist.
- **Backend-only this phase** — consistent with Phase 2; Phase 4 builds the login/project UI against these endpoints.
