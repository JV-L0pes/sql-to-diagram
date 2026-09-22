from sqlalchemy import DateTime

from src.identity.infrastructure.models import ProjectModel, RefreshTokenModel, UserModel


def test_identity_timestamp_columns_are_timezone_aware():
    for model in (UserModel, ProjectModel, RefreshTokenModel):
        for column in model.__table__.columns:
            if isinstance(column.type, DateTime):
                assert column.type.timezone is True, f"{model.__name__}.{column.name}"
