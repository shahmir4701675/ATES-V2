"""Input contracts for accounts and linked directory records."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

Role = Literal["Administrator", "Coordinator", "Approver", "Faculty", "Student"]
ROLES = Role.__args__
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Username = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
Email = Annotated[str, StringConstraints(strip_whitespace=True, max_length=120, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")]
Password = Annotated[str, StringConstraints(min_length=8, max_length=1024)]
AccountId = Annotated[int, Field(gt=0)]
SmallPositive = Annotated[int, Field(ge=1, le=32767)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Login(Input):
    username: Username
    password: Annotated[str, StringConstraints(min_length=1, max_length=1024)]


class ResetPassword(Input):
    password: Password


class ChangePassword(Input):
    current_password: Annotated[str, StringConstraints(min_length=1, max_length=1024)]
    password: Password


class NewDepartment(Input):
    code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10)]
    name: Name


class LinkedRecord(Input):
    department_id: AccountId | None = None
    department: NewDepartment | None = None


class NewInstructor(LinkedRecord):
    full_name: Name
    email: Email
    max_daily_hours: SmallPositive = 4
    max_weekly_hours: SmallPositive = 18

    @field_validator("max_weekly_hours")
    @classmethod
    def validate_weekly_hours(cls, value, info):
        if value < info.data.get("max_daily_hours", 1):
            raise ValueError("Weekly hours must be at least the daily hours.")
        return value


class NewBatch(LinkedRecord):
    program_code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10)]
    batch_year: Annotated[int, Field(ge=1900, le=9999)]
    section: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5)]
    strength: SmallPositive


class AccountDetails(Input):
    username: Username
    full_name: Name
    email: Email
    role: Role
    instructor_id: AccountId | None = None
    batch_id: AccountId | None = None
    instructor: NewInstructor | None = None
    batch: NewBatch | None = None


class NewAccount(AccountDetails, ResetPassword):
    pass


class AccountStatus(Input):
    active: bool

