"""Coordinator-only CSV templates, previews and commit actions."""

from pathlib import PurePosixPath
from typing import Annotated, Literal
from uuid import UUID

from fastapi import File, Form, Request, Response, UploadFile

from backend.api.errors import problem
from backend.api.master import require_role
from backend.services import imports
from backend.services.csv_output import csv_text

Entity = Literal["courses", "instructors", "rooms", "batches", "offerings", "enrollments"]


def register_imports(app, Current):
    @app.get("/import/templates/{entity}", tags=["CSV import"])
    def template(context: Current, entity: Entity):
        require_role(context[1], "Coordinator")
        sample = imports.CsvTypes[entity][1]
        return Response(csv_text([sample.keys(), sample.values()]), media_type="text/csv", headers={
            "Content-Disposition": f'attachment; filename="{entity}.csv"',
        })

    @app.post("/import/{entity}", tags=["CSV import"])
    def preview(request: Request, context: Current, entity: Entity,
                request_token: Annotated[UUID, Form()], file: Annotated[UploadFile, File()]):
        require_role(context[1], "Coordinator")
        filename = PurePosixPath((file.filename or "").replace("\\", "/")).name
        if not filename.lower().endswith(".csv") or len(filename) > 120:
            raise problem(422, "Choose a .csv file with a name of at most 120 characters.", "file")
        source = file.file.read(imports.MB_10 + 1)
        if len(source) > imports.MB_10:
            raise problem(413, "Choose a CSV file of 10 MB or less.", "file")
        return imports.preview(context[0], request.app.state.store, context[1]["user_id"],
                               str(request_token), entity, filename, source)

    @app.post("/import/previews/{key}/{action}", tags=["CSV import"])
    def finish(request: Request, context: Current, key: UUID, action: Literal["confirm", "cancel"]):
        require_role(context[1], "Coordinator")
        return imports.apply(context[0], request.app.state.store, context[1]["user_id"], str(key), action == "confirm")

