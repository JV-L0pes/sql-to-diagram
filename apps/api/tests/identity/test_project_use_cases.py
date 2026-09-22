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
