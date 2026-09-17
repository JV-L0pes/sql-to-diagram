from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.health.interfaces import router as health_router
from src.shared_kernel.errors import error_body
from src.shared_kernel.settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="SQL to Diagram API")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)

    @app.exception_handler(Exception)
    async def handle_unhandled_exception(_request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=error_body("internal_error", str(exc)),
        )

    return app


app = create_app()
