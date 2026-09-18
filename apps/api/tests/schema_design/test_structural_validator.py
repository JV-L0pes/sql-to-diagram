from src.schema_design.domain.relationship import Relationship, RelationshipSource, RelationshipType
from src.schema_design.domain.table import Column, Table
from src.schema_design.domain.warning import WarningCode
from src.schema_design.infrastructure.structural_validator import validate_structure


def test_warns_on_missing_primary_key():
    logs = Table(name="logs", columns=[Column("message", "TEXT", True, False)])

    warnings = validate_structure([logs], [])

    codes = [w.code for w in warnings]
    assert WarningCode.MISSING_PRIMARY_KEY in codes


def test_no_warning_when_primary_key_present():
    users = Table(name="users", columns=[Column("id", "INTEGER", False, True)])

    warnings = validate_structure([users], [])

    assert all(w.code != WarningCode.MISSING_PRIMARY_KEY for w in warnings)


def test_warns_on_non_atomic_column_type():
    tags_table = Table(
        name="posts",
        columns=[
            Column("id", "INTEGER", False, True),
            Column("tags", "TEXT[]", True, False),
        ],
    )

    warnings = validate_structure([tags_table], [])

    codes = [w.code for w in warnings]
    assert WarningCode.NON_ATOMIC_COLUMN_TYPE in codes


def test_warns_on_nullable_foreign_key():
    users = Table(name="users", columns=[Column("id", "INTEGER", False, True)])
    posts = Table(
        name="posts",
        columns=[
            Column("id", "INTEGER", False, True),
            Column("user_id", "INTEGER", True, False),  # nullable FK
        ],
    )
    relationships = [
        Relationship("posts", "user_id", "users", "id", RelationshipType.MANY_TO_ONE, RelationshipSource.EXPLICIT)
    ]

    warnings = validate_structure([users, posts], relationships)

    codes = [w.code for w in warnings]
    assert WarningCode.NULLABLE_FOREIGN_KEY in codes


def test_warns_on_non_snake_case_identifier():
    weird = Table(name="UserAccounts", columns=[Column("id", "INTEGER", False, True)])

    warnings = validate_structure([weird], [])

    codes = [w.code for w in warnings]
    assert WarningCode.NON_SNAKE_CASE_IDENTIFIER in codes
