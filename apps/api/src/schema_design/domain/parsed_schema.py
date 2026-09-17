from dataclasses import dataclass, field

from src.schema_design.domain.relationship import Relationship
from src.schema_design.domain.table import Table
from src.schema_design.domain.warning import SchemaWarning


@dataclass
class ParsedSchema:
    tables: list[Table] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)
    warnings: list[SchemaWarning] = field(default_factory=list)
