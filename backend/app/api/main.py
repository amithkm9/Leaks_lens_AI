"""Application assembly; endpoint logic lives in domain routers."""

import logging
from contextlib import asynccontextmanager

from app.api.errors import security_headers, validation_error, value_error
from app.api.middleware import RequestBodyLimitMiddleware
from app.api.routes import auth, incidents, remediation, scans, sources, system, workspace
from app.config import settings
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

logging.basicConfig(level=logging.INFO, format="%(message)s")
# Transport libraries must not log provider errors or sensitive request metadata.
for name in ("httpx", "httpcore", "anthropic", "mcp", "fastmcp", "presidio-analyzer"):
    logging.getLogger(name).setLevel(logging.CRITICAL)


@asynccontextmanager
async def lifespan(app):
    root = settings().data_dir.resolve()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    (root / "uploads").mkdir(exist_ok=True, mode=0o700)
    yield


app = FastAPI(title="LeakLens AI", version="0.1.0", lifespan=lifespan)
app.add_middleware(RequestBodyLimitMiddleware)
app.middleware("http")(security_headers)
app.add_exception_handler(RequestValidationError, validation_error)
app.add_exception_handler(ValueError, value_error)
for router in (
    system.router,
    auth.router,
    workspace.router,
    sources.router,
    scans.router,
    incidents.router,
    remediation.router,
):
    app.include_router(router)
