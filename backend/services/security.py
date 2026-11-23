"""Bcrypt credentials, revocable JWT sessions and authentication audit events."""

import base64
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from math import ceil
from uuid import uuid4

import bcrypt
import jwt
from sqlalchemy import select

from backend.api.errors import problem

IDLE = timedelta(minutes=30)
LOCKOUT = timedelta(minutes=15)
FAILURE_LIMIT = 5
PASSWORD_PREFIX = "sha256:"
DUMMY_HASH = bcrypt.hashpw(b"dummy for unknown accounts", bcrypt.gensalt(rounds=12)).decode()


def utc_now():
    return datetime.now(UTC).replace(tzinfo=None)


def password_bytes(password):
    return password.encode("utf-8")


def password_hash(password):
    data = password_bytes(password)
    prefix = ""
    if len(data) > 72:
        data = base64.b64encode(sha256(data).digest())
        prefix = PASSWORD_PREFIX
    return prefix + bcrypt.hashpw(data, bcrypt.gensalt(rounds=12)).decode()


def verify_password(password, stored):
    data = password_bytes(password)
    if stored.startswith(PASSWORD_PREFIX):
        data = base64.b64encode(sha256(data).digest())
        stored = stored[len(PASSWORD_PREFIX):]
    try:
        return bcrypt.checkpw(data, stored.encode("ascii"))
    except (ValueError, UnicodeError):
        return False


def audit(connection, store, actor, action, entity="User", entity_id=None, details=None):
    connection.execute(store["audit_logs"].insert().inline().values(
        user_id=actor, action=action, entity_type=entity, entity_id=entity_id, details=details,
    ))


def revoke(connection, store, user_id):
    sessions = store["user_sessions"]
    connection.execute(sessions.delete().where(sessions.c.user_id == user_id))


def public_user(user):
    fields = ("user_id", "username", "full_name", "email", "role", "account_status", "instructor_id", "batch_id")
    return {field: user[field] for field in fields}


class Security:
    def __init__(self, store, secret, clock=utc_now):
        self.store = store
        self.secret = secret
        self.clock = clock

    def login(self, connection, username, password):
        users = self.store["users"]
        sessions = self.store["user_sessions"]
        user = connection.execute(
            select(users).where(users.c.username == username).with_for_update()
        ).mappings().first()
        now = self.clock()
        if user and user["account_status"] == "Locked" and user["locked_until"] and now < user["locked_until"]:
            audit(connection, self.store, user["user_id"], "login_failed", entity_id=user["user_id"], details="Account locked")
            minutes = ceil((user["locked_until"] - now).total_seconds() / 60)
            return problem(423, f"Account locked. Try again in {minutes} minute(s).", retry_minutes=minutes)

        stored = user["password_hash"] if user else DUMMY_HASH
        valid = verify_password(password, stored)
        if not user or user["account_status"] == "Deactivated":
            audit(connection, self.store, user["user_id"] if user else None, "login_failed", details="Invalid credentials")
            return problem(401, "The username or password is incorrect.")

        user_id = user["user_id"]
        if not valid:
            failed_attempts = 1 if user["account_status"] == "Locked" else user["failed_attempts"] + 1
            locked = failed_attempts >= FAILURE_LIMIT
            connection.execute(users.update().where(users.c.user_id == user_id).values(
                failed_attempts=failed_attempts,
                account_status="Locked" if locked else "Active",
                locked_until=now + LOCKOUT if locked else None,
            ))
            audit(connection, self.store, user_id, "login_failed", entity_id=user_id, details="Invalid credentials")
            if locked:
                revoke(connection, self.store, user_id)
                audit(connection, self.store, user_id, "account_locked", entity_id=user_id)
                return problem(423, "Account locked. Try again in 15 minutes.", retry_minutes=15)
            return problem(401, "The username or password is incorrect.")

        connection.execute(users.update().where(users.c.user_id == user_id).values(
            failed_attempts=0, account_status="Active", locked_until=None,
        ))
        connection.execute(sessions.delete().where(sessions.c.last_seen_at <= now - IDLE))
        session_id = str(uuid4())
        connection.execute(sessions.insert().values(session_id=session_id, user_id=user_id, last_seen_at=now))
        token = jwt.encode({"sub": str(user_id), "sid": session_id, "iss": "ates"}, self.secret, algorithm="HS256")
        audit(connection, self.store, user_id, "login_success", entity_id=user_id)
        return {"access_token": token, "token_type": "bearer", "user": public_user(dict(user, account_status="Active"))}

    def authenticate(self, connection, token, activity=True):
        users = self.store["users"]
        sessions = self.store["user_sessions"]
        expired = problem(401, "Your session has ended. Sign in again.")
        try:
            claims = jwt.decode(token, self.secret, algorithms=["HS256"], issuer="ates",
                                options={"require": ["sub", "sid", "iss"]})
            user_id = int(claims["sub"])
            session_id = str(claims["sid"])
            if user_id <= 0 or user_id > 2_147_483_647 or len(session_id) != 36:
                raise ValueError("Invalid identifier")
        except (jwt.InvalidTokenError, TypeError, ValueError):
            raise expired from None

        now = self.clock()
        query = select(users, sessions.c.last_seen_at).join(sessions).where(
            users.c.user_id == user_id, users.c.account_status == "Active", sessions.c.session_id == session_id,
        )
        user = connection.execute(query.with_for_update(of=users) if activity else query).mappings().first()
        if not user or user["last_seen_at"] <= now - IDLE:
            raise expired
        if activity:
            connection.execute(sessions.update().where(sessions.c.session_id == session_id).values(last_seen_at=now))
        return user, session_id

