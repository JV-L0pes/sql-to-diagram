from dataclasses import dataclass
from enum import StrEnum


class RelationshipType(StrEnum):
    ONE_TO_ONE = "ONE_TO_ONE"
    ONE_TO_MANY = "ONE_TO_MANY"
    MANY_TO_ONE = "MANY_TO_ONE"
    MANY_TO_MANY = "MANY_TO_MANY"


class RelationshipSource(StrEnum):
    EXPLICIT = "explicit"
    INFERRED = "inferred"


@dataclass(frozen=True)
class Relationship:
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    type: RelationshipType
    source: RelationshipSource
    via_table: str | None = None
