from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from src.identity.application.project_use_cases import (
    CreateProject,
    DeleteProject,
    GetProject,
    ListProjects,
    UpdateProject,
)
from src.identity.domain.errors import ProjectNotFoundError
from src.identity.infrastructure.project_repository import ProjectRepository
from src.identity.interfaces.dependencies import get_current_user
from src.identity.interfaces.schemas import (
    ProjectCreateRequest,
    ProjectResponse,
    ProjectSummaryResponse,
    ProjectUpdateRequest,
)
from src.shared_kernel.db import get_db
from src.shared_kernel.errors import error_body

router = APIRouter(prefix="/api/projects", tags=["identity"])


@router.get("")
def list_projects(user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    projects = ListProjects(ProjectRepository(db)).execute(user_id)
    return [
        ProjectSummaryResponse(id=p.id, name=p.name, dialect=p.dialect, updated_at=p.updated_at)
        for p in projects
    ]


@router.post("", status_code=201)
def create_project(
    request: ProjectCreateRequest,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = CreateProject(ProjectRepository(db)).execute(
        user_id, request.name, request.sql, request.dialect
    )
    return _to_response(project)


@router.get("/{project_id}")
def get_project(
    project_id: str, user_id: str = Depends(get_current_user), db: Session = Depends(get_db)
):
    try:
        project = GetProject(ProjectRepository(db)).execute(project_id, user_id)
    except ProjectNotFoundError as exc:
        return JSONResponse(status_code=404, content=error_body("project_not_found", str(exc)))
    return _to_response(project)


@router.put("/{project_id}")
def update_project(
    project_id: str,
    request: ProjectUpdateRequest,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        project = UpdateProject(ProjectRepository(db)).execute(
            project_id, user_id, request.name, request.sql, request.dialect
        )
    except ProjectNotFoundError as exc:
        return JSONResponse(status_code=404, content=error_body("project_not_found", str(exc)))
    return _to_response(project)


@router.delete("/{project_id}", status_code=204)
def delete_project(
    project_id: str, user_id: str = Depends(get_current_user), db: Session = Depends(get_db)
):
    try:
        DeleteProject(ProjectRepository(db)).execute(project_id, user_id)
    except ProjectNotFoundError as exc:
        return JSONResponse(status_code=404, content=error_body("project_not_found", str(exc)))
    return Response(status_code=204)


def _to_response(project) -> ProjectResponse:
    return ProjectResponse(
        id=project.id,
        name=project.name,
        sql=project.sql,
        dialect=project.dialect,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )
