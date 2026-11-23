"""Bound the multipart stream before it can spool an oversized upload."""

from fastapi import HTTPException
from fastapi.responses import JSONResponse

from backend.services.imports import MB_10

ENVELOPE_LIMIT = MB_10 + 64 * 1024
MESSAGE = "Choose a CSV file of 10 MB or less."


class UploadLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        if scope["type"] != "http" or scope["method"] != "POST" or not path.startswith("/import/"):
            await self.app(scope, receive, send)
            return
        length = dict(scope["headers"]).get(b"content-length", b"")
        if length.isdigit() and int(length) > ENVELOPE_LIMIT:
            response = JSONResponse({"detail": {"message": MESSAGE, "fields": {"file": MESSAGE}}}, status_code=413)
            await response(scope, receive, send)
            return

        read = 0

        async def limited_receive():
            nonlocal read
            message = await receive()
            read += len(message.get("body", b""))
            if read > ENVELOPE_LIMIT:
                raise HTTPException(413, {"message": MESSAGE, "fields": {"file": MESSAGE}})
            return message

        await self.app(scope, limited_receive, send)

