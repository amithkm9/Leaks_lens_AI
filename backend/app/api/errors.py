"""Consistent safe API errors, origin checks, and response headers."""

from app.config import settings
from app.detectors import safe_text
from fastapi.responses import JSONResponse


async def security_headers(request, call_next):
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        if origin and origin.rstrip("/") != settings().allowed_origin.rstrip("/"):
            return JSONResponse({"detail": "Origin is not allowed"}, status_code=403)
    response = await call_next(request)
    response.headers.update(
        {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "no-referrer",
            "Cache-Control": "no-store",
        }
    )
    return response


async def validation_error(request, exc):
    # Pydantic's default error includes the rejected input; never echo submitted secrets.
    return JSONResponse(
        {
            "detail": safe_text(
                "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['type']}" for e in exc.errors())
            )
        },
        status_code=422,
    )


async def value_error(request, exc):
    return JSONResponse({"detail": safe_text(str(exc))}, status_code=400)
