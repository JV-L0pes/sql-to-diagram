from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.health.interfaces import router as health_router
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

    return app


app = create_app()
