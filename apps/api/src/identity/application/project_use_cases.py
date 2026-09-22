import uuid

from src.identity.domain.errors import ProjectNotFoundError
from src.identity.domain.project import Project
from src.identity.infrastructure.project_repository import ProjectRepository


class CreateProject:
    def __init__(self, project_repository: ProjectRepository):
        self._project_repository = project_repository

    def execute(self, user_id: str, name: str, sql: str, dialect: str) -> Project:
        return self._project_repository.create(id=str(uuid.uuid4()), user_id=user_id, name=name, sql=sql, dialect=dialect)


class ListProjects:
    def __init__(self, project_repository: ProjectRepository):
        self._project_repository = project_repository

    def execute(self, user_id: str) -> list[Project]:
        return self._project_repository.list_by_user(user_id)


class GetProject:
    def __init__(self, project_repository: ProjectRepository):
        self._project_repository = project_repository

    def execute(self, project_id: str, user_id: str) -> Project:
        project = self._project_repository.get_by_id_and_user(project_id, user_id)
        if project is None:
            raise ProjectNotFoundError(project_id)
        return project


class UpdateProject:
    def __init__(self, project_repository: ProjectRepository):
        self._project_repository = project_repository

    def execute(self, project_id: str, user_id: str, name: str, sql: str, dialect: str) -> Project:
        project = self._project_repository.update(project_id, user_id, name=name, sql=sql, dialect=dialect)
        if project is None:
            raise ProjectNotFoundError(project_id)
        return project


class DeleteProject:
    def __init__(self, project_repository: ProjectRepository):
        self._project_repository = project_repository

    def execute(self, project_id: str, user_id: str) -> None:
        deleted = self._project_repository.delete(project_id, user_id)
        if not deleted:
            raise ProjectNotFoundError(project_id)
