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
