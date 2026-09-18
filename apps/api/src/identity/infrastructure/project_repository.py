from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.identity.domain.project import Project
from src.identity.infrastructure.models import ProjectModel


class ProjectRepository:
    def __init__(self, session: Session):
        self._session = session

    def create(self, id: str, user_id: str, name: str, sql: str, dialect: str) -> Project:
        model = ProjectModel(id=id, user_id=user_id, name=name, sql=sql, dialect=dialect)
        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)
        return self._to_domain(model)

    def list_by_user(self, user_id: str) -> list[Project]:
        models = self._session.query(ProjectModel).filter_by(user_id=user_id).order_by(ProjectModel.created_at).all()
        return [self._to_domain(m) for m in models]

    def get_by_id_and_user(self, project_id: str, user_id: str) -> Project | None:
        model = self._find(project_id, user_id)
        return self._to_domain(model) if model else None

    def update(self, project_id: str, user_id: str, name: str, sql: str, dialect: str) -> Project | None:
        model = self._find(project_id, user_id)
        if model is None:
            return None
        model.name = name
        model.sql = sql
        model.dialect = dialect
        model.updated_at = datetime.now(timezone.utc)
        self._session.commit()
        self._session.refresh(model)
        return self._to_domain(model)

    def delete(self, project_id: str, user_id: str) -> bool:
        model = self._find(project_id, user_id)
        if model is None:
            return False
        self._session.delete(model)
        self._session.commit()
        return True

    def _find(self, project_id: str, user_id: str) -> ProjectModel | None:
        return self._session.query(ProjectModel).filter_by(id=project_id, user_id=user_id).first()

    @staticmethod
    def _to_domain(model: ProjectModel) -> Project:
        return Project(
            id=model.id,
            user_id=model.user_id,
            name=model.name,
            sql=model.sql,
            dialect=model.dialect,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
