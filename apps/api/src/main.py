import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.health.interfaces import router as health_router
from src.identity.interfaces.auth_router import router as auth_router
from src.identity.interfaces.projects_router import router as projects_router
from src.schema_design.interfaces.router import router as schema_design_router
from src.shared_kernel.errors import error_body
from src.shared_kernel.settings import get_settings

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Schemio API")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(schema_design_router)
    app.include_router(auth_router)
    app.include_router(projects_router)

    @app.exception_handler(Exception)
    async def handle_unhandled_exception(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled exception")
        return JSONResponse(
            status_code=500,
            content=error_body("internal_error", "Internal Server Error"),
        )

    return app


app = create_app()
