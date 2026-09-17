from dataclasses import dataclass
from enum import Enum


class RelationshipType(str, Enum):
    ONE_TO_ONE = "ONE_TO_ONE"
    ONE_TO_MANY = "ONE_TO_MANY"
    MANY_TO_ONE = "MANY_TO_ONE"
    MANY_TO_MANY = "MANY_TO_MANY"


class RelationshipSource(str, Enum):
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
