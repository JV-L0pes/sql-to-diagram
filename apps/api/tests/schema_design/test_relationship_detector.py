from src.schema_design.domain.relationship import Relationship, RelationshipSource, RelationshipType
from src.schema_design.domain.table import Column, Table
from src.schema_design.infrastructure.relationship_detector import (
    detect_explicit_relationships,
    detect_inferred_relationships,
)


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
            Column("user_id", "INTEGER", False, False, True),  # UNIQUE on this table -> 1:1
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
    assert all(r.via_table == "enrollments" for r in many_to_many)
    # The junction table itself should not appear as a plain FK relationship
    assert all(r.from_table != "enrollments" for r in relationships)


def test_infers_relationship_from_naming_convention_when_no_explicit_fk():
    users = _table("users", [Column("id", "INTEGER", False, True)])
    posts = _table(
        "posts",
        [
            Column("id", "INTEGER", False, True),
            Column("user_id", "INTEGER", False, False),
        ],
    )

    relationships = detect_inferred_relationships(
        [users, posts], explicit_relationships=[], foreign_keys=[]
    )

    assert len(relationships) == 1
    rel = relationships[0]
    assert rel.from_table == "posts"
    assert rel.from_column == "user_id"
    assert rel.to_table == "users"
    assert rel.to_column == "id"
    assert rel.source == RelationshipSource.INFERRED


def test_does_not_infer_when_explicit_relationship_already_covers_the_column():
    users = _table("users", [Column("id", "INTEGER", False, True)])
    posts = _table(
        "posts",
        [
            Column("id", "INTEGER", False, True),
            Column("user_id", "INTEGER", False, False),
        ],
    )
    explicit = [
        Relationship(
            "posts",
            "user_id",
            "users",
            "id",
            RelationshipType.MANY_TO_ONE,
            RelationshipSource.EXPLICIT,
        )
    ]

    foreign_keys = [("posts", "user_id", "users", "id")]

    relationships = detect_inferred_relationships(
        [users, posts], explicit_relationships=explicit, foreign_keys=foreign_keys
    )

    assert relationships == []


def test_does_not_infer_when_no_matching_table_exists():
    posts = _table(
        "posts",
        [
            Column("id", "INTEGER", False, True),
            Column("category_id", "INTEGER", False, False),
        ],
    )

    relationships = detect_inferred_relationships(
        [posts], explicit_relationships=[], foreign_keys=[]
    )

    assert relationships == []


def test_does_not_infer_spurious_relationship_for_junction_table_fk_columns():
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

    explicit_relationships = detect_explicit_relationships(
        [students, courses, enrollments], foreign_keys
    )
    inferred_relationships = detect_inferred_relationships(
        [students, courses, enrollments],
        explicit_relationships=explicit_relationships,
        foreign_keys=foreign_keys,
    )

    assert inferred_relationships == []


def test_does_not_infer_when_target_id_column_type_is_incompatible():
    tenants = _table("tenants", [Column("id", "INTEGER", False, True)])
    accounts = _table(
        "accounts",
        [
            Column("id", "INTEGER", False, True),
            Column("tenant_id", "VARCHAR(36)", False, False),
        ],
    )

    relationships = detect_inferred_relationships(
        [tenants, accounts], explicit_relationships=[], foreign_keys=[]
    )

    assert relationships == []


def test_infers_when_target_id_column_type_is_compatible_integer_family():
    tenants = _table("tenants", [Column("id", "BIGINT", False, True)])
    accounts = _table(
        "accounts",
        [
            Column("id", "INTEGER", False, True),
            Column("tenant_id", "INTEGER", False, False),
        ],
    )

    relationships = detect_inferred_relationships(
        [tenants, accounts], explicit_relationships=[], foreign_keys=[]
    )

    assert len(relationships) == 1
    assert relationships[0].from_table == "accounts"
    assert relationships[0].to_table == "tenants"


def test_composite_pk_member_is_not_treated_as_individually_unique():
    orders = _table("orders", [Column("id", "INTEGER", False, True)])
    tickets = _table(
        "tickets",
        [
            Column("order_id", "INTEGER", False, True),
            Column("seq", "INTEGER", False, True),
            Column("id", "INTEGER", False, False),
        ],
    )
    # order_id may be any of many tickets per order: must stay MANY_TO_ONE
    foreign_keys = [("tickets", "order_id", "orders", "id")]

    relationships = detect_explicit_relationships([orders, tickets], foreign_keys)

    assert relationships[0].type == RelationshipType.MANY_TO_ONE


def test_explicit_unique_flag_makes_relationship_one_to_one():
    users = _table("users", [Column("id", "INTEGER", False, True)])
    profiles = _table(
        "profiles",
        [
            Column("id", "INTEGER", False, True),
            Column("user_id", "INTEGER", False, False, True),  # UNIQUE
        ],
    )
    foreign_keys = [("profiles", "user_id", "users", "id")]

    relationships = detect_explicit_relationships([users, profiles], foreign_keys)

    assert relationships[0].type == RelationshipType.ONE_TO_ONE


def test_two_fks_to_the_same_table_are_not_collapsed_into_many_to_many():
    users = _table("users", [Column("id", "INTEGER", False, True)])
    friendships = _table(
        "friendships",
        [
            Column("user_a_id", "INTEGER", False, False),
            Column("user_b_id", "INTEGER", False, False),
        ],
    )
    foreign_keys = [
        ("friendships", "user_a_id", "users", "id"),
        ("friendships", "user_b_id", "users", "id"),
    ]

    relationships = detect_explicit_relationships([users, friendships], foreign_keys)

    assert all(r.type != RelationshipType.MANY_TO_MANY for r in relationships)
    assert len(relationships) == 2


def test_surrogate_pk_junction_with_composite_unique_collapses_to_many_to_many():
    students = _table("students", [Column("id", "INTEGER", False, True)])
    courses = _table("courses", [Column("id", "INTEGER", False, True)])
    enrollments = Table(
        name="enrollments",
        columns=[
            Column("id", "INTEGER", False, True),
            Column("student_id", "INTEGER", False, False),
            Column("course_id", "INTEGER", False, False),
        ],
        unique_constraints=[("student_id", "course_id")],
    )
    foreign_keys = [
        ("enrollments", "student_id", "students", "id"),
        ("enrollments", "course_id", "courses", "id"),
    ]

    relationships = detect_explicit_relationships([students, courses, enrollments], foreign_keys)

    many_to_many = [r for r in relationships if r.type == RelationshipType.MANY_TO_MANY]
    assert {(r.from_table, r.to_table) for r in many_to_many} == {
        ("students", "courses"),
        ("courses", "students"),
    }
    assert all(r.via_table == "enrollments" for r in many_to_many)


def test_infers_to_single_column_primary_key_not_named_id():
    parents = _table("parents", [Column("uuid", "TEXT", False, True)])
    children = _table(
        "children",
        [
            Column("id", "INTEGER", False, True),
            Column("parent_id", "TEXT", False, False),
        ],
    )

    relationships = detect_inferred_relationships([parents, children], [], [])

    assert len(relationships) == 1
    assert relationships[0].to_table == "parents"
    assert relationships[0].to_column == "uuid"


def test_does_not_infer_when_target_id_column_is_not_a_key():
    categories = _table("categories", [Column("id", "INTEGER", False, False)])
    posts = _table(
        "posts",
        [
            Column("id", "INTEGER", False, True),
            Column("category_id", "INTEGER", False, False),
        ],
    )

    assert detect_inferred_relationships([categories, posts], [], []) == []


def test_does_not_infer_when_multiple_tables_match_the_prefix():
    users = _table("users", [Column("id", "INTEGER", False, True)])
    usera = _table("usera", [Column("id", "INTEGER", False, True)])
    posts = _table(
        "posts",
        [
            Column("id", "INTEGER", False, True),
            Column("user_id", "INTEGER", False, False),
        ],
    )

    assert detect_inferred_relationships([users, usera, posts], [], []) == []


def test_infers_when_types_differ_only_by_unsigned_modifier():
    users = _table("users", [Column("id", "INT", False, True)])
    posts = _table(
        "posts",
        [
            Column("id", "INT", False, True),
            Column("user_id", "INT UNSIGNED", False, False),
        ],
    )

    relationships = detect_inferred_relationships([users, posts], [], [])

    assert len(relationships) == 1


def test_inference_matches_schema_qualified_tables_by_last_segment():
    users = _table("public.users", [Column("id", "INT", False, True)])
    posts = _table(
        "posts",
        [
            Column("id", "INT", False, True),
            Column("user_id", "INT", False, False),
        ],
    )

    relationships = detect_inferred_relationships([users, posts], [], [])

    assert len(relationships) == 1
    assert relationships[0].to_table == "public.users"


def test_inference_is_skipped_when_multiple_schemas_share_the_table_name():
    public_users = _table("public.users", [Column("id", "INT", False, True)])
    auth_users = _table("auth.users", [Column("id", "INT", False, True)])
    posts = _table(
        "posts",
        [
            Column("id", "INT", False, True),
            Column("user_id", "INT", False, False),
        ],
    )

    assert detect_inferred_relationships([public_users, auth_users, posts], [], []) == []
