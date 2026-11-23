"""Named configurations, rule switches and dated exam sessions."""

from datetime import date, time
from typing import Annotated, Literal

from fastapi import Query, Request, Response
from pydantic import Field, StringConstraints, model_validator
from sqlalchemy import select

from backend.api.errors import problem
from backend.api.master import require_role
from backend.api.schemas import AccountId, Input
from backend.services import master
from backend.services.accounts import insert
from backend.services.rules import MANDATORY, RULE_DEFAULTS, seed_rules
from backend.services.security import audit

Kind = Literal["Timetable", "Exam"]


class ConfigValues(Input):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
    solver_time_limit_s: Annotated[int, Field(ge=10, le=600)] = 120
    random_seed: Annotated[int, Field(ge=0, le=2147483647)] = 1
    lab_block_slots: Annotated[int, Field(ge=1, le=48)] | None = None


class NewConfig(ConfigValues):
    term_id: AccountId
    schedule_type: Kind
    clone_id: AccountId | None = None


class RuleEdit(Input):
    rule_code: str
    is_enabled: bool
    weight: Annotated[int, Field(ge=0, le=10)]
    param_value: Annotated[int, Field(ge=1, le=32767)] | None = None


class RuleUpdates(Input):
    rules: Annotated[list[RuleEdit], Field(min_length=1, max_length=24)]
    confirmed_disable: bool = False


class ExamSlot(Input):
    exam_date: date
    start_time: time
    end_time: time
    label: Annotated[str, StringConstraints(strip_whitespace=True, max_length=30)] = ""

    @model_validator(mode="after")
    def check_window(self):
        if any(value.second or value.microsecond or value.tzinfo for value in (self.start_time, self.end_time)):
            raise ValueError("Enter the start and end times in hours and minutes.")
        if self.end_time <= self.start_time:
            raise ValueError("End time must be after start time.")
        return self


def register_settings(app, Current):
    def permissions(request, context, *, write=True):
        connection, user, _ = context
        require_role(user, "Coordinator", *(() if write else ("Approver",)))
        if write:
            master.serialize_term_change(connection)
        return connection, request.app.state.store, user["user_id"]

    def config_for_write(connection, store, key):
        row = master.by_id(connection, store["scheduling_configs"], key, lock=True)
        master.ensure_editable(master.by_id(connection, store["academic_terms"], row["term_id"], lock=True))
        return row

    def check_name(connection, table, term_id, kind, name, own=None):
        query = select(table.c.config_id).where(
            table.c.term_id == term_id, table.c.schedule_type == kind, table.c.name == name,
        )
        if own is not None:
            query = query.where(table.c.config_id != own)
        if connection.scalar(query):
            raise problem(409, "This configuration name already exists for the term and type.", "name")

    @app.get("/configs", tags=["Configuration"])
    def configs(request: Request, context: Current, term_id: Annotated[int, Query(ge=1, le=2147483647)],
                schedule_type: Kind | None = None):
        connection, store, _ = permissions(request, context, write=False)
        table = store["scheduling_configs"]
        query = select(table).where(table.c.term_id == term_id)
        if schedule_type:
            query = query.where(table.c.schedule_type == schedule_type)
        return connection.execute(query.order_by((table.c.name != "Default"), table.c.name)).mappings().all()

    @app.post("/configs", status_code=201, tags=["Configuration"])
    def add_config(request: Request, context: Current, form: NewConfig):
        connection, store, actor = permissions(request, context)
        table = store["scheduling_configs"]
        master.ensure_editable(master.by_id(connection, store["academic_terms"], form.term_id, "term_id", lock=True))
        check_name(connection, table, form.term_id, form.schedule_type, form.name)
        values = form.model_dump(exclude={"clone_id"})
        source = None
        if form.clone_id:
            source = master.by_id(connection, table, form.clone_id, "clone_id")
            if source["schedule_type"] != form.schedule_type:
                raise problem(422, "Choose a configuration of the same schedule type.", "clone_id")
            values.update(solver_time_limit_s=source["solver_time_limit_s"], random_seed=source["random_seed"],
                          lab_block_slots=source["lab_block_slots"])
        if form.schedule_type == "Exam" and values["lab_block_slots"] is not None:
            raise problem(422, "Lab blocks are only available in timetable configurations.", "lab_block_slots")
        row = insert(connection, table, {**values, "created_by": actor})
        key = row["config_id"]
        if source:
            rules = store["constraint_rules"]
            selected = rules.c.rule_code, rules.c.rule_type, rules.c.is_enabled, rules.c.weight, rules.c.param_value
            copied = connection.execute(select(*selected).where(rules.c.config_id == form.clone_id)).mappings().all()
            if copied:
                connection.execute(rules.insert(), [{**rule, "config_id": key} for rule in copied])
            else:
                seed_rules(connection, store, key, form.schedule_type)
        else:
            seed_rules(connection, store, key, form.schedule_type)
        audit(connection, store, actor, "config_cloned" if source else "config_created", "Config", key)
        return row

    @app.put("/configs/{config_id}", tags=["Configuration"])
    def edit_config(request: Request, context: Current, config_id: int, form: ConfigValues):
        connection, store, actor = permissions(request, context)
        row = config_for_write(connection, store, config_id)
        if row["schedule_type"] == "Exam" and form.lab_block_slots is not None:
            raise problem(422, "Lab blocks are only available in timetable configurations.", "lab_block_slots")
        if row["name"] == "Default" and form.name != "Default":
            raise problem(422, "Keep this configuration named Default.", "name")
        table = store["scheduling_configs"]
        check_name(connection, table, row["term_id"], row["schedule_type"], form.name, config_id)
        connection.execute(table.update().where(table.c.config_id == config_id).values(**form.model_dump()))
        audit(connection, store, actor, "config_updated", "Config", config_id)
        return dict(row, **form.model_dump())

    @app.delete("/configs/{config_id}", status_code=204, tags=["Configuration"])
    def delete_config(request: Request, context: Current, config_id: int):
        connection, store, actor = permissions(request, context)
        row = config_for_write(connection, store, config_id)
        schedules = store["schedules"]
        if row["name"] == "Default" or connection.scalar(select(schedules.c.schedule_id).where(
            schedules.c.config_id == config_id,
        ).limit(1)):
            raise problem(409, "Keep the default and configurations used by saved versions.")
        table = store["scheduling_configs"]
        connection.execute(table.delete().where(table.c.config_id == config_id))
        audit(connection, store, actor, "config_deleted", "Config", config_id)
        return Response(status_code=204)

    @app.get("/configs/{config_id}/rules", tags=["Configuration"])
    def config_rules(request: Request, context: Current, config_id: int):
        connection, store, _ = permissions(request, context, write=False)
        master.by_id(connection, store["scheduling_configs"], config_id)
        table = store["constraint_rules"]
        return connection.execute(select(table).where(table.c.config_id == config_id)
                                  .order_by(table.c.rule_type, table.c.rule_code)).mappings().all()

    @app.put("/configs/{config_id}/rules", tags=["Configuration"])
    def update_rules(request: Request, context: Current, config_id: int, form: RuleUpdates):
        connection, store, actor = permissions(request, context)
        config = config_for_write(connection, store, config_id)
        table = store["constraint_rules"]
        existing = {row["rule_code"]: row for row in connection.execute(select(table).where(
            table.c.config_id == config_id,
        )).mappings()}
        input_codes = {entry.rule_code for entry in form.rules}
        expected = {code: param for code, _, _, param in RULE_DEFAULTS[config["schedule_type"]]}
        if len(input_codes) != len(form.rules) or input_codes - existing.keys():
            raise problem(422, "Select distinct rules from this configuration.", "rules")
        disabling = []
        for entry in form.rules:
            code = entry.rule_code
            prior = existing[code]
            if not entry.is_enabled and code in MANDATORY:
                raise problem(422, f"{code} is mandatory and must stay enabled.", "rules")
            if (expected.get(code) is None) != (entry.param_value is None):
                raise problem(422, f"Use a parameter only when defined for {code}.", "rules")
            if prior["rule_type"] == "Hard":
                if entry.weight != 0:
                    raise problem(422, "Weights apply to soft rules.", "rules")
                if prior["is_enabled"] and not entry.is_enabled:
                    disabling.append(code)
        if disabling and not form.confirmed_disable:
            raise problem(409, f"Confirm that these rules may be violated in future runs: {', '.join(disabling)}.")
        for entry in form.rules:
            connection.execute(table.update().where(table.c.rule_id == existing[entry.rule_code]["rule_id"])
                               .values(**entry.model_dump(exclude={"rule_code"})))
        audit(connection, store, actor, "rules_updated", "Config", config_id,
              details="Disabled " + ", ".join(disabling) if disabling else None)
        return {"updated": len(form.rules)}

    @app.get("/terms/{term_id}/exam-slots", tags=["Exam sessions"])
    def exam_slots(request: Request, context: Current, term_id: int):
        connection, store, _ = permissions(request, context, write=False)
        master.by_id(connection, store["academic_terms"], term_id)
        table = store["exam_slots"]
        return connection.execute(select(table).where(table.c.term_id == term_id).order_by(
            table.c.exam_date, table.c.start_time,
        )).mappings().all()

    def save_exam_slot(request, context, term_id, form, slot_id=None):
        connection, store, actor = permissions(request, context)
        term = master.by_id(connection, store["academic_terms"], term_id, "term_id", lock=True)
        master.ensure_editable(term)
        table = store["exam_slots"]
        if slot_id:
            original = master.by_id(connection, table, slot_id, lock=True)
            if original["term_id"] != term_id:
                raise problem(404, "This exam session is outside the selected term.")
        if not term["start_date"] <= form.exam_date <= term["end_date"]:
            raise problem(422, "Choose a date inside the academic term.", "exam_date")
        overlap = select(table.c.exam_slot_id).where(
            table.c.term_id == term_id, table.c.exam_date == form.exam_date,
            table.c.start_time < form.end_time, table.c.end_time > form.start_time,
        )
        if slot_id:
            overlap = overlap.where(table.c.exam_slot_id != slot_id)
        if connection.scalar(overlap):
            raise problem(409, "This exam session overlaps an existing session.", "start_time")
        data = form.model_dump()
        if slot_id:
            row = connection.execute(table.update().where(table.c.exam_slot_id == slot_id)
                                     .values(**data).returning(*table.c)).mappings().one()
        else:
            row = insert(connection, table, {**data, "term_id": term_id})
        audit(connection, store, actor, "exam_slot_saved", "Exam session", row["exam_slot_id"])
        return row

    @app.post("/terms/{term_id}/exam-slots", status_code=201, tags=["Exam sessions"])
    def add_exam_slot(request: Request, context: Current, term_id: int, form: ExamSlot):
        return save_exam_slot(request, context, term_id, form)

    @app.put("/terms/{term_id}/exam-slots/{slot_id}", tags=["Exam sessions"])
    def edit_exam_slot(request: Request, context: Current, term_id: int, slot_id: int, form: ExamSlot):
        return save_exam_slot(request, context, term_id, form, slot_id)

