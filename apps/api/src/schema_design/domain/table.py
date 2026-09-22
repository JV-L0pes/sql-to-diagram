from dataclasses import dataclass, field


@dataclass(frozen=True)
class Column:
    name: str
    type: str
    nullable: bool
    primary_key: bool
    unique: bool = False


@dataclass
class Table:
    name: str
    columns: list[Column] = field(default_factory=list)
    unique_constraints: list[tuple[str, ...]] = field(default_factory=list)

    def find_column(self, name: str) -> Column | None:
        for column in self.columns:
            if column.name == name:
                return column
        return None
