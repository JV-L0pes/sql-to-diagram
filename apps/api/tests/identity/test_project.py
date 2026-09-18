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
