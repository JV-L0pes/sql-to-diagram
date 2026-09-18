from src.schema_design.domain.relationship import RelationshipSource, RelationshipType
from src.schema_design.domain.table import Column, Table
from src.schema_design.infrastructure.relationship_detector import detect_explicit_relationships


def _table(name, columns):
    return Table(name=name, columns=columns)


def test_detects_many_to_one_for_simple_foreign_key():
    users = _table("users", [Column("id", "INTEGER", False, True)])
    posts = _table(
        "posts",
        [
            Column("id", "INTEGER", False, True),
            Column("user_id", "INTEGER", False, False),
        ],
    )
    foreign_keys = [("posts", "user_id", "users", "id")]

    relationships = detect_explicit_relationships([users, posts], foreign_keys)

    assert len(relationships) == 1
    rel = relationships[0]
    assert rel.from_table == "posts"
    assert rel.to_table == "users"
    assert rel.type == RelationshipType.MANY_TO_ONE
    assert rel.source == RelationshipSource.EXPLICIT


def test_detects_one_to_one_when_both_sides_unique():
    users = _table("users", [Column("id", "INTEGER", False, True)])
    profiles = _table(
        "profiles",
        [
            Column("id", "INTEGER", False, True),
            Column("user_id", "INTEGER", False, True),  # PK on this table too -> unique
        ],
    )
    foreign_keys = [("profiles", "user_id", "users", "id")]

    relationships = detect_explicit_relationships([users, profiles], foreign_keys)

    assert relationships[0].type == RelationshipType.ONE_TO_ONE


def test_collapses_junction_table_into_many_to_many():
    students = _table("students", [Column("id", "INTEGER", False, True)])
    courses = _table("courses", [Column("id", "INTEGER", False, True)])
    enrollments = _table(
        "enrollments",
        [
            Column("student_id", "INTEGER", False, True),
            Column("course_id", "INTEGER", False, True),
        ],
    )
    foreign_keys = [
        ("enrollments", "student_id", "students", "id"),
        ("enrollments", "course_id", "courses", "id"),
    ]

    relationships = detect_explicit_relationships([students, courses, enrollments], foreign_keys)

    many_to_many = [r for r in relationships if r.type == RelationshipType.MANY_TO_MANY]
    assert len(many_to_many) == 2  # both directions
    pairs = {(r.from_table, r.to_table) for r in many_to_many}
    assert pairs == {("students", "courses"), ("courses", "students")}
    # The junction table itself should not appear as a plain FK relationship
    assert all(r.from_table != "enrollments" for r in relationships)
