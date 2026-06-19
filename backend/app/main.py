import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import router
from app.auth import bearer_token, verify_token
from app.config import get_settings
from app.db import Base, SessionLocal, engine
from app.seed_data import seed_if_empty
from app.trustsignal import validation_exception_handler_payload


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    app = FastAPI(
        title="Mock WhatsApp Provider",
        summary="TrustSignal-compatible WhatsApp mock server for recruitment workflow testing.",
        version="1.0.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    Path("storage/uploads").mkdir(parents=True, exist_ok=True)
    app.mount("/files", StaticFiles(directory="storage/uploads"), name="files")

    @app.middleware("http")
    async def admin_guard(request: Request, call_next):
        # Gate only the dashboard control surface. The TrustSignal /api/v1/* endpoints,
        # /health, /files, /auth/login, and CORS preflight stay open.
        if request.method != "OPTIONS" and request.url.path.startswith("/mock"):
            if not verify_token(bearer_token(request.headers.get("authorization"))):
                return JSONResponse(
                    status_code=401,
                    content={
                        "errors": [{"code": "401", "codeMsg": "UNAUTHORIZED", "message": "Admin login required"}],
                        "success": False,
                    },
                )
        return await call_next(request)

    app.include_router(router)

    @app.on_event("startup")
    def startup() -> None:
        Base.metadata.create_all(bind=engine)
        if settings.auto_seed:
            with SessionLocal() as db:
                seed_if_empty(db)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=validation_exception_handler_payload(exc))

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={
                "errors": [
                    {"code": "400", "codeMsg": "VALIDATION_ERROR", "message": exc.errors()[0].get("msg", "Invalid request")}
                ],
                "success": False,
            },
        )

    return app


app = create_app()
