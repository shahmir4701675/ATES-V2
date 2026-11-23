"""Validated teaching records and weekly-grid inputs."""

from datetime import date, time
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, field_validator, model_validator

from backend.api.schemas import AccountId, Email, Input, Name, NewBatch, NewDepartment, SmallPositive

ShortCode = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=15)]
NonnegativeHours = Annotated[int, Field(ge=0, le=32767)]


class Department(NewDepartment):
    pass


class Term(Input):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
    start_date: date
    end_date: date
    status: Literal["Planned", "Active", "Closed"] = "Planned"
    successor_id: AccountId | None = None
    confirm_close: bool = False

    @field_validator("end_date")
    @classmethod
    def order_dates(cls, value, info):
        if info.data.get("start_date", date.min) >= value:
            raise ValueError("End date must be after the start date.")
        return value


class Course(Input):
    course_code: ShortCode
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]
    department_id: AccountId
    credit_hours: NonnegativeHours
    lecture_hours: NonnegativeHours = 0
    lab_hours: NonnegativeHours = 0
    is_active: bool = True
    confirm_deactivate: bool = False

    @field_validator("lab_hours")
    @classmethod
    def contact_hours(cls, value, info):
        if value + info.data.get("lecture_hours", 0) == 0:
            raise ValueError("Enter at least one lecture or lab contact hour.")
        return value

    @model_validator(mode="after")
    def positive_contact_hours(self):
        if self.lecture_hours + self.lab_hours == 0:
            raise ValueError("Enter at least one lecture or lab contact hour.")
        return self


class Instructor(Input):
    full_name: Name
    department_id: AccountId
    email: Email
    max_daily_hours: SmallPositive = 4
    max_weekly_hours: SmallPositive = 18
    is_active: bool = True
    confirm_deactivate: bool = False

    @model_validator(mode="after")
    def valid_limit(self):
        if self.max_weekly_hours < self.max_daily_hours:
            raise ValueError("Weekly hours must be at least the daily hours.")
        return self


class Batch(NewBatch):
    department_id: AccountId
    department: None = None
    is_active: bool = True
    confirm_deactivate: bool = False


class Room(Input):
    room_code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)]
    building: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
    capacity: SmallPositive
    room_type: Literal["Lecture", "Lab", "Exam Hall"]
    is_active: bool = True
    confirm_deactivate: bool = False


class Offering(Input):
    term_id: AccountId
    course_id: AccountId
    batch_id: AccountId
    instructor_id: AccountId
    enrolled_count: SmallPositive


class Enrollment(Input):
    offering_id: AccountId
    student_id: AccountId


class Grid(Input):
    days: Annotated[list[Annotated[int, Field(ge=1, le=7)]], Field(min_length=1, max_length=7)]
    first_start: time
    slot_minutes: Annotated[int, Field(ge=5, le=240)] = 60
    slots_per_day: Annotated[int, Field(ge=1, le=48)]

    @field_validator("days")
    @classmethod
    def distinct_days(cls, value):
        if len(set(value)) != len(value):
            raise ValueError("Select each teaching day once.")
        return sorted(value)

    @field_validator("first_start")
    @classmethod
    def minute_start(cls, value):
        if value.second or value.microsecond or value.tzinfo:
            raise ValueError("Enter a local start time using hours and minutes.")
        return value

    @model_validator(mode="after")
    def end_before_midnight(self):
        if self.first_start.hour * 60 + self.first_start.minute + self.slot_minutes * self.slots_per_day >= 1440:
            raise ValueError("The last slot must end before midnight.")
        return self


class Block(Input):
    is_blocked: bool
    block_reason: Annotated[str, StringConstraints(strip_whitespace=True, max_length=50)] = ""

    @model_validator(mode="after")
    def require_reason(self):
        if self.is_blocked and not self.block_reason:
            raise ValueError("Enter a reason for the blocked slot.")
        return self


class Availability(Input):
    is_available: bool

