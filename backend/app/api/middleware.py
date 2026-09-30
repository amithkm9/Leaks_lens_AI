"""Bound request streams before multipart files can exhaust temporary storage."""

from starlette.formparsers import MultiPartException
from starlette.responses import JSONResponse
from app.config import settings


class RequestBodyTooLarge(MultiPartException):
    # Starlette closes multipart temporary files when this exception is raised.
    pass


class RequestBodyLimitMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        limit = 64 * 1024
        if scope["path"] == "/api/uploads":
            limit += settings().max_file_bytes
        lengths = [v for k, v in scope.get("headers", []) if k.lower() == b"content-length"]
        if lengths and (len(lengths) != 1 or len(lengths[0]) > 20 or not lengths[0].isdigit()):
            return await JSONResponse({"detail": "Invalid Content-Length"}, status_code=400)(
                scope, receive, send
            )
        rejected = JSONResponse({"detail": "Request body exceeds configured limit"}, status_code=413)
        if lengths and int(lengths[0]) > limit:
            return await rejected(scope, receive, send)

        size = 0
        exceeded = False
        replaced = False

        async def bounded_receive():
            nonlocal size, exceeded
            message = await receive()
            if message["type"] == "http.request":
                size += len(message.get("body", b""))
                if size > limit:
                    exceeded = True
                    raise RequestBodyTooLarge("Request body exceeds configured limit")
            return message

        async def bounded_send(message):
            nonlocal replaced
            if exceeded:
                if not replaced:
                    replaced = True
                    await rejected(scope, receive, send)
                return
            await send(message)

        try:
            await self.app(scope, bounded_receive, bounded_send)
        except RequestBodyTooLarge:
            if not replaced:
                await rejected(scope, receive, send)
