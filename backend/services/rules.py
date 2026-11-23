"""Default constraint rows shared by configuration setup and the engines."""

from sqlalchemy import select

RULE_DEFAULTS = {
    "Timetable": (
        *((f"H{index:02}", "Hard", 0, None) for index in range(1, 11)),
        ("S01", "Soft", 5, None), ("S02", "Soft", 5, None), ("S03", "Soft", 5, 5),
        ("S04", "Soft", 5, 3), ("S05", "Soft", 5, None), ("S06", "Soft", 5, None),
    ),
    "Exam": (
        ("E01", "Hard", 0, None), ("E02", "Hard", 0, 2), ("E03", "Hard", 0, None),
        ("E04", "Hard", 0, None), ("E05", "Hard", 0, None),
        ("ES01", "Soft", 5, None), ("ES02", "Soft", 5, None), ("ES03", "Soft", 5, None),
    ),
}
MANDATORY = frozenset({"H01", "H02", "H03", "H08", "E01", "E04", "E05"})


def seed_rules(connection, store, config_id, kind):
    table = store["constraint_rules"]
    connection.execute(table.insert(), [
        {"config_id": config_id, "rule_code": code, "rule_type": rule_type, "weight": weight, "param_value": param}
        for code, rule_type, weight, param in RULE_DEFAULTS[kind]
    ])


def default_config(connection, store, user_id, term_id, kind):
    table = store["scheduling_configs"]
    reference = connection.scalar(select(table.c.config_id).where(
        table.c.term_id == term_id, table.c.schedule_type == kind, table.c.name == "Default",
    ))
    if reference is None:
        reference = connection.scalar(table.insert().values(
            term_id=term_id, schedule_type=kind, name="Default", created_by=user_id,
        ).returning(table.c.config_id))
        seed_rules(connection, store, reference, kind)
    return reference

