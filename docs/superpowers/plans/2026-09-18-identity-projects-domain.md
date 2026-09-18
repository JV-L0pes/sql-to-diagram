# Identity & Projects Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add user accounts (JWT auth with revocable refresh tokens) and saved SQL "projects" (name + SQL + dialect, owned by a user) to `apps/api`'s `identity` bounded context, exposed as `/api/auth/*` and `/api/projects/*` FastAPI endpoints.

**Architecture:** Four-layer DDD split inside `apps/api/src/identity/` (domain/application/infrastructure/interfaces), matching `schema_design`'s established pattern. `domain/` stays free of SQLAlchemy/argon2/JWT-library imports. Three new DB tables (`users`, `projects`, `refresh_tokens`) via Alembic migration, using string-UUID primary keys for Postgres/SQLite portability (tests run against SQLite, production against Neon Postgres).

**Tech Stack:** `argon2-cffi` (password hashing), `PyJWT` (access tokens), SQLAlchemy (ORM models + repositories), Alembic (migration), FastAPI (routers, `HTTPBearer` security), pytest (unit + integration tests, SQLite override pattern from Phases 1-2).

**Spec:** [docs/superpowers/specs/2026-09-18-identity-projects-domain.md](../specs/2026-09-18-identity-projects-domain.md)

## Global Constraints

- `identity/domain/` files import nothing from `sqlalchemy`, `fastapi`, `argon2`, or `jwt` — verified by grep in each task's self-review.
- No bare `except`/silent fallback — typed domain exceptions raised in `application/`, caught specifically in `interfaces/` routers, mapped via the shared `error_body()` shape (from `shared_kernel/errors.py`, Phase 1).
- A project that doesn't exist OR belongs to another user both return 404 (never 403) — no ownership-existence leak.
- Password/token raw values are never logged or included in any error message or exception string passed to `error_body()`.
- `schema_design`'s `/api/schema/parse` endpoint is not modified by this plan.
- IDs are string UUIDs (`str(uuid.uuid4())`), stored as `String(36)` columns — works identically on Postgres and SQLite (the test suite's DB).
- Access tokens: JWT HS256, 30-minute expiry, payload `{"sub": "<user_id>", "exp": ...}`. Refresh tokens: opaque `secrets.token_urlsafe(32)` strings, DB-backed via SHA-256 hash, 30-day expiry, rotated (old revoked) on every use.

---

## File Structure

```
apps/api/
├── pyproject.toml                          # add argon2-cffi, PyJWT (Task 1)
└── src/
    ├── shared_kernel/
    │   ├── settings.py                     # add jwt_secret field (Task 3)
    │   └── db.py                           # add Base = declarative_base() (Task 5)
    └── identity/
        ├── domain/
        │   ├── user.py                     # User entity (Task 1)
        │   ├── project.py                  # Project entity (Task 1)
        │   └── errors.py                   # domain exceptions (Task 1)
        ├── infrastructure/
        │   ├── password_hasher.py          # PasswordHasher (Task 2)
        │   ├── jwt_service.py              # JwtService (Task 3)
        │   ├── models.py                   # UserModel, ProjectModel, RefreshTokenModel (Task 5)
        │   ├── user_repository.py          # UserRepository (Task 6)
        │   ├── refresh_token_repository.py # RefreshTokenRepository (Task 7)
        │   └── project_repository.py       # ProjectRepository (Task 8)
        ├── application/
        │   ├── register_user.py            # RegisterUser (Task 9)
        │   ├── authenticate_user.py        # AuthenticateUser (Task 10)
        │   ├── refresh_access_token.py      # RefreshAccessToken (Task 11)
        │   ├── logout.py                    # Logout (Task 11)
        │   └── project_use_cases.py         # Create/List/Get/Update/Delete (Task 13)
        └── interfaces/
            ├── schemas.py                   # Pydantic models (Tasks 12, 14)
            ├── dependencies.py              # get_current_user (Task 12)
            ├── auth_router.py               # /api/auth/* (Task 12)
            └── projects_router.py           # /api/projects/* (Task 14)
apps/api/alembic/versions/
└── <rev>_create_identity_tables.py         # users, projects, refresh_tokens (Task 4)
apps/api/tests/identity/
├── __init__.py, test_user.py, test_project.py         # Task 1
├── test_password_hasher.py                            # Task 2
├── test_jwt_service.py                                # Task 3
├── test_user_repository.py                            # Task 6
├── test_refresh_token_repository.py                   # Task 7
├── test_project_repository.py                         # Task 8
├── test_register_user.py                              # Task 9
├── test_authenticate_user.py                          # Task 10
├── test_refresh_and_logout.py                         # Task 11
├── test_auth_endpoints.py                             # Task 12
├── test_project_use_cases.py                          # Task 13
└── test_project_endpoints.py                          # Task 14
```

---

### Task 1: Domain — `User`, `Project`, domain errors

**Files:**
- Create: `apps/api/src/identity/domain/user.py`
- Create: `apps/api/src/identity/domain/project.py`
- Create: `apps/api/src/identity/domain/errors.py`
- Create: `apps/api/tests/identity/__init__.py`, `apps/api/tests/identity/test_user.py`, `apps/api/tests/identity/test_project.py`

**Interfaces:**
- Produces: `User` (dataclass: `id: str`, `email: str`, `password_hash: str`, `created_at: datetime`), `Project` (dataclass: `id: str`, `user_id: str`, `name: str`, `sql: str`, `dialect: str`, `created_at: datetime`, `updated_at: datetime`), and exceptions `EmailAlreadyRegisteredError(ValueError)`, `InvalidCredentialsError(ValueError)`, `InvalidRefreshTokenError(ValueError)`, `ProjectNotFoundError(ValueError)` in `errors.py`.

- [ ] **Step 1: Write the failing tests — `apps/api/tests/identity/test_user.py`**

```python
from datetime import datetime, timezone

from src.identity.domain.user import User


def test_user_holds_all_fields():
    now = datetime.now(timezone.utc)
    user = User(id="u1", email="a@example.com", password_hash="hash", created_at=now)

    assert user.id == "u1"
    assert user.email == "a@example.com"
    assert user.password_hash == "hash"
    assert user.created_at == now
```

- [ ] **Step 2: Write the failing tests — `apps/api/tests/identity/test_project.py`**

```python
from datetime import datetime, timezone

from src.identity.domain.project import Project


def test_project_holds_all_fields():
    now = datetime.now(timezone.utc)
    project = Project(
        id="p1",
        user_id="u1",
        name="My Schema",
        sql="CREATE TABLE t (id INT);",
        dialect="postgres",
        created_at=now,
        updated_at=now,
    )

    assert project.id == "p1"
    assert project.user_id == "u1"
    assert project.name == "My Schema"
    assert project.dialect == "postgres"
```

- [ ] **Step 3: Create `apps/api/tests/identity/__init__.py`** (empty)

- [ ] **Step 4: Run both to verify they fail**

Run (from `apps/api`): `pytest tests/identity/ -v`
Expected: FAIL — modules don't exist.

- [ ] **Step 5: Implement `apps/api/src/identity/domain/user.py`**

```python
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class User:
    id: str
    email: str
    password_hash: str
    created_at: datetime
```

- [ ] **Step 6: Implement `apps/api/src/identity/domain/project.py`**

```python
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Project:
    id: str
    user_id: str
    name: str
    sql: str
    dialect: str
    created_at: datetime
    updated_at: datetime
```

- [ ] **Step 7: Implement `apps/api/src/identity/domain/errors.py`**

```python
class EmailAlreadyRegisteredError(ValueError):
    def __init__(self, email: str):
        super().__init__(f"Email already registered: {email!r}")


class InvalidCredentialsError(ValueError):
    def __init__(self):
        super().__init__("Invalid email or password")


class InvalidRefreshTokenError(ValueError):
    def __init__(self):
        super().__init__("Invalid or expired refresh token")


class ProjectNotFoundError(ValueError):
    def __init__(self, project_id: str):
        super().__init__(f"Project not found: {project_id!r}")
```

- [ ] **Step 8: Run the tests to verify they pass**

Run (from `apps/api`): `pytest tests/identity/ -v`
Expected: PASS (2 tests)

- [ ] **Step 9: Verify no framework imports leaked into domain**

Run: `grep -rn "^import\|^from" apps/api/src/identity/domain/`
Expected: only stdlib (`dataclasses`, `datetime`) — no sqlalchemy/fastapi/argon2/jwt.

- [ ] **Step 10: Commit**

```bash
git add apps/api/src/identity/domain apps/api/tests/identity
git commit -m "feat(api): add User, Project domain entities and identity domain errors"
```

---

### Task 2: Infrastructure — `PasswordHasher`

**Files:**
- Modify: `apps/api/pyproject.toml` (add `argon2-cffi`)
- Create: `apps/api/src/identity/infrastructure/password_hasher.py`
- Test: `apps/api/tests/identity/test_password_hasher.py`

**Interfaces:**
- Produces: `PasswordHasher` class with `hash(password: str) -> str` and `verify(password_hash: str, password: str) -> bool`.

- [ ] **Step 1: Add `argon2-cffi` to `apps/api/pyproject.toml`**

In the `[project]` section's `dependencies` list, add (alphabetically):
```toml
    "argon2-cffi>=23.1.0",
```

- [ ] **Step 2: Install it**

Run (from `apps/api`): `.venv/Scripts/python.exe -m pip install -e ".[dev]"`

- [ ] **Step 3: Write the failing test — `apps/api/tests/identity/test_password_hasher.py`**

```python
from src.identity.infrastructure.password_hasher import PasswordHasher


def test_hash_then_verify_succeeds_with_correct_password():
    hasher = PasswordHasher()
    password_hash = hasher.hash("correct horse battery staple")

    assert hasher.verify(password_hash, "correct horse battery staple") is True


def test_verify_fails_with_wrong_password():
    hasher = PasswordHasher()
    password_hash = hasher.hash("correct horse battery staple")

    assert hasher.verify(password_hash, "wrong password") is False


def test_hash_is_not_the_plaintext_password():
    hasher = PasswordHasher()
    password_hash = hasher.hash("correct horse battery staple")

    assert password_hash != "correct horse battery staple"
    assert "correct horse battery staple" not in password_hash
```

- [ ] **Step 4: Run it to verify it fails**

Run (from `apps/api`): `pytest tests/identity/test_password_hasher.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 5: Implement `apps/api/src/identity/infrastructure/password_hasher.py`**

```python
from argon2 import PasswordHasher as Argon2Hasher
from argon2.exceptions import VerifyMismatchError


class PasswordHasher:
    def __init__(self):
        self._hasher = Argon2Hasher()

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password_hash: str, password: str) -> bool:
        try:
            return self._hasher.verify(password_hash, password)
        except VerifyMismatchError:
            return False
```

- [ ] **Step 6: Run the tests to verify they pass**

Run (from `apps/api`): `pytest tests/identity/test_password_hasher.py -v`
Expected: PASS (3 tests)

- [ ] **Step 7: Commit**

```bash
git add apps/api/pyproject.toml apps/api/src/identity/infrastructure/password_hasher.py apps/api/tests/identity/test_password_hasher.py
git commit -m "feat(api): add argon2 PasswordHasher"
```

---

### Task 3: Infrastructure — `JwtService` + `jwt_secret` setting

**Files:**
- Modify: `apps/api/pyproject.toml` (add `PyJWT`)
- Modify: `apps/api/src/shared_kernel/settings.py` (add `jwt_secret` field)
- Create: `apps/api/src/identity/infrastructure/jwt_service.py`
- Test: `apps/api/tests/identity/test_jwt_service.py`

**Interfaces:**
- Consumes: `get_settings()` from `apps/api/src/shared_kernel/settings.py` (Phase 1, now with a new `jwt_secret` field).
- Produces: `JwtService` class with `create_access_token(user_id: str) -> str` and `decode_access_token(token: str) -> str` (returns the `user_id`, raises `InvalidCredentialsError`-adjacent... no — raises a plain `jwt`-library exception on failure, caught by the caller; see Task 12 for where that's handled at the HTTP boundary).

- [ ] **Step 1: Add `PyJWT` to `apps/api/pyproject.toml`**

```toml
    "PyJWT>=2.9.0",
```

- [ ] **Step 2: Add `jwt_secret` to `apps/api/src/shared_kernel/settings.py`**

Find the `Settings` class (from Phase 1) and add one field alongside the existing `database_url`:
```python
    jwt_secret: str
```
(Insert it as a new attribute in the `Settings` class body, after `database_url: str`. Leave `cors_allow_origins` and everything else unchanged.)

- [ ] **Step 3: Add `JWT_SECRET` to your local `apps/api/.env`**

```
JWT_SECRET=<any long random string for local dev — e.g. output of `python -c "import secrets; print(secrets.token_urlsafe(32))"`>
```
(Do not commit `.env` — it's already gitignored from Phase 1.)

- [ ] **Step 4: Install the new dependency**

Run (from `apps/api`): `.venv/Scripts/python.exe -m pip install -e ".[dev]"`

- [ ] **Step 5: Write the failing test — `apps/api/tests/identity/test_jwt_service.py`**

```python
import time

import jwt
import pytest

from src.identity.infrastructure.jwt_service import JwtService


def test_create_then_decode_returns_the_same_user_id():
    service = JwtService(secret="test-secret", expiry_minutes=30)
    token = service.create_access_token("user-123")

    assert service.decode_access_token(token) == "user-123"


def test_decode_rejects_expired_token():
    service = JwtService(secret="test-secret", expiry_minutes=-1)  # already expired
    token = service.create_access_token("user-123")

    with pytest.raises(jwt.ExpiredSignatureError):
        service.decode_access_token(token)


def test_decode_rejects_token_signed_with_a_different_secret():
    service_a = JwtService(secret="secret-a", expiry_minutes=30)
    service_b = JwtService(secret="secret-b", expiry_minutes=30)
    token = service_a.create_access_token("user-123")

    with pytest.raises(jwt.InvalidTokenError):
        service_b.decode_access_token(token)
```

- [ ] **Step 6: Run it to verify it fails**

Run (from `apps/api`): `pytest tests/identity/test_jwt_service.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 7: Implement `apps/api/src/identity/infrastructure/jwt_service.py`**

```python
from datetime import datetime, timedelta, timezone

import jwt


class JwtService:
    def __init__(self, secret: str, expiry_minutes: int = 30):
        self._secret = secret
        self._expiry_minutes = expiry_minutes
        self._algorithm = "HS256"

    def create_access_token(self, user_id: str) -> str:
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=self._expiry_minutes)
        payload = {"sub": user_id, "exp": expires_at}
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)

    def decode_access_token(self, token: str) -> str:
        payload = jwt.decode(token, self._secret, algorithms=[self._algorithm])
        return payload["sub"]
```

- [ ] **Step 8: Run the tests to verify they pass**

Run (from `apps/api`): `pytest tests/identity/test_jwt_service.py -v`
Expected: PASS (3 tests)

- [ ] **Step 9: Run the full `apps/api` test suite to confirm the new `jwt_secret` setting doesn't break existing tests**

Run (from `apps/api`): `pytest -v`
Expected: all PASS — `test_settings.py` (Phase 1) constructs `Settings` via `monkeypatch.setenv`, so it needs `JWT_SECRET` set too now that it's a required field. If any Phase 1 settings test fails with a `jwt_secret` validation error, add `monkeypatch.setenv("JWT_SECRET", "test-secret")` alongside that test's existing `DATABASE_URL` env var — do this fix as part of this task if needed (it's a direct, minimal consequence of this task's own change, not scope creep).

- [ ] **Step 10: Commit**

```bash
git add apps/api/pyproject.toml apps/api/src/shared_kernel/settings.py apps/api/src/identity/infrastructure/jwt_service.py apps/api/tests/identity/test_jwt_service.py apps/api/tests/shared_kernel/test_settings.py
git commit -m "feat(api): add JwtService and jwt_secret setting"
```
(Only include `test_settings.py` in the commit if Step 9 required changing it.)

---

### Task 4: Infrastructure — `Base` declarative registry in `shared_kernel`

**Files:**
- Modify: `apps/api/src/shared_kernel/db.py`

**Interfaces:**
- Produces: `Base` (SQLAlchemy declarative base) exported from `apps/api/src/shared_kernel/db.py`, for `identity/infrastructure/models.py` (Task 5) to inherit from, and for `apps/api/alembic/env.py` (Task 5) to point `target_metadata` at.

- [ ] **Step 1: Add `Base` to `apps/api/src/shared_kernel/db.py`**

Add near the top of the file, after the existing imports:
```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```
Leave `engine`, `SessionLocal`, and `get_db()` (from Phase 1) exactly as they are — this is a pure addition.

- [ ] **Step 2: Verify the module still imports cleanly**

Run (from `apps/api`): `.venv/Scripts/python.exe -c "from src.shared_kernel.db import Base, engine, SessionLocal, get_db"`
Expected: no error.

- [ ] **Step 3: Run the full test suite to confirm nothing broke**

Run (from `apps/api`): `pytest -v`
Expected: all PASS (this change adds an unused-so-far class, no behavior change).

- [ ] **Step 4: Commit**

```bash
git add apps/api/src/shared_kernel/db.py
git commit -m "feat(api): add SQLAlchemy declarative Base to shared_kernel"
```

---

### Task 5: Infrastructure — SQLAlchemy models + Alembic migration

**Files:**
- Create: `apps/api/src/identity/infrastructure/models.py`
- Create: `apps/api/alembic/versions/<generated>_create_identity_tables.py`
- Modify: `apps/api/alembic/env.py` (point `target_metadata` at `Base.metadata`)

**Interfaces:**
- Consumes: `Base` from `apps/api/src/shared_kernel/db.py` (Task 4).
- Produces: `UserModel`, `ProjectModel`, `RefreshTokenModel` (SQLAlchemy ORM classes) in `models.py`, and the three tables (`users`, `projects`, `refresh_tokens`) created in the database via the migration.

- [ ] **Step 1: Implement `apps/api/src/identity/infrastructure/models.py`**

```python
from datetime import datetime, timezone

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared_kernel.db import Base


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))

    projects: Mapped[list["ProjectModel"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    refresh_tokens: Mapped[list["RefreshTokenModel"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class ProjectModel(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    sql: Mapped[str] = mapped_column(Text, nullable=False)
    dialect: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))

    user: Mapped["UserModel"] = relationship(back_populates="projects")


class RefreshTokenModel(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))

    user: Mapped["UserModel"] = relationship(back_populates="refresh_tokens")
```

- [ ] **Step 2: Point Alembic's `target_metadata` at `Base.metadata`**

Open `apps/api/alembic/env.py`. Find the line `target_metadata = None` (Alembic's default scaffold) and replace it with:
```python
from src.shared_kernel.db import Base
from src.identity.infrastructure import models  # noqa: F401  (registers models on Base.metadata)

target_metadata = Base.metadata
```
Place this near the other imports Phase 1 already added (the `sys.path.append` / `get_settings` block) — after `sys.path.append(...)` runs (so `src` is importable), before `target_metadata` is used later in the file.

- [ ] **Step 3: Generate a new migration revision**

Run (from `apps/api`, with `.venv` active and `.env`'s `DATABASE_URL` pointing at your real Neon connection): `alembic revision -m "create identity tables"`
Expected: creates a new file in `apps/api/alembic/versions/`.

- [ ] **Step 4: Fill in the migration's `upgrade()`/`downgrade()`**

Open the generated file and replace the empty `upgrade()`/`downgrade()` functions with:
```python
def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "projects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("sql", sa.Text(), nullable=False),
        sa.Column("dialect", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("refresh_tokens")
    op.drop_table("projects")
    op.drop_table("users")
```
(`sa` and `op` are already imported by Alembic's generated file template — don't add duplicate imports.)

- [ ] **Step 5: Apply the migration to your real Neon dev database**

Run (from `apps/api`): `alembic upgrade head`
Expected: no error. Verify with `alembic current` — should show the new revision as current.

- [ ] **Step 6: Verify the tables exist**

Run (from `apps/api`, using the venv's Python): a quick check via `python -c "from src.shared_kernel.db import engine; from sqlalchemy import inspect; print(inspect(engine).get_table_names())"` — expect to see `users`, `projects`, `refresh_tokens` in the output (alongside any pre-existing tables).

- [ ] **Step 7: Run the full test suite to confirm nothing broke**

Run (from `apps/api`): `pytest -v`
Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
git add apps/api/src/identity/infrastructure/models.py apps/api/alembic/env.py apps/api/alembic/versions/
git commit -m "feat(api): add identity SQLAlchemy models and create_identity_tables migration"
```

---

### Task 6: Infrastructure — `UserRepository`

**Files:**
- Create: `apps/api/src/identity/infrastructure/user_repository.py`
- Test: `apps/api/tests/identity/test_user_repository.py`

**Interfaces:**
- Consumes: `UserModel` (Task 5), `User` domain entity (Task 1).
- Produces: `UserRepository` class (constructed with a SQLAlchemy `Session`) with `create(id: str, email: str, password_hash: str) -> User`, `get_by_email(email: str) -> User | None`, `get_by_id(user_id: str) -> User | None`.

- [ ] **Step 1: Write the failing test — `apps/api/tests/identity/test_user_repository.py`**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.identity.infrastructure.user_repository import UserRepository
from src.shared_kernel.db import Base


def _make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_create_then_get_by_email_returns_the_same_user():
    session = _make_session()
    repo = UserRepository(session)

    created = repo.create(id="u1", email="a@example.com", password_hash="hash")
    found = repo.get_by_email("a@example.com")

    assert found is not None
    assert found.id == created.id
    assert found.email == "a@example.com"
    assert found.password_hash == "hash"


def test_get_by_email_returns_none_when_not_found():
    session = _make_session()
    repo = UserRepository(session)

    assert repo.get_by_email("missing@example.com") is None


def test_get_by_id_returns_the_matching_user():
    session = _make_session()
    repo = UserRepository(session)
    created = repo.create(id="u1", email="a@example.com", password_hash="hash")

    found = repo.get_by_id("u1")

    assert found is not None
    assert found.id == created.id
```

- [ ] **Step 2: Run it to verify it fails**

Run (from `apps/api`): `pytest tests/identity/test_user_repository.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement `apps/api/src/identity/infrastructure/user_repository.py`**

```python
from sqlalchemy.orm import Session

from src.identity.domain.user import User
from src.identity.infrastructure.models import UserModel


class UserRepository:
    def __init__(self, session: Session):
        self._session = session

    def create(self, id: str, email: str, password_hash: str) -> User:
        model = UserModel(id=id, email=email, password_hash=password_hash)
        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)
        return self._to_domain(model)

    def get_by_email(self, email: str) -> User | None:
        model = self._session.query(UserModel).filter_by(email=email).first()
        return self._to_domain(model) if model else None

    def get_by_id(self, user_id: str) -> User | None:
        model = self._session.get(UserModel, user_id)
        return self._to_domain(model) if model else None

    @staticmethod
    def _to_domain(model: UserModel) -> User:
        return User(
            id=model.id,
            email=model.email,
            password_hash=model.password_hash,
            created_at=model.created_at,
        )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run (from `apps/api`): `pytest tests/identity/test_user_repository.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/identity/infrastructure/user_repository.py apps/api/tests/identity/test_user_repository.py
git commit -m "feat(api): add UserRepository"
```

---

### Task 7: Infrastructure — `RefreshTokenRepository`

**Files:**
- Create: `apps/api/src/identity/infrastructure/refresh_token_repository.py`
- Test: `apps/api/tests/identity/test_refresh_token_repository.py`

**Interfaces:**
- Consumes: `RefreshTokenModel` (Task 5).
- Produces: `RefreshTokenRepository` class (constructed with a `Session`) with:
  - `create(id: str, user_id: str, token_hash: str, expires_at: datetime) -> None`
  - `get_valid_by_hash(token_hash: str) -> RefreshTokenRecord | None` — returns a small dataclass `RefreshTokenRecord(id: str, user_id: str, expires_at: datetime)` for a token that is NOT revoked and NOT expired (the query itself filters on `revoked_at IS NULL AND expires_at > now()`), `None` otherwise.
  - `revoke(token_id: str) -> None` — sets `revoked_at = now()`.

- [ ] **Step 1: Write the failing test — `apps/api/tests/identity/test_refresh_token_repository.py`**

```python
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.identity.infrastructure.refresh_token_repository import RefreshTokenRepository
from src.shared_kernel.db import Base


def _make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _future():
    return datetime.now(timezone.utc) + timedelta(days=30)


def _past():
    return datetime.now(timezone.utc) - timedelta(days=1)


def test_create_then_get_valid_by_hash_returns_the_record():
    session = _make_session()
    repo = RefreshTokenRepository(session)
    repo.create(id="t1", user_id="u1", token_hash="hash1", expires_at=_future())

    record = repo.get_valid_by_hash("hash1")

    assert record is not None
    assert record.id == "t1"
    assert record.user_id == "u1"


def test_get_valid_by_hash_returns_none_for_unknown_hash():
    session = _make_session()
    repo = RefreshTokenRepository(session)

    assert repo.get_valid_by_hash("nonexistent") is None


def test_get_valid_by_hash_returns_none_for_expired_token():
    session = _make_session()
    repo = RefreshTokenRepository(session)
    repo.create(id="t1", user_id="u1", token_hash="hash1", expires_at=_past())

    assert repo.get_valid_by_hash("hash1") is None


def test_get_valid_by_hash_returns_none_after_revoke():
    session = _make_session()
    repo = RefreshTokenRepository(session)
    repo.create(id="t1", user_id="u1", token_hash="hash1", expires_at=_future())

    repo.revoke("t1")

    assert repo.get_valid_by_hash("hash1") is None
```

- [ ] **Step 2: Run it to verify it fails**

Run (from `apps/api`): `pytest tests/identity/test_refresh_token_repository.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement `apps/api/src/identity/infrastructure/refresh_token_repository.py`**

```python
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import and_
from sqlalchemy.orm import Session

from src.identity.infrastructure.models import RefreshTokenModel


@dataclass(frozen=True)
class RefreshTokenRecord:
    id: str
    user_id: str
    expires_at: datetime


class RefreshTokenRepository:
    def __init__(self, session: Session):
        self._session = session

    def create(self, id: str, user_id: str, token_hash: str, expires_at: datetime) -> None:
        model = RefreshTokenModel(id=id, user_id=user_id, token_hash=token_hash, expires_at=expires_at)
        self._session.add(model)
        self._session.commit()

    def get_valid_by_hash(self, token_hash: str) -> RefreshTokenRecord | None:
        now = datetime.now(timezone.utc)
        model = (
            self._session.query(RefreshTokenModel)
            .filter(
                and_(
                    RefreshTokenModel.token_hash == token_hash,
                    RefreshTokenModel.revoked_at.is_(None),
                    RefreshTokenModel.expires_at > now,
                )
            )
            .first()
        )
        if model is None:
            return None
        return RefreshTokenRecord(id=model.id, user_id=model.user_id, expires_at=model.expires_at)

    def revoke(self, token_id: str) -> None:
        model = self._session.get(RefreshTokenModel, token_id)
        if model is not None:
            model.revoked_at = datetime.now(timezone.utc)
            self._session.commit()
```

**Note on datetime comparisons:** SQLite stores `datetime` values without timezone info by default via SQLAlchemy's generic `DateTime` type, which can make naive-vs-aware comparisons awkward. If `expires_at > now` comparisons behave unexpectedly in SQLite during testing (e.g. a timezone-aware `now()` failing to compare against a naive stored value), store and compare using naive UTC datetimes consistently: use `datetime.now(timezone.utc).replace(tzinfo=None)` wherever a value is written to or compared against the DB in this file, and note this adjustment in your report if you needed it.

- [ ] **Step 4: Run the tests, adjust for the datetime-comparison note above if needed, until they pass**

Run (from `apps/api`): `pytest tests/identity/test_refresh_token_repository.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/identity/infrastructure/refresh_token_repository.py apps/api/tests/identity/test_refresh_token_repository.py
git commit -m "feat(api): add RefreshTokenRepository"
```

---

### Task 8: Infrastructure — `ProjectRepository`

**Files:**
- Create: `apps/api/src/identity/infrastructure/project_repository.py`
- Test: `apps/api/tests/identity/test_project_repository.py`

**Interfaces:**
- Consumes: `ProjectModel` (Task 5), `Project` domain entity (Task 1).
- Produces: `ProjectRepository` class (constructed with a `Session`) with:
  - `create(id: str, user_id: str, name: str, sql: str, dialect: str) -> Project`
  - `list_by_user(user_id: str) -> list[Project]`
  - `get_by_id_and_user(project_id: str, user_id: str) -> Project | None`
  - `update(project_id: str, user_id: str, name: str, sql: str, dialect: str) -> Project | None`
  - `delete(project_id: str, user_id: str) -> bool` (returns `True` if a row was deleted, `False` if no matching project existed for that user)

- [ ] **Step 1: Write the failing test — `apps/api/tests/identity/test_project_repository.py`**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.identity.infrastructure.project_repository import ProjectRepository
from src.identity.infrastructure.user_repository import UserRepository
from src.shared_kernel.db import Base


def _make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_create_then_get_by_id_and_user_returns_the_project():
    session = _make_session()
    UserRepository(session).create(id="u1", email="a@example.com", password_hash="h")
    repo = ProjectRepository(session)

    created = repo.create(id="p1", user_id="u1", name="Schema A", sql="CREATE TABLE t(id INT);", dialect="postgres")
    found = repo.get_by_id_and_user("p1", "u1")

    assert found is not None
    assert found.id == created.id
    assert found.name == "Schema A"


def test_get_by_id_and_user_returns_none_for_a_different_users_project():
    session = _make_session()
    UserRepository(session).create(id="u1", email="a@example.com", password_hash="h")
    UserRepository(session).create(id="u2", email="b@example.com", password_hash="h")
    repo = ProjectRepository(session)
    repo.create(id="p1", user_id="u1", name="Schema A", sql="...", dialect="postgres")

    assert repo.get_by_id_and_user("p1", "u2") is None


def test_list_by_user_returns_only_that_users_projects():
    session = _make_session()
    UserRepository(session).create(id="u1", email="a@example.com", password_hash="h")
    UserRepository(session).create(id="u2", email="b@example.com", password_hash="h")
    repo = ProjectRepository(session)
    repo.create(id="p1", user_id="u1", name="A", sql="...", dialect="postgres")
    repo.create(id="p2", user_id="u2", name="B", sql="...", dialect="postgres")

    result = repo.list_by_user("u1")

    assert [p.id for p in result] == ["p1"]


def test_update_changes_the_project_fields():
    session = _make_session()
    UserRepository(session).create(id="u1", email="a@example.com", password_hash="h")
    repo = ProjectRepository(session)
    repo.create(id="p1", user_id="u1", name="Old", sql="OLD SQL", dialect="postgres")

    updated = repo.update("p1", "u1", name="New", sql="NEW SQL", dialect="mysql")

    assert updated is not None
    assert updated.name == "New"
    assert updated.sql == "NEW SQL"
    assert updated.dialect == "mysql"


def test_update_returns_none_for_a_different_users_project():
    session = _make_session()
    UserRepository(session).create(id="u1", email="a@example.com", password_hash="h")
    UserRepository(session).create(id="u2", email="b@example.com", password_hash="h")
    repo = ProjectRepository(session)
    repo.create(id="p1", user_id="u1", name="A", sql="...", dialect="postgres")

    assert repo.update("p1", "u2", name="Hacked", sql="...", dialect="postgres") is None


def test_delete_returns_true_and_removes_the_project():
    session = _make_session()
    UserRepository(session).create(id="u1", email="a@example.com", password_hash="h")
    repo = ProjectRepository(session)
    repo.create(id="p1", user_id="u1", name="A", sql="...", dialect="postgres")

    assert repo.delete("p1", "u1") is True
    assert repo.get_by_id_and_user("p1", "u1") is None


def test_delete_returns_false_for_a_different_users_project():
    session = _make_session()
    UserRepository(session).create(id="u1", email="a@example.com", password_hash="h")
    UserRepository(session).create(id="u2", email="b@example.com", password_hash="h")
    repo = ProjectRepository(session)
    repo.create(id="p1", user_id="u1", name="A", sql="...", dialect="postgres")

    assert repo.delete("p1", "u2") is False
```

- [ ] **Step 2: Run it to verify it fails**

Run (from `apps/api`): `pytest tests/identity/test_project_repository.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement `apps/api/src/identity/infrastructure/project_repository.py`**

```python
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.identity.domain.project import Project
from src.identity.infrastructure.models import ProjectModel


class ProjectRepository:
    def __init__(self, session: Session):
        self._session = session

    def create(self, id: str, user_id: str, name: str, sql: str, dialect: str) -> Project:
        model = ProjectModel(id=id, user_id=user_id, name=name, sql=sql, dialect=dialect)
        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)
        return self._to_domain(model)

    def list_by_user(self, user_id: str) -> list[Project]:
        models = self._session.query(ProjectModel).filter_by(user_id=user_id).order_by(ProjectModel.created_at).all()
        return [self._to_domain(m) for m in models]

    def get_by_id_and_user(self, project_id: str, user_id: str) -> Project | None:
        model = self._find(project_id, user_id)
        return self._to_domain(model) if model else None

    def update(self, project_id: str, user_id: str, name: str, sql: str, dialect: str) -> Project | None:
        model = self._find(project_id, user_id)
        if model is None:
            return None
        model.name = name
        model.sql = sql
        model.dialect = dialect
        model.updated_at = datetime.now(timezone.utc)
        self._session.commit()
        self._session.refresh(model)
        return self._to_domain(model)

    def delete(self, project_id: str, user_id: str) -> bool:
        model = self._find(project_id, user_id)
        if model is None:
            return False
        self._session.delete(model)
        self._session.commit()
        return True

    def _find(self, project_id: str, user_id: str) -> ProjectModel | None:
        return self._session.query(ProjectModel).filter_by(id=project_id, user_id=user_id).first()

    @staticmethod
    def _to_domain(model: ProjectModel) -> Project:
        return Project(
            id=model.id,
            user_id=model.user_id,
            name=model.name,
            sql=model.sql,
            dialect=model.dialect,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run (from `apps/api`): `pytest tests/identity/test_project_repository.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/identity/infrastructure/project_repository.py apps/api/tests/identity/test_project_repository.py
git commit -m "feat(api): add ProjectRepository with per-user ownership scoping"
```

---

### Task 9: Application — `RegisterUser`

**Files:**
- Create: `apps/api/src/identity/application/register_user.py`
- Test: `apps/api/tests/identity/test_register_user.py`

**Interfaces:**
- Consumes: `UserRepository` (Task 6), `PasswordHasher` (Task 2), `EmailAlreadyRegisteredError` (Task 1).
- Produces: `RegisterUser` class (constructed with a `UserRepository` and a `PasswordHasher`) with `execute(email: str, password: str) -> User`. Raises `EmailAlreadyRegisteredError` if the email is already taken.

- [ ] **Step 1: Write the failing test — `apps/api/tests/identity/test_register_user.py`**

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.identity.application.register_user import RegisterUser
from src.identity.domain.errors import EmailAlreadyRegisteredError
from src.identity.infrastructure.password_hasher import PasswordHasher
from src.identity.infrastructure.user_repository import UserRepository
from src.shared_kernel.db import Base


def _make_use_case():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    return RegisterUser(UserRepository(session), PasswordHasher())


def test_registers_a_new_user_with_a_hashed_password():
    use_case = _make_use_case()

    user = use_case.execute("a@example.com", "correct horse battery staple")

    assert user.email == "a@example.com"
    assert user.password_hash != "correct horse battery staple"


def test_rejects_a_duplicate_email():
    use_case = _make_use_case()
    use_case.execute("a@example.com", "password1")

    with pytest.raises(EmailAlreadyRegisteredError):
        use_case.execute("a@example.com", "password2")
```

- [ ] **Step 2: Run it to verify it fails**

Run (from `apps/api`): `pytest tests/identity/test_register_user.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement `apps/api/src/identity/application/register_user.py`**

```python
import uuid

from src.identity.domain.errors import EmailAlreadyRegisteredError
from src.identity.domain.user import User
from src.identity.infrastructure.password_hasher import PasswordHasher
from src.identity.infrastructure.user_repository import UserRepository


class RegisterUser:
    def __init__(self, user_repository: UserRepository, password_hasher: PasswordHasher):
        self._user_repository = user_repository
        self._password_hasher = password_hasher

    def execute(self, email: str, password: str) -> User:
        if self._user_repository.get_by_email(email) is not None:
            raise EmailAlreadyRegisteredError(email)

        password_hash = self._password_hasher.hash(password)
        return self._user_repository.create(id=str(uuid.uuid4()), email=email, password_hash=password_hash)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run (from `apps/api`): `pytest tests/identity/test_register_user.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/identity/application/register_user.py apps/api/tests/identity/test_register_user.py
git commit -m "feat(api): add RegisterUser use case"
```

---

### Task 10: Application — `AuthenticateUser` (login)

**Files:**
- Create: `apps/api/src/identity/application/authenticate_user.py`
- Test: `apps/api/tests/identity/test_authenticate_user.py`

**Interfaces:**
- Consumes: `UserRepository` (Task 6), `PasswordHasher` (Task 2), `JwtService` (Task 3), `RefreshTokenRepository` (Task 7), `InvalidCredentialsError` (Task 1).
- Produces: `TokenPair` (dataclass: `access_token: str`, `refresh_token: str`), `AuthenticateUser` class (constructed with `UserRepository`, `PasswordHasher`, `JwtService`, `RefreshTokenRepository`, `refresh_token_expiry_days: int = 30`) with `execute(email: str, password: str) -> TokenPair`. Raises `InvalidCredentialsError` for a wrong email or password (same exception for both — never reveal which one was wrong).

- [ ] **Step 1: Write the failing test — `apps/api/tests/identity/test_authenticate_user.py`**

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.identity.application.authenticate_user import AuthenticateUser
from src.identity.application.register_user import RegisterUser
from src.identity.domain.errors import InvalidCredentialsError
from src.identity.infrastructure.jwt_service import JwtService
from src.identity.infrastructure.password_hasher import PasswordHasher
from src.identity.infrastructure.refresh_token_repository import RefreshTokenRepository
from src.identity.infrastructure.user_repository import UserRepository
from src.shared_kernel.db import Base


def _make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _register(session, email="a@example.com", password="correct horse battery staple"):
    RegisterUser(UserRepository(session), PasswordHasher()).execute(email, password)


def _make_use_case(session):
    return AuthenticateUser(
        UserRepository(session),
        PasswordHasher(),
        JwtService(secret="test-secret"),
        RefreshTokenRepository(session),
    )


def test_returns_a_token_pair_for_correct_credentials():
    session = _make_session()
    _register(session)
    use_case = _make_use_case(session)

    tokens = use_case.execute("a@example.com", "correct horse battery staple")

    assert tokens.access_token
    assert tokens.refresh_token


def test_rejects_wrong_password():
    session = _make_session()
    _register(session)
    use_case = _make_use_case(session)

    with pytest.raises(InvalidCredentialsError):
        use_case.execute("a@example.com", "wrong password")


def test_rejects_unknown_email():
    session = _make_session()
    use_case = _make_use_case(session)

    with pytest.raises(InvalidCredentialsError):
        use_case.execute("missing@example.com", "anything")
```

- [ ] **Step 2: Run it to verify it fails**

Run (from `apps/api`): `pytest tests/identity/test_authenticate_user.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement `apps/api/src/identity/application/authenticate_user.py`**

```python
import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from src.identity.domain.errors import InvalidCredentialsError
from src.identity.infrastructure.jwt_service import JwtService
from src.identity.infrastructure.password_hasher import PasswordHasher
from src.identity.infrastructure.refresh_token_repository import RefreshTokenRepository
from src.identity.infrastructure.user_repository import UserRepository


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str


class AuthenticateUser:
    def __init__(
        self,
        user_repository: UserRepository,
        password_hasher: PasswordHasher,
        jwt_service: JwtService,
        refresh_token_repository: RefreshTokenRepository,
        refresh_token_expiry_days: int = 30,
    ):
        self._user_repository = user_repository
        self._password_hasher = password_hasher
        self._jwt_service = jwt_service
        self._refresh_token_repository = refresh_token_repository
        self._refresh_token_expiry_days = refresh_token_expiry_days

    def execute(self, email: str, password: str) -> TokenPair:
        user = self._user_repository.get_by_email(email)
        if user is None or not self._password_hasher.verify(user.password_hash, password):
            raise InvalidCredentialsError()

        access_token = self._jwt_service.create_access_token(user.id)
        refresh_token = self._issue_refresh_token(user.id)
        return TokenPair(access_token=access_token, refresh_token=refresh_token)

    def _issue_refresh_token(self, user_id: str) -> str:
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(days=self._refresh_token_expiry_days)
        self._refresh_token_repository.create(
            id=str(uuid.uuid4()), user_id=user_id, token_hash=token_hash, expires_at=expires_at
        )
        return raw_token
```

- [ ] **Step 4: Run the tests to verify they pass**

Run (from `apps/api`): `pytest tests/identity/test_authenticate_user.py -v`
Expected: PASS (3 tests) — adjust the `expires_at` timezone handling here to match whatever you settled on in Task 7 if you hit a naive/aware comparison issue there.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/identity/application/authenticate_user.py apps/api/tests/identity/test_authenticate_user.py
git commit -m "feat(api): add AuthenticateUser use case issuing access+refresh token pairs"
```

---

### Task 11: Application — `RefreshAccessToken` and `Logout`

**Files:**
- Create: `apps/api/src/identity/application/refresh_access_token.py`
- Create: `apps/api/src/identity/application/logout.py`
- Test: `apps/api/tests/identity/test_refresh_and_logout.py`

**Interfaces:**
- Consumes: `RefreshTokenRepository` (Task 7), `JwtService` (Task 3), `TokenPair` (Task 10), `InvalidRefreshTokenError` (Task 1).
- Produces: `RefreshAccessToken` class (constructed with `RefreshTokenRepository`, `JwtService`, `refresh_token_expiry_days: int = 30`) with `execute(raw_refresh_token: str) -> TokenPair` — verifies the token, revokes it, issues a new pair (rotation). Raises `InvalidRefreshTokenError` if the token is unknown/expired/already revoked. `Logout` class (constructed with `RefreshTokenRepository`) with `execute(raw_refresh_token: str) -> None` — revokes the token if it's currently valid; silently no-ops if it's already invalid/unknown (logout is idempotent, never an error case for the caller).

- [ ] **Step 1: Write the failing tests — `apps/api/tests/identity/test_refresh_and_logout.py`**

```python
import hashlib
import secrets

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.identity.application.logout import Logout
from src.identity.application.refresh_access_token import RefreshAccessToken
from src.identity.domain.errors import InvalidRefreshTokenError
from src.identity.infrastructure.jwt_service import JwtService
from src.identity.infrastructure.refresh_token_repository import RefreshTokenRepository
from src.shared_kernel.db import Base


def _make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _issue_raw_token(repo, user_id="u1"):
    from datetime import datetime, timedelta, timezone
    import uuid

    raw = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    repo.create(
        id=str(uuid.uuid4()),
        user_id=user_id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    )
    return raw


def test_refresh_issues_a_new_token_pair_and_revokes_the_old_one():
    session = _make_session()
    repo = RefreshTokenRepository(session)
    raw = _issue_raw_token(repo)
    use_case = RefreshAccessToken(repo, JwtService(secret="test-secret"))

    tokens = use_case.execute(raw)

    assert tokens.access_token
    assert tokens.refresh_token != raw
    # the old token is now revoked — using it again must fail
    with pytest.raises(InvalidRefreshTokenError):
        use_case.execute(raw)


def test_refresh_rejects_an_unknown_token():
    session = _make_session()
    repo = RefreshTokenRepository(session)
    use_case = RefreshAccessToken(repo, JwtService(secret="test-secret"))

    with pytest.raises(InvalidRefreshTokenError):
        use_case.execute("not-a-real-token")


def test_logout_revokes_a_valid_token():
    session = _make_session()
    repo = RefreshTokenRepository(session)
    raw = _issue_raw_token(repo)
    use_case = RefreshAccessToken(repo, JwtService(secret="test-secret"))

    Logout(repo).execute(raw)

    with pytest.raises(InvalidRefreshTokenError):
        use_case.execute(raw)


def test_logout_is_a_no_op_for_an_unknown_token():
    session = _make_session()
    repo = RefreshTokenRepository(session)

    Logout(repo).execute("not-a-real-token")  # must not raise
```

- [ ] **Step 2: Run it to verify it fails**

Run (from `apps/api`): `pytest tests/identity/test_refresh_and_logout.py -v`
Expected: FAIL — modules don't exist.

- [ ] **Step 3: Implement `apps/api/src/identity/application/refresh_access_token.py`**

```python
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from src.identity.application.authenticate_user import TokenPair
from src.identity.domain.errors import InvalidRefreshTokenError
from src.identity.infrastructure.jwt_service import JwtService
from src.identity.infrastructure.refresh_token_repository import RefreshTokenRepository


class RefreshAccessToken:
    def __init__(
        self,
        refresh_token_repository: RefreshTokenRepository,
        jwt_service: JwtService,
        refresh_token_expiry_days: int = 30,
    ):
        self._refresh_token_repository = refresh_token_repository
        self._jwt_service = jwt_service
        self._refresh_token_expiry_days = refresh_token_expiry_days

    def execute(self, raw_refresh_token: str) -> TokenPair:
        token_hash = hashlib.sha256(raw_refresh_token.encode()).hexdigest()
        record = self._refresh_token_repository.get_valid_by_hash(token_hash)
        if record is None:
            raise InvalidRefreshTokenError()

        self._refresh_token_repository.revoke(record.id)

        access_token = self._jwt_service.create_access_token(record.user_id)
        new_raw_token = secrets.token_urlsafe(32)
        new_token_hash = hashlib.sha256(new_raw_token.encode()).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(days=self._refresh_token_expiry_days)
        self._refresh_token_repository.create(
            id=str(uuid.uuid4()), user_id=record.user_id, token_hash=new_token_hash, expires_at=expires_at
        )
        return TokenPair(access_token=access_token, refresh_token=new_raw_token)
```

- [ ] **Step 4: Implement `apps/api/src/identity/application/logout.py`**

```python
import hashlib

from src.identity.infrastructure.refresh_token_repository import RefreshTokenRepository


class Logout:
    def __init__(self, refresh_token_repository: RefreshTokenRepository):
        self._refresh_token_repository = refresh_token_repository

    def execute(self, raw_refresh_token: str) -> None:
        token_hash = hashlib.sha256(raw_refresh_token.encode()).hexdigest()
        record = self._refresh_token_repository.get_valid_by_hash(token_hash)
        if record is not None:
            self._refresh_token_repository.revoke(record.id)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run (from `apps/api`): `pytest tests/identity/test_refresh_and_logout.py -v`
Expected: PASS (4 tests)

- [ ] **Step 6: Commit**

```bash
git add apps/api/src/identity/application/refresh_access_token.py apps/api/src/identity/application/logout.py apps/api/tests/identity/test_refresh_and_logout.py
git commit -m "feat(api): add RefreshAccessToken (rotation) and Logout use cases"
```

---

### Task 12: Interfaces — auth schemas, `get_current_user`, `/api/auth/*` router

**Files:**
- Create: `apps/api/src/identity/interfaces/schemas.py`
- Create: `apps/api/src/identity/interfaces/dependencies.py`
- Create: `apps/api/src/identity/interfaces/auth_router.py`
- Modify: `apps/api/src/main.py` (register the auth router)
- Test: `apps/api/tests/identity/test_auth_endpoints.py`

**Interfaces:**
- Consumes: `RegisterUser` (Task 9), `AuthenticateUser`/`TokenPair` (Task 10), `RefreshAccessToken`/`Logout` (Task 11), `JwtService` (Task 3), all the domain errors (Task 1), `error_body` (Phase 1), `get_db` (Phase 1).
- Produces: Pydantic models `RegisterRequest`, `RegisterResponse`, `LoginRequest`, `TokenResponse`, `RefreshRequest`, `LogoutRequest` in `schemas.py`; `get_current_user(request) -> str` dependency in `dependencies.py` (returns the authenticated user's id, or raises an `HTTPException(401)` — used directly by FastAPI's dependency injection, not caught by application-layer error handling since it's a pure interface-layer concern); the auth router at `/api/auth/register`, `/login`, `/refresh`, `/logout`.

- [ ] **Step 1: Write the failing tests — `apps/api/tests/identity/test_auth_endpoints.py`**

```python
def test_register_then_login_then_access_protected_route(client):
    register = client.post("/api/auth/register", json={"email": "a@example.com", "password": "correct horse battery staple"})
    assert register.status_code == 201
    assert register.json()["email"] == "a@example.com"

    login = client.post("/api/auth/login", json={"email": "a@example.com", "password": "correct horse battery staple"})
    assert login.status_code == 200
    tokens = login.json()
    assert "access_token" in tokens and "refresh_token" in tokens

    protected = client.get("/api/projects", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert protected.status_code == 200
    assert protected.json() == []


def test_register_rejects_duplicate_email(client):
    payload = {"email": "dup@example.com", "password": "correct horse battery staple"}
    client.post("/api/auth/register", json=payload)

    response = client.post("/api/auth/register", json=payload)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_already_registered"


def test_login_rejects_wrong_password(client):
    client.post("/api/auth/register", json={"email": "b@example.com", "password": "correct horse battery staple"})

    response = client.post("/api/auth/login", json={"email": "b@example.com", "password": "wrong"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_accessing_a_protected_route_without_a_token_returns_401(client):
    response = client.get("/api/projects")

    assert response.status_code == 401


def test_refresh_then_logout_flow(client):
    client.post("/api/auth/register", json={"email": "c@example.com", "password": "correct horse battery staple"})
    login = client.post("/api/auth/login", json={"email": "c@example.com", "password": "correct horse battery staple"})
    refresh_token = login.json()["refresh_token"]

    refreshed = client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert refreshed.status_code == 200
    new_tokens = refreshed.json()

    # old refresh token is now revoked
    reused = client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert reused.status_code == 401

    logout = client.post("/api/auth/logout", json={"refresh_token": new_tokens["refresh_token"]})
    assert logout.status_code == 204
```

- [ ] **Step 2: Run it to verify it fails**

Run (from `apps/api`): `pytest tests/identity/test_auth_endpoints.py -v`
Expected: FAIL — 404s (no routes registered yet).

- [ ] **Step 3: Implement `apps/api/src/identity/interfaces/schemas.py`**

```python
from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)


class RegisterResponse(BaseModel):
    id: str
    email: str


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str
```

- [ ] **Step 4: Implement `apps/api/src/identity/interfaces/dependencies.py`**

```python
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
import jwt

from src.identity.infrastructure.jwt_service import JwtService
from src.shared_kernel.db import get_db
from src.shared_kernel.settings import get_settings

_security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_security),
    db: Session = Depends(get_db),
) -> str:
    settings = get_settings()
    jwt_service = JwtService(secret=settings.jwt_secret)
    try:
        return jwt_service.decode_access_token(credentials.credentials)
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired access token") from exc
```

Note: `db` is accepted here (unused directly) to keep the dependency signature consistent with how `get_current_user` will be depended on alongside `get_db` in the projects router (Task 14) — FastAPI resolves each `Depends(...)` independently regardless, so this is not strictly required, but if it turns out unnecessary in practice, it's fine to drop the unused `db` parameter; use your judgment and note the choice in your report.

- [ ] **Step 5: Implement `apps/api/src/identity/interfaces/auth_router.py`**

```python
from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from src.identity.application.authenticate_user import AuthenticateUser
from src.identity.application.logout import Logout
from src.identity.application.refresh_access_token import RefreshAccessToken
from src.identity.application.register_user import RegisterUser
from src.identity.domain.errors import (
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
)
from src.identity.infrastructure.jwt_service import JwtService
from src.identity.infrastructure.password_hasher import PasswordHasher
from src.identity.infrastructure.refresh_token_repository import RefreshTokenRepository
from src.identity.infrastructure.user_repository import UserRepository
from src.identity.interfaces.schemas import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
)
from src.shared_kernel.db import get_db
from src.shared_kernel.errors import error_body
from src.shared_kernel.settings import get_settings

router = APIRouter(prefix="/api/auth", tags=["identity"])


def _jwt_service() -> JwtService:
    return JwtService(secret=get_settings().jwt_secret)


@router.post("/register", status_code=201)
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    use_case = RegisterUser(UserRepository(db), PasswordHasher())
    try:
        user = use_case.execute(request.email, request.password)
    except EmailAlreadyRegisteredError as exc:
        return JSONResponse(status_code=409, content=error_body("email_already_registered", str(exc)))
    return RegisterResponse(id=user.id, email=user.email)


@router.post("/login")
def login(request: LoginRequest, db: Session = Depends(get_db)):
    use_case = AuthenticateUser(UserRepository(db), PasswordHasher(), _jwt_service(), RefreshTokenRepository(db))
    try:
        tokens = use_case.execute(request.email, request.password)
    except InvalidCredentialsError as exc:
        return JSONResponse(status_code=401, content=error_body("invalid_credentials", str(exc)))
    return TokenResponse(access_token=tokens.access_token, refresh_token=tokens.refresh_token)


@router.post("/refresh")
def refresh(request: RefreshRequest, db: Session = Depends(get_db)):
    use_case = RefreshAccessToken(RefreshTokenRepository(db), _jwt_service())
    try:
        tokens = use_case.execute(request.refresh_token)
    except InvalidRefreshTokenError as exc:
        return JSONResponse(status_code=401, content=error_body("invalid_refresh_token", str(exc)))
    return TokenResponse(access_token=tokens.access_token, refresh_token=tokens.refresh_token)


@router.post("/logout", status_code=204)
def logout(request: LogoutRequest, db: Session = Depends(get_db)):
    Logout(RefreshTokenRepository(db)).execute(request.refresh_token)
    return Response(status_code=204)
```

- [ ] **Step 6: Register the router in `apps/api/src/main.py`**

```python
from src.identity.interfaces.auth_router import router as auth_router

def create_app() -> FastAPI:
    # ... existing settings/middleware/health_router/schema_design_router setup ...
    app.include_router(auth_router)
    return app
```

Add the import alongside the existing router imports, and `app.include_router(auth_router)` right after the existing `app.include_router(schema_design_router)` line, before `return app`.

- [ ] **Step 7: Run the tests to verify they pass**

Run (from `apps/api`): `pytest tests/identity/test_auth_endpoints.py -v`
Expected: PASS (5 tests) — note `test_register_then_login_then_access_protected_route` depends on `GET /api/projects` existing, which is Task 14; if you're implementing tasks strictly in order, that one test will fail until Task 14 lands — that's expected and fine, it's specified here because it's the natural end-to-end auth+projects test, not because it must pass within this task. The other 4 tests in this file must pass now.

- [ ] **Step 8: Commit**

```bash
git add apps/api/src/identity/interfaces/schemas.py apps/api/src/identity/interfaces/dependencies.py apps/api/src/identity/interfaces/auth_router.py apps/api/src/main.py apps/api/tests/identity/test_auth_endpoints.py
git commit -m "feat(api): add /api/auth/* endpoints (register, login, refresh, logout)"
```

---

### Task 13: Application — Project use cases

**Files:**
- Create: `apps/api/src/identity/application/project_use_cases.py`
- Test: `apps/api/tests/identity/test_project_use_cases.py`

**Interfaces:**
- Consumes: `ProjectRepository` (Task 8), `Project` (Task 1), `ProjectNotFoundError` (Task 1).
- Produces: `CreateProject`, `ListProjects`, `GetProject`, `UpdateProject`, `DeleteProject` — five small classes, each constructed with a `ProjectRepository`, each with an `execute(...)` method:
  - `CreateProject.execute(user_id: str, name: str, sql: str, dialect: str) -> Project`
  - `ListProjects.execute(user_id: str) -> list[Project]`
  - `GetProject.execute(project_id: str, user_id: str) -> Project` (raises `ProjectNotFoundError` if not found/not owned)
  - `UpdateProject.execute(project_id: str, user_id: str, name: str, sql: str, dialect: str) -> Project` (raises `ProjectNotFoundError`)
  - `DeleteProject.execute(project_id: str, user_id: str) -> None` (raises `ProjectNotFoundError`)

- [ ] **Step 1: Write the failing test — `apps/api/tests/identity/test_project_use_cases.py`**

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.identity.application.project_use_cases import (
    CreateProject,
    DeleteProject,
    GetProject,
    ListProjects,
    UpdateProject,
)
from src.identity.domain.errors import ProjectNotFoundError
from src.identity.infrastructure.project_repository import ProjectRepository
from src.identity.infrastructure.user_repository import UserRepository
from src.shared_kernel.db import Base


def _make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    UserRepository(session).create(id="u1", email="a@example.com", password_hash="h")
    UserRepository(session).create(id="u2", email="b@example.com", password_hash="h")
    return session


def test_create_then_get_returns_the_project():
    session = _make_session()
    repo = ProjectRepository(session)
    created = CreateProject(repo).execute("u1", "My Schema", "CREATE TABLE t(id INT);", "postgres")

    found = GetProject(repo).execute(created.id, "u1")

    assert found.name == "My Schema"


def test_get_raises_not_found_for_another_users_project():
    session = _make_session()
    repo = ProjectRepository(session)
    created = CreateProject(repo).execute("u1", "My Schema", "...", "postgres")

    with pytest.raises(ProjectNotFoundError):
        GetProject(repo).execute(created.id, "u2")


def test_list_returns_only_the_users_projects():
    session = _make_session()
    repo = ProjectRepository(session)
    CreateProject(repo).execute("u1", "A", "...", "postgres")
    CreateProject(repo).execute("u2", "B", "...", "postgres")

    result = ListProjects(repo).execute("u1")

    assert [p.name for p in result] == ["A"]


def test_update_changes_the_project():
    session = _make_session()
    repo = ProjectRepository(session)
    created = CreateProject(repo).execute("u1", "Old", "OLD", "postgres")

    updated = UpdateProject(repo).execute(created.id, "u1", "New", "NEW", "mysql")

    assert updated.name == "New"
    assert updated.dialect == "mysql"


def test_update_raises_not_found_for_another_users_project():
    session = _make_session()
    repo = ProjectRepository(session)
    created = CreateProject(repo).execute("u1", "A", "...", "postgres")

    with pytest.raises(ProjectNotFoundError):
        UpdateProject(repo).execute(created.id, "u2", "Hacked", "...", "postgres")


def test_delete_removes_the_project():
    session = _make_session()
    repo = ProjectRepository(session)
    created = CreateProject(repo).execute("u1", "A", "...", "postgres")

    DeleteProject(repo).execute(created.id, "u1")

    with pytest.raises(ProjectNotFoundError):
        GetProject(repo).execute(created.id, "u1")


def test_delete_raises_not_found_for_another_users_project():
    session = _make_session()
    repo = ProjectRepository(session)
    created = CreateProject(repo).execute("u1", "A", "...", "postgres")

    with pytest.raises(ProjectNotFoundError):
        DeleteProject(repo).execute(created.id, "u2")
```

- [ ] **Step 2: Run it to verify it fails**

Run (from `apps/api`): `pytest tests/identity/test_project_use_cases.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement `apps/api/src/identity/application/project_use_cases.py`**

```python
import uuid

from src.identity.domain.errors import ProjectNotFoundError
from src.identity.domain.project import Project
from src.identity.infrastructure.project_repository import ProjectRepository


class CreateProject:
    def __init__(self, project_repository: ProjectRepository):
        self._project_repository = project_repository

    def execute(self, user_id: str, name: str, sql: str, dialect: str) -> Project:
        return self._project_repository.create(id=str(uuid.uuid4()), user_id=user_id, name=name, sql=sql, dialect=dialect)


class ListProjects:
    def __init__(self, project_repository: ProjectRepository):
        self._project_repository = project_repository

    def execute(self, user_id: str) -> list[Project]:
        return self._project_repository.list_by_user(user_id)


class GetProject:
    def __init__(self, project_repository: ProjectRepository):
        self._project_repository = project_repository

    def execute(self, project_id: str, user_id: str) -> Project:
        project = self._project_repository.get_by_id_and_user(project_id, user_id)
        if project is None:
            raise ProjectNotFoundError(project_id)
        return project


class UpdateProject:
    def __init__(self, project_repository: ProjectRepository):
        self._project_repository = project_repository

    def execute(self, project_id: str, user_id: str, name: str, sql: str, dialect: str) -> Project:
        project = self._project_repository.update(project_id, user_id, name=name, sql=sql, dialect=dialect)
        if project is None:
            raise ProjectNotFoundError(project_id)
        return project


class DeleteProject:
    def __init__(self, project_repository: ProjectRepository):
        self._project_repository = project_repository

    def execute(self, project_id: str, user_id: str) -> None:
        deleted = self._project_repository.delete(project_id, user_id)
        if not deleted:
            raise ProjectNotFoundError(project_id)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run (from `apps/api`): `pytest tests/identity/test_project_use_cases.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/identity/application/project_use_cases.py apps/api/tests/identity/test_project_use_cases.py
git commit -m "feat(api): add Create/List/Get/Update/DeleteProject use cases"
```

---

### Task 14: Interfaces — project schemas + `/api/projects/*` router

**Files:**
- Modify: `apps/api/src/identity/interfaces/schemas.py` (add project schemas)
- Create: `apps/api/src/identity/interfaces/projects_router.py`
- Modify: `apps/api/src/main.py` (register the projects router)
- Test: `apps/api/tests/identity/test_project_endpoints.py`

**Interfaces:**
- Consumes: `CreateProject`/`ListProjects`/`GetProject`/`UpdateProject`/`DeleteProject` (Task 13), `get_current_user` (Task 12), `ProjectNotFoundError` (Task 1).
- Produces: `ProjectSummaryResponse`, `ProjectResponse`, `ProjectCreateRequest`, `ProjectUpdateRequest` in `schemas.py`; the projects router at `GET/POST /api/projects`, `GET/PUT/DELETE /api/projects/{project_id}`.

- [ ] **Step 1: Write the failing tests — `apps/api/tests/identity/test_project_endpoints.py`**

```python
def _register_and_login(client, email="proj@example.com"):
    client.post("/api/auth/register", json={"email": email, "password": "correct horse battery staple"})
    login = client.post("/api/auth/login", json={"email": email, "password": "correct horse battery staple"})
    return login.json()["access_token"]


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_create_list_get_update_delete_project_flow(client):
    token = _register_and_login(client)
    headers = _auth_headers(token)

    create = client.post(
        "/api/projects", json={"name": "My Schema", "sql": "CREATE TABLE t(id INT);", "dialect": "postgres"}, headers=headers
    )
    assert create.status_code == 201
    project_id = create.json()["id"]

    listed = client.get("/api/projects", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    fetched = client.get(f"/api/projects/{project_id}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["sql"] == "CREATE TABLE t(id INT);"

    updated = client.put(
        f"/api/projects/{project_id}", json={"name": "Renamed", "sql": "CREATE TABLE u(id INT);", "dialect": "mysql"}, headers=headers
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Renamed"

    deleted = client.delete(f"/api/projects/{project_id}", headers=headers)
    assert deleted.status_code == 204

    gone = client.get(f"/api/projects/{project_id}", headers=headers)
    assert gone.status_code == 404


def test_a_user_cannot_access_another_users_project(client):
    token_a = _register_and_login(client, email="owner@example.com")
    token_b = _register_and_login(client, email="intruder@example.com")

    create = client.post(
        "/api/projects", json={"name": "Private", "sql": "...", "dialect": "postgres"}, headers=_auth_headers(token_a)
    )
    project_id = create.json()["id"]

    response = client.get(f"/api/projects/{project_id}", headers=_auth_headers(token_b))

    assert response.status_code == 404


def test_projects_endpoints_require_authentication(client):
    response = client.post("/api/projects", json={"name": "X", "sql": "...", "dialect": "postgres"})

    assert response.status_code == 401
```

- [ ] **Step 2: Run it to verify it fails**

Run (from `apps/api`): `pytest tests/identity/test_project_endpoints.py -v`
Expected: FAIL — 404s (no routes registered yet).

- [ ] **Step 3: Add project schemas to `apps/api/src/identity/interfaces/schemas.py`** (append)

```python
from datetime import datetime


class ProjectCreateRequest(BaseModel):
    name: str
    sql: str
    dialect: str


class ProjectUpdateRequest(BaseModel):
    name: str
    sql: str
    dialect: str


class ProjectSummaryResponse(BaseModel):
    id: str
    name: str
    dialect: str
    updated_at: datetime


class ProjectResponse(BaseModel):
    id: str
    name: str
    sql: str
    dialect: str
    created_at: datetime
    updated_at: datetime
```
(Add `from datetime import datetime` near the top of the file alongside the existing imports, not duplicated inline.)

- [ ] **Step 4: Implement `apps/api/src/identity/interfaces/projects_router.py`**

```python
from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from src.identity.application.project_use_cases import (
    CreateProject,
    DeleteProject,
    GetProject,
    ListProjects,
    UpdateProject,
)
from src.identity.domain.errors import ProjectNotFoundError
from src.identity.infrastructure.project_repository import ProjectRepository
from src.identity.interfaces.dependencies import get_current_user
from src.identity.interfaces.schemas import (
    ProjectCreateRequest,
    ProjectResponse,
    ProjectSummaryResponse,
    ProjectUpdateRequest,
)
from src.shared_kernel.db import get_db
from src.shared_kernel.errors import error_body

router = APIRouter(prefix="/api/projects", tags=["identity"])


@router.get("")
def list_projects(user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    projects = ListProjects(ProjectRepository(db)).execute(user_id)
    return [
        ProjectSummaryResponse(id=p.id, name=p.name, dialect=p.dialect, updated_at=p.updated_at) for p in projects
    ]


@router.post("", status_code=201)
def create_project(
    request: ProjectCreateRequest, user_id: str = Depends(get_current_user), db: Session = Depends(get_db)
):
    project = CreateProject(ProjectRepository(db)).execute(user_id, request.name, request.sql, request.dialect)
    return _to_response(project)


@router.get("/{project_id}")
def get_project(project_id: str, user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        project = GetProject(ProjectRepository(db)).execute(project_id, user_id)
    except ProjectNotFoundError as exc:
        return JSONResponse(status_code=404, content=error_body("project_not_found", str(exc)))
    return _to_response(project)


@router.put("/{project_id}")
def update_project(
    project_id: str,
    request: ProjectUpdateRequest,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        project = UpdateProject(ProjectRepository(db)).execute(
            project_id, user_id, request.name, request.sql, request.dialect
        )
    except ProjectNotFoundError as exc:
        return JSONResponse(status_code=404, content=error_body("project_not_found", str(exc)))
    return _to_response(project)


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str, user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        DeleteProject(ProjectRepository(db)).execute(project_id, user_id)
    except ProjectNotFoundError as exc:
        return JSONResponse(status_code=404, content=error_body("project_not_found", str(exc)))
    return Response(status_code=204)


def _to_response(project) -> ProjectResponse:
    return ProjectResponse(
        id=project.id,
        name=project.name,
        sql=project.sql,
        dialect=project.dialect,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )
```

- [ ] **Step 5: Register the router in `apps/api/src/main.py`**

```python
from src.identity.interfaces.projects_router import router as projects_router

def create_app() -> FastAPI:
    # ... existing setup ...
    app.include_router(projects_router)
    return app
```

Add the import alongside the others, and `app.include_router(projects_router)` right after `app.include_router(auth_router)`, before `return app`.

- [ ] **Step 6: Run this task's tests, then the full suite**

Run (from `apps/api`): `pytest tests/identity/test_project_endpoints.py -v`
Expected: PASS (3 tests)

Then run (from `apps/api`): `pytest -v`
Expected: ALL tests in the project pass, including Task 12's `test_register_then_login_then_access_protected_route` (which was expected to fail until this task landed) and everything from Phases 1-2.

- [ ] **Step 7: Run Ruff**

Run (from `apps/api`): `ruff check .` and `ruff format --check .`
Expected: 0 errors. Fix any findings before committing (this branch's history shows accumulated lint drift is a real recurring risk — run this for real, don't skip it).

- [ ] **Step 8: Manual spot-check via Swagger**

Run: `uvicorn src.main:app --reload` (from `apps/api`), open `http://127.0.0.1:8000/docs`, walk through register → login → create a project → list → get → update → delete using the returned access token (Swagger UI's "Authorize" button accepts a Bearer token). Confirm ownership enforcement by creating a second user and confirming they can't see the first user's project. Stop the server after.

- [ ] **Step 9: Regenerate `packages/api-client`** (same pattern as Phase 2's Task 11)

Run (from `apps/api`): `python scripts/export_openapi.py`
Run (from `packages/api-client`): `pnpm generate`
Run (from repo root): `git add packages/api-client/src/schema.ts && git diff --exit-code packages/api-client/src/schema.ts` (confirms the CI drift check will pass)
Run (from `apps/web`): `tsc --noEmit` (confirms nothing broke)

- [ ] **Step 10: Commit**

```bash
git add apps/api/src/identity/interfaces apps/api/src/main.py apps/api/tests/identity/test_project_endpoints.py packages/api-client/src/schema.ts
git commit -m "feat(api): add /api/projects/* endpoints with per-user ownership"
```

---

## Self-Review Notes

- **Spec coverage:** domain entities (Task 1), password hashing (Task 2), JWT access tokens (Task 3), DB schema via migration (Tasks 4-5), all three repositories with ownership scoping (Tasks 6-8), all five auth use cases including rotation (Tasks 9-11), all five project use cases (Task 13), the full `/api/auth/*` and `/api/projects/*` HTTP surface with the exact contract from the spec including 404-not-403 anti-enumeration (Tasks 12, 14), api-client regeneration (Task 14). `schema_design`'s endpoint is never touched by any task.
- **Placeholder scan:** every step has literal, complete code. The one deliberately-left judgment call (Task 3's `test_settings.py` fix, Task 6's naive/aware datetime note) is flagged as a concrete decision point with an exact fallback, not a vague TODO.
- **Type consistency:** `User`/`Project` fields (Task 1) match the SQLAlchemy models' columns (Task 5) match each repository's `_to_domain` mapping (Tasks 6, 8) match the Pydantic response schemas (Tasks 12, 14). `TokenPair` is defined once (Task 10) and imported by Task 11 rather than redefined. `get_current_user`'s return type (`str`, the user id) is used identically by both routers (Tasks 12, 14) as `user_id: str = Depends(get_current_user)`.
