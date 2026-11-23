"""Account administration with atomic creation of required linked records."""

from sqlalchemy import func, or_, select

from backend.api.errors import problem
from backend.services.security import audit, password_hash, public_user, revoke


def search_accounts(connection, store, search, page):
    users = store["users"]
    query = select(users)
    if search:
        query = query.where(or_(*(
            column.icontains(search, autoescape=True)
            for column in (users.c.username, users.c.full_name, users.c.email, users.c.role)
        )))
    total = connection.scalar(select(func.count()).select_from(query.subquery()))
    rows = connection.execute(query.order_by(users.c.username, users.c.user_id).offset((page - 1) * 25).limit(25))
    return {"items": [public_user(row) for row in rows.mappings()], "total": total, "page": page}


def insert(connection, table, values):
    return connection.execute(table.insert().values(**values).returning(*table.c)).mappings().one()


def existing(connection, table, key, field):
    row = connection.execute(select(table).where(next(iter(table.primary_key)) == key)).mappings().first()
    if not row:
        raise problem(422, "Select an existing record.", field)
    return row


def find_account(connection, store, user_id):
    users = store["users"]
    row = connection.execute(select(users).where(users.c.user_id == user_id).with_for_update()).mappings().first()
    if not row:
        raise problem(404, "This account could not be found.")
    return row


def account_links(connection, store, form):
    links = {"instructor_id": None, "batch_id": None}
    for role, entity, table_name in (("Faculty", "instructor", "instructors"), ("Student", "batch", "batches")):
        field = f"{entity}_id"
        key = getattr(form, field)
        record = getattr(form, entity)
        if form.role != role:
            if key or record:
                raise problem(422, f"Only {role} accounts can have this link.", field)
            continue
        if bool(key) == bool(record):
            raise problem(422, f"Select an existing {entity} or create one.", field)
        table = store[table_name]
        if record:
            if bool(record.department_id) == bool(record.department):
                raise problem(422, "Select an existing department or create one.", f"{entity}.department_id")
            department_id = record.department_id
            departments = store["departments"]
            if record.department:
                code = record.department.code
                if connection.scalar(select(departments.c.department_id).where(departments.c.code == code)):
                    raise problem(409, "This department code already exists.", f"{entity}.department.code")
                department_id = insert(connection, departments, record.department.model_dump())["department_id"]
            else:
                existing(connection, departments, department_id, f"{entity}.department_id")
            values = record.model_dump(exclude={"department", "department_id"})
            if entity == "instructor" and connection.scalar(select(table.c.instructor_id).where(table.c.email == values["email"])):
                raise problem(409, "This instructor email already exists.", "instructor.email")
            if entity == "batch" and connection.scalar(select(table.c.batch_id).where(
                table.c.program_code == values["program_code"], table.c.batch_year == values["batch_year"],
                table.c.section == values["section"],
            )):
                raise problem(409, "This programme, year and section already exist.", "batch.section")
            key = insert(connection, table, {**values, "department_id": department_id})[field]
        elif not existing(connection, table, key, field)["is_active"]:
            raise problem(422, f"Select an active {entity}.", field)
        links[field] = key
    return links


def save_account(connection, store, actor, form, user_id=None):
    users = store["users"]
    if user_id is not None:
        original = find_account(connection, store, user_id)
        if user_id == actor and form.role != original["role"]:
            raise problem(422, "Another Administrator must change your role.", "role")

    for field in ("username", "email"):
        query = select(users.c.user_id).where(users.c[field] == getattr(form, field))
        if user_id is not None:
            query = query.where(users.c.user_id != user_id)
        if connection.scalar(query):
            raise problem(409, f"This {field} already exists.", field)

    links = account_links(connection, store, form)
    if links["instructor_id"]:
        query = select(users.c.user_id).where(users.c.instructor_id == links["instructor_id"])
        if user_id is not None:
            query = query.where(users.c.user_id != user_id)
        if connection.scalar(query):
            raise problem(409, "This instructor already has an account.", "instructor_id")

    values = form.model_dump(include={"username", "full_name", "email", "role"})
    values.update(links)
    if user_id is None:
        values["password_hash"] = password_hash(form.password)
        row = insert(connection, users, values)
        user_id = row["user_id"]
        audit(connection, store, actor, "account_created", entity_id=user_id, details=row["role"])
    else:
        row = connection.execute(
            users.update().where(users.c.user_id == user_id).values(**values).returning(*users.c)
        ).mappings().one()
        if any(original[field] != row[field] for field in ("username", "role", "instructor_id", "batch_id")):
            revoke(connection, store, user_id)
        audit(connection, store, actor, "account_updated", entity_id=user_id,
              details=f"{original['role']} → {row['role']}")
    return public_user(row)


def set_status(connection, store, actor, user_id, active):
    old = find_account(connection, store, user_id)
    status = "Active" if active else "Deactivated"
    if actor == user_id:
        raise problem(422, "Another Administrator must change your account status.")
    if old["account_status"] != status:
        users = store["users"]
        connection.execute(users.update().where(users.c.user_id == user_id).values(
            account_status=status, locked_until=None, failed_attempts=0,
        ))
        revoke(connection, store, user_id)
        audit(connection, store, actor, "account_reactivated" if active else "account_deactivated", entity_id=user_id)


def set_password(connection, store, actor, user_id, password, action):
    users = store["users"]
    connection.execute(users.update().where(users.c.user_id == user_id).values(password_hash=password_hash(password)))
    revoke(connection, store, user_id)
    audit(connection, store, actor, action, entity_id=user_id)

