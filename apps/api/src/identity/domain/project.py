from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Project:
    id: str
    user_id: str
    name: str
    sql: str
    dialect: str
    created_at: datetime
    updated_at: datetime
