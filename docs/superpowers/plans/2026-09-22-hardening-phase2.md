# Hardening Phase 2 Implementation Plan (free-infra follow-ups)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the review follow-ups that were waiting on infra decisions, using only free resources: DB-backed rate limiting and token revocation/cleanup on the existing Postgres (Neon), multi-schema SQL support, an application-layer cleanup, a real Postgres concurrency test in CI, and the HomePage retry polish.

**Architecture:** Keep the DDD layering. New state (rate-limit counters, revoked access-token JTIs) lives in Postgres via Alembic migrations — no Redis/Upstash, no new services. CI gets a free `postgres:16` service container for the concurrency test. Multi-schema is implemented by qualifying table names as `schema.table` with unique-suffix resolution for unqualified references.

**Tech Stack:** existing (FastAPI, SQLAlchemy 2, Alembic, sqlglot, pytest; React 19 + Vitest). No new runtime dependencies.

**Spec:** `docs/superpowers/specs/` (2026-09-16/17/18) + PR #9 review. Conflicts resolve toward the harder contract defined here; update the schema-design spec in Task 3.

## Global Constraints

- Branch: `feat/hardening-phase2`, stacked on `fix/review-findings` (PR #9). PR base = `fix/review-findings`.
- Test env (same as CI): `DATABASE_URL=postgresql+psycopg://ci:ci@localhost/ci_placeholder`, `JWT_SECRET=ci_placeholder_jwt_secret_at_least_32_chars`.
- Local venv: `%TEMP%\opencode\schemio-venv\Scripts\python.exe`; pytest workdir `apps/api`.
- Concurrency test runs against a real Postgres when `TEST_POSTGRES_URL` is set (Docker locally, CI service container); otherwise skipped.
- All error responses keep the `{"error": {"code", "message"}}` envelope; 429 code is `http_429` (via the existing HTTPException handler) with a `Retry-After` header.
- No new pip/npm dependencies.
- Rulings documented in the run ledger when deviating.

## Review Focus

1. **Rate limiting under shared DB state**: concurrent requests must not lose counts; DB down must not 500 the app (fail-open); window boundaries deterministic in tests.
2. **Logout revocation**: the whole session (access + refresh) must die; revoked-JTI checks must not break normal auth; blacklist must not grow unbounded.
3. **Multi-schema correctness**: no two same-named tables collapse; unqualified references resolve only when unambiguous; naming warnings must not fire on qualified names.
4. **Application layer purity**: no SQLAlchemy imports in `identity/application/`.
5. **Concurrency**: two rotations of the same token mint exactly one token pair.

---

### Task 1: DB-backed rate limiting

**Files:**
- Create: `apps/api/src/shared_kernel/rate_limit.py` (model + repository + dependency in one focused module)
- Create: `apps/api/alembic/versions/d4b2f6a8c1e3_create_rate_limit_counters.py`
- Modify: `apps/api/src/identity/interfaces/auth_router.py`, `apps/api/src/schema_design/interfaces/router.py`
- Modify: `apps/api/tests/conftest.py` (register model, clear counters per test)
- Create: `apps/api/tests/test_rate_limit.py`

**Interfaces:**
- `class RateLimitCounter(Base)` → table `rate_limit_counters(key str PK, window_start datetime PK, count int)`.
- `class RateLimitRepository(session)`: `hit(key: str, window_start: datetime) -> int`, `delete_older_than(cutoff: datetime) -> None`.
- `def client_ip(request: Request) -> str` (first `x-forwarded-for` hop, else `request.client.host`, else `"unknown"`).
- `def rate_limit(bucket: str, limit: int, window_seconds: int) -> Callable` → FastAPI dependency; raises `HTTPException(429, "Too many requests", headers={"Retry-After": str(window_seconds)})` when `count > limit`; fail-open on `SQLAlchemyError`.
- Policies: login 10/min, register 5/min, refresh 20/min, schema/parse 30/min.

- [ ] **Step 1: Failing tests**

`tests/test_rate_limit.py`:

```python
from datetime import UTC, datetime

import pytest

from src.shared_kernel import rate_limit as rate_limit_module


@pytest.fixture()
def frozen_now(monkeypatch):
    moment = datetime(2026, 9, 22, 12, 0, 0, tzinfo=UTC)
    monkeypatch.setattr(rate_limit_module, "utc_now", lambda: moment)
    return moment


def _login(client, ip="203.0.113.10"):
    return client.post(
        "/api/auth/login",
        json={"email": "nobody@example.com", "password": "wrong password"},
        headers={"x-forwarded-for": ip},
    )


def test_login_is_rate_limited_per_ip(client, frozen_now):
    for _ in range(10):
        assert _login(client).status_code == 401

    response = _login(client)

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "http_429"
    assert response.headers["retry-after"] == "60"


def test_rate_limit_is_scoped_to_the_client_ip(client, frozen_now):
    for _ in range(11):
        _login(client, ip="198.51.100.7")

    other = _login(client, ip="198.51.100.8")

    assert other.status_code == 401  # different bucket


def test_register_is_rate_limited(client, frozen_now):
    for _ in range(5):
        client.post(
            "/api/auth/register",
            json={"email": "rl@example.com", "password": "correct horse battery staple"},
            headers={"x-forwarded-for": "203.0.113.99"},
        )

    response = client.post(
        "/api/auth/register",
        json={"email": "rl2@example.com", "password": "correct horse battery staple"},
        headers={"x-forwarded-for": "203.0.113.99"},
    )

    assert response.status_code == 429


def test_schema_parse_is_rate_limited(client, frozen_now):
    payload = {"sql": "CREATE TABLE t (id INTEGER PRIMARY KEY);", "dialect": "postgres"}
    for _ in range(30):
        assert client.post("/api/schema/parse", json=payload).status_code == 200

    response = client.post("/api/schema/parse", json=payload)

    assert response.status_code == 429
```

`tests/conftest.py` changes:

```python
from src.identity.infrastructure import models  # noqa: F401
from src.shared_kernel import rate_limit  # noqa: F401  (registers rate_limit_counters)
from src.shared_kernel.rate_limit import RateLimitCounter


@pytest.fixture()
def client():
    with TestSessionLocal() as cleanup_session:
        cleanup_session.query(RateLimitCounter).delete()
        cleanup_session.commit()
    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)
```

- [ ] **Step 2: Run to verify RED**

Run: `pytest tests/test_rate_limit.py -q` → expect no 429s (fail).

- [ ] **Step 3: Implement `shared_kernel/rate_limit.py`**

```python
from collections.abc import Callable
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, Request
from sqlalchemy import DateTime, Integer, String, delete
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Mapped, Session, mapped_column

from src.shared_kernel.datetimes import utc_now
from src.shared_kernel.db import Base, get_db

_LAST_CLEANUP = datetime.min.replace(tzinfo=None)


class RateLimitCounter(Base):
    __tablename__ = "rate_limit_counters"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimitRepository:
    def __init__(self, session: Session):
        self._session = session

    def hit(self, key: str, window_start: datetime) -> int:
        dialect = self._session.get_bind().dialect.name
        if dialect == "sqlite":
            from sqlalchemy.dialects.sqlite import insert
        else:
            from sqlalchemy.dialects.postgresql import insert
        statement = (
            insert(RateLimitCounter)
            .values(key=key, window_start=window_start, count=1)
            .on_conflict_do_update(
                index_elements=["key", "window_start"],
                set_={"count": RateLimitCounter.count + 1},
            )
            .returning(RateLimitCounter.count)
        )
        count = self._session.execute(statement).scalar_one()
        self._session.commit()
        return int(count)

    def delete_older_than(self, cutoff: datetime) -> None:
        self._session.execute(delete(RateLimitCounter).where(RateLimitCounter.window_start < cutoff))
        self._session.commit()


def rate_limit(bucket: str, limit: int, window_seconds: int) -> Callable:
    def dependency(request: Request, db: Session = Depends(get_db)):  # noqa: B008
        global _LAST_CLEANUP
        now = utc_now()
        window_start = now - timedelta(seconds=now.timestamp() % window_seconds)
        window_start = window_start.replace(microsecond=0)
        repository = RateLimitRepository(db)
        try:
            count = repository.hit(f"{bucket}:{client_ip(request)}", window_start)
            if now.replace(tzinfo=None) - _LAST_CLEANUP > timedelta(hours=1):
                repository.delete_older_than(now - timedelta(days=1))
                _LAST_CLEANUP = now.replace(tzinfo=None)
        except SQLAlchemyError:
            return  # fail-open: never take the API down for limiter trouble
        if count > limit:
            raise HTTPException(
                status_code=429,
                detail="Too many requests",
                headers={"Retry-After": str(window_seconds)},
            )

    return dependency
```

Wire policies: in `auth_router.py` add `dependencies=[Depends(rate_limit("login", 10, 60))]` etc. per route decorator; in `schema_design/interfaces/router.py` add `dependencies=[Depends(rate_limit("schema_parse", 30, 60))]`.

- [ ] **Step 4: Migration `d4b2f6a8c1e3`**

```python
def upgrade() -> None:
    op.create_table(
        "rate_limit_counters",
        sa.Column("key", sa.String(255), primary_key=True),
        sa.Column("window_start", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("count", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("rate_limit_counters")
```

(down_revision = `c8d1e7f2a9b4`.)

- [ ] **Step 5: GREEN + full suite** → `pytest -q`; then commit `feat(api): add database-backed rate limiting`.

---

### Task 2: Access-token revocation + expired-token cleanup

**Files:**
- Modify: `apps/api/src/identity/infrastructure/jwt_service.py`
- Modify: `apps/api/src/identity/infrastructure/models.py` (+ `RevokedAccessTokenModel`)
- Create: `apps/api/src/identity/infrastructure/revoked_access_token_repository.py`
- Modify: `apps/api/src/identity/infrastructure/refresh_token_repository.py` (+ `delete_expired`)
- Modify: `apps/api/src/identity/application/logout.py`, `refresh_access_token.py`
- Modify: `apps/api/src/identity/interfaces/dependencies.py`, `auth_router.py`
- Create: migration `e7c3a9b1d5f2_create_revoked_access_tokens.py`
- Modify tests: `test_jwt_service.py`, `test_auth_endpoints.py`, `test_refresh_and_logout.py`, `test_refresh_token_repository.py`

**Interfaces:**
- `JwtService.decode_access_token(token) -> AccessTokenClaims(user_id, jti, expires_at)`; payload adds `jti` and requires `["sub", "exp", "jti"]`.
- `RevokedAccessTokenRepository(session)`: `add(jti: str, expires_at: datetime)`, `is_revoked(jti: str) -> bool`, `delete_expired(now: datetime) -> None`.
- `RefreshTokenRepository.delete_expired(now: datetime) -> None`.
- `get_current_claims` dependency (checks blacklist); `get_current_user` becomes a thin wrapper over it.
- `Logout(refresh_token_repository, revoked_access_token_repository).execute(raw_refresh_token, access_jti, access_expires_at)`; on logout also `revoked.delete_expired(utc_now())` and `refresh.delete_expired(utc_now())`.
- `RefreshAccessToken.execute` calls `delete_expired(utc_now())` after a successful rotation.

- [ ] **Step 1: Failing tests**

`test_jwt_service.py` additions:

```python
def test_each_access_token_has_a_unique_jti_and_expiry():
    service = JwtService(secret="test-secret-at-least-32-characters-long")
    first = service.decode_access_token(service.create_access_token("u1"))
    second = service.decode_access_token(service.create_access_token("u1"))

    assert first.user_id == "u1"
    assert first.jti and first.jti != second.jti
    assert first.expires_at > datetime.now(UTC)
```

`test_auth_endpoints.py` additions/updates:

```python
def test_logout_revokes_the_access_token(client):
    client.post("/api/auth/register", json={"email": "rev@example.com", "password": "correct horse battery staple"})
    login = client.post("/api/auth/login", json={"email": "rev@example.com", "password": "correct horse battery staple"}).json()
    headers = {"Authorization": f"Bearer {login['access_token']}"}

    assert client.get("/api/projects", headers=headers).status_code == 200
    logout = client.post("/api/auth/logout", json={"refresh_token": login["refresh_token"]}, headers=headers)
    assert logout.status_code == 204
    assert client.get("/api/projects", headers=headers).status_code == 401


def test_logout_requires_authentication(client):
    response = client.post("/api/auth/logout", json={"refresh_token": "whatever"})
    assert response.status_code == 401
```

`test_refresh_and_logout.py`: update all `Logout(repo)` usages to the new signature and add:

```python
def test_rotation_cleans_up_expired_refresh_tokens():
    from datetime import datetime, timedelta

    from src.identity.infrastructure.models import RefreshTokenModel

    session = _make_session()
    repo = RefreshTokenRepository(session)
    past = datetime.now(UTC) - timedelta(days=1)
    session.add(RefreshTokenModel(id="old", user_id="u1", token_hash="h-old", expires_at=past))
    session.commit()
    raw = _issue_raw_token(repo)

    RefreshAccessToken(repo, JwtService(secret="test-secret")).execute(raw)

    assert session.get(RefreshTokenModel, "old") is None


def test_logout_cleans_up_expired_revoked_access_tokens():
    from datetime import datetime, timedelta

    from src.identity.infrastructure.models import RevokedAccessTokenModel
    from src.identity.infrastructure.revoked_access_token_repository import (
        RevokedAccessTokenRepository,
    )

    session = _make_session()
    repo = RefreshTokenRepository(session)
    revoked = RevokedAccessTokenRepository(session)
    past = datetime.now(UTC) - timedelta(days=1)
    revoked.add(jti="j-old", expires_at=past)
    raw = _issue_raw_token(repo)

    Logout(repo, revoked).execute(
        raw, access_jti="j-current", access_expires_at=datetime.now(UTC) + timedelta(minutes=30)
    )

    assert session.get(RevokedAccessTokenModel, "j-old") is None
```

Cleanup ownership: rotation cleans expired refresh tokens; logout cleans expired revoked access tokens (and expired refresh tokens too).

- [ ] **Step 2: RED** → `pytest tests/identity -q`.

- [ ] **Step 3: Implement** per Interfaces above (models, repository, migrations, dependencies, router, use cases).

- [ ] **Step 4: GREEN + full suite**, regenerate `openapi.json`/`schema.ts` (logout now documented as requiring auth), commit `feat(identity): revoke access tokens on logout and clean up expired tokens`.

---

### Task 3: Multi-schema support

**Files:**
- Modify: `apps/api/src/schema_design/infrastructure/sqlglot_parser.py`
- Modify: `apps/api/src/schema_design/infrastructure/relationship_detector.py`
- Modify: `apps/api/src/schema_design/infrastructure/structural_validator.py`
- Modify tests: `test_sqlglot_parser.py`, `test_relationship_detector.py`, `test_structural_validator.py`
- Modify: `docs/superpowers/specs/2026-09-17-schema-design-domain.md`

**Interfaces:**
- Table names are qualified as `schema.table` when the DDL specifies a schema (`CREATE TABLE auth.users`), unqualified otherwise.
- `_resolve_foreign_key`: exact qualified match wins; an unqualified reference resolves to the unique table whose name ends with `.<ref>`; if several match → the FK is dropped.
- `_find_matching_table` (inference): compares candidates against the last segment; ambiguity (multiple schemas share the name) → skipped.
- Naming warnings validate each dot-separated segment.

- [ ] **Step 1: Failing tests**

```python
def test_tables_in_different_schemas_stay_distinct():
    sql = """
    CREATE TABLE public.users (id SERIAL PRIMARY KEY);
    CREATE TABLE auth.users (id SERIAL PRIMARY KEY);
    """
    tables = extract_tables(sql, SqlDialect.POSTGRES)
    assert {t.name for t in tables} == {"public.users", "auth.users"}


def test_foreign_key_with_qualified_reference_resolves_exactly():
    sql = """
    CREATE TABLE auth.users (id SERIAL PRIMARY KEY);
    CREATE TABLE posts (id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES auth.users(id));
    """
    assert extract_foreign_keys(sql, SqlDialect.POSTGRES) == [
        ("posts", "user_id", "auth.users", "id")
    ]


def test_unqualified_reference_resolves_to_the_unique_suffix_match():
    sql = """
    CREATE TABLE auth.users (id SERIAL PRIMARY KEY);
    CREATE TABLE posts (id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES users(id));
    """
    assert extract_foreign_keys(sql, SqlDialect.POSTGRES) == [
        ("posts", "user_id", "auth.users", "id")
    ]


def test_ambiguous_unqualified_reference_is_dropped():
    sql = """
    CREATE TABLE public.users (id SERIAL PRIMARY KEY);
    CREATE TABLE auth.users (id SERIAL PRIMARY KEY);
    CREATE TABLE posts (id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES users(id));
    """
    assert extract_foreign_keys(sql, SqlDialect.POSTGRES) == []
```

Detector test: inference skips ambiguous table name across schemas. Validator test: `public.users` produces no `NON_SNAKE_CASE_IDENTIFIER` warning.

- [ ] **Step 2: RED** → `pytest tests/schema_design -q`.
- [ ] **Step 3: Implement** the parser/detector/validator changes; update the spec section "Relationship Detection Rules" with one paragraph on schema-qualified names.
- [ ] **Step 4: GREEN + full suite**, commit `feat(schema-design): keep schema-qualified table names and resolve references unambiguously`.

---

### Task 4: Application layer without SQLAlchemy + real Postgres concurrency test

**Files:**
- Modify: `apps/api/src/identity/infrastructure/user_repository.py` (translate `IntegrityError` → `EmailAlreadyRegisteredError`)
- Modify: `apps/api/src/identity/application/register_user.py` (drop SQLAlchemy import/catch)
- Create: `apps/api/tests/test_postgres_concurrency.py`
- Modify: `apps/api/pyproject.toml` (register `postgres` marker)
- Modify: `.github/workflows/ci.yml` (api job: `postgres:16` service + `TEST_POSTGRES_URL`)
- Modify tests: `test_user_repository.py`

**Interfaces:**
- `UserRepository.create` raises `EmailAlreadyRegisteredError` on unique violation (after rollback).
- `TEST_POSTGRES_URL` enables `tests/test_postgres_concurrency.py` (skipped otherwise).

- [ ] **Step 1: Failing tests**

`test_user_repository.py`:

```python
def test_duplicate_email_create_raises_domain_error():
    from src.identity.domain.errors import EmailAlreadyRegisteredError

    session = _make_session()
    repo = UserRepository(session)
    repo.create(id="u1", email="a@example.com", password_hash="h")

    with pytest.raises(EmailAlreadyRegisteredError):
        repo.create(id="u2", email="a@example.com", password_hash="h")
```

`test_postgres_concurrency.py`:

```python
import os
import threading
import uuid
from datetime import UTC, datetime, timedelta
from hashlib import sha256

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.identity.infrastructure.refresh_token_repository import (
    RefreshTokenRepository,
    RotationOutcome,
)
from src.shared_kernel.db import Base

TEST_POSTGRES_URL = os.environ.get("TEST_POSTGRES_URL")

pytestmark = pytest.mark.skipif(not TEST_POSTGRES_URL, reason="TEST_POSTGRES_URL not set")


def test_concurrent_rotation_mints_exactly_one_replacement():
    engine = create_engine(TEST_POSTGRES_URL)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    raw = "concurrent-token"
    token_hash = sha256(raw.encode()).hexdigest()
    with session_factory() as setup:
        RefreshTokenRepository(setup).create(
            id=str(uuid.uuid4()),
            user_id="u1",
            token_hash=token_hash,
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )

    barrier = threading.Barrier(2)
    outcomes: list[RotationOutcome] = []
    lock = threading.Lock()

    def rotate_once() -> None:
        session = session_factory()
        try:
            barrier.wait(timeout=10)
            outcome, _ = RefreshTokenRepository(session).rotate(
                old_token_hash=token_hash,
                new_id=str(uuid.uuid4()),
                new_token_hash=str(uuid.uuid4()),
                new_expires_at=datetime.now(UTC) + timedelta(days=30),
            )
        finally:
            session.close()
        with lock:
            outcomes.append(outcome)

    threads = [threading.Thread(target=rotate_once) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert sorted(outcomes) == [RotationOutcome.REUSED, RotationOutcome.ROTATED]
```

`pyproject.toml`:

```toml
[tool.pytest.ini_options]
pythonpath = ["."]
markers = ["postgres: requires a real Postgres (TEST_POSTGRES_URL)"]
```

`.github/workflows/ci.yml` `api` job:

```yaml
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_PASSWORD: postgres
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    env:
      DATABASE_URL: postgresql+psycopg://ci:ci@localhost/ci_placeholder
      JWT_SECRET: ci_placeholder_jwt_secret_at_least_32_chars
      TEST_POSTGRES_URL: postgresql+psycopg://postgres:postgres@localhost:5432/postgres
```

- [ ] **Step 2: RED locally** (repo test) and run the Postgres test against Docker: `docker run -d --name schemio-pg -e POSTGRES_PASSWORD=postgres -p 55432:5432 postgres:16`, then `TEST_POSTGRES_URL=postgresql+psycopg://postgres:postgres@localhost:55432/postgres pytest tests/test_postgres_concurrency.py -v`.
- [ ] **Step 3: Implement** the repository translation and `register_user.py` cleanup.
- [ ] **Step 4: GREEN** (full suite + Postgres test against Docker), commit `refactor(identity): translate unique violations in the repository; add Postgres concurrency test`.

---

### Task 5: HomePage retry abort + wrap-up

**Files:**
- Modify: `apps/web/src/pages/HomePage.tsx`
- Modify: `README.md` (brief "rate limits" note)

- [ ] **Step 1: Implement abortable retry**

```tsx
import { useCallback, useEffect, useRef, useState } from 'react'
// ...
  const controllerRef = useRef<AbortController | null>(null)

  const checkHealth = useCallback((signal?: AbortSignal) => {
    setApiStatus('checking')
    return getHealth({ signal })
      .then((health) => setApiStatus(health.status === 'ok' ? 'ok' : 'unreachable'))
      .catch(() => {
        if (!signal?.aborted) setApiStatus('unreachable')
      })
  }, [])

  const load = useCallback(() => {
    controllerRef.current?.abort()
    const controller = new AbortController()
    controllerRef.current = controller
    void checkHealth(controller.signal)
  }, [checkHealth])

  useEffect(() => {
    load()
    return () => controllerRef.current?.abort()
  }, [load])
// button: onClick={load}
```

- [ ] **Step 2: Web checks** → `pnpm --filter web lint`, `test`, `build`, biome on the file.
- [ ] **Step 3: Wrap-up verification** — full CI-equivalent (pytest incl. Postgres via Docker, ruff, web suites, biome LF clone, client drift, smoke) and commit `chore(web,docs): abortable health retry and rate-limit notes`.

---

### Task 6: Push, PR #10 and CI

- [ ] Push `feat/hardening-phase2`, open PR with base `fix/review-findings` (`gh pr create --base fix/review-findings`), watch CI (including the Postgres service job), and report. If PR #9 is merged first, retarget PR #10 to `main` with `gh pr edit --base main`.
