from src.schema_design.domain.relationship import Relationship, RelationshipSource, RelationshipType


def test_relationship_source_values_match_api_contract():
    assert RelationshipSource.EXPLICIT.value == "explicit"
    assert RelationshipSource.INFERRED.value == "inferred"


def test_relationship_holds_all_fields():
    rel = Relationship(
        from_table="posts",
        from_column="user_id",
        to_table="users",
        to_column="id",
        type=RelationshipType.MANY_TO_ONE,
        source=RelationshipSource.EXPLICIT,
    )

    assert rel.from_table == "posts"
    assert rel.to_table == "users"
    assert rel.type == RelationshipType.MANY_TO_ONE
    assert rel.source == RelationshipSource.EXPLICIT
