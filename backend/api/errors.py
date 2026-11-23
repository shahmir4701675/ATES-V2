"""Public error shape shared by the API and form error summaries."""

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def problem(status, message, field=None, **details):
    return HTTPException(
        status,
        {"message": message, "fields": {field: message} if field else {}, **details},
        headers={"WWW-Authenticate": "Bearer"} if status == 401 else None,
    )


async def validation_response(request: Request, exc: RequestValidationError):
    fields = {}
    for error in exc.errors():
        field = ".".join(str(part) for part in error["loc"][1:]) or "form"
        fields[field] = error["msg"]
    return JSONResponse(
        status_code=422,
        content={"detail": {"message": "Check the highlighted fields and try again.", "fields": fields}},
    )

