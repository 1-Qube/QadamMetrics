"""QadamMetrics API."""

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api.routes import router
from app.core.access import set_owner_token
from app.core.config import get_settings, validate_runtime
from app.core.errors import AppError
from app.core.logging_config import configure_logging
from app.core.rate_limit import rate_limit_middleware
from app.database.session import check_db, init_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    configure_logging()
    settings = get_settings()
    validate_runtime(settings)
    init_db()
    if settings.seed_demo:
        from app.demo.seed import seed_public_demo

        seed_public_demo()
    logger.info("QadamMetrics started environment=%s ai_configured=%s", settings.environment, settings.ai_configured)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="QadamMetrics",
        version=__version__,
        description=(
            "Curriculum intelligence API. Diagnostics, knowledge-graph review, "
            "hypothetical hour optimization, textbook structure comparison, and "
            "association analysis. The API does not claim causal certainty. "
            "Synthetic datasets are labeled and are not real student evidence."
        ),
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.middleware("http")(rate_limit_middleware)

    @app.middleware("http")
    async def owner_context(request: Request, call_next):
        set_owner_token(request.headers.get("X-Owner-Token"))
        return await call_next(request)

    @app.middleware("http")
    async def api_key_guard(request: Request, call_next):
        if settings.api_key and request.url.path.startswith("/api"):
            provided = request.headers.get("X-API-Key")
            if provided != settings.api_key:
                return JSONResponse(status_code=401, content={"error": {"code": "unauthorized", "message": "Missing or invalid X-API-Key."}})
        return await call_next(request)

    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError):
        return JSONResponse(status_code=exc.status_code, content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}})

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_request: Request, exc: RequestValidationError):
        return JSONResponse(status_code=422, content={"error": {"code": "validation_error", "message": "Request validation failed.", "details": {"errors": exc.errors()}}})

    @app.exception_handler(Exception)
    async def unexpected_handler(_request: Request, exc: Exception):
        logger.exception("Unhandled error")
        return JSONResponse(status_code=500, content={"error": {"code": "internal_error", "message": "Unexpected server error."}})

    @app.get("/health")
    def health():
        db_ok = check_db()
        return {
            "status": "ok" if db_ok else "degraded",
            "version": __version__,
            "environment": settings.environment,
            "database": "up" if db_ok else "down",
            "database_dialect": "sqlite" if settings.is_sqlite else "postgresql" if "postgres" in settings.database_url else "other",
            "ai": {"configured": settings.ai_configured, "required": False},
        }

    app.include_router(router, prefix="/api")
    return app


app = create_app()
