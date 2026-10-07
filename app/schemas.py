from datetime import date
from typing import Annotated

from pydantic import BaseModel, EmailStr, Field, StringConstraints

from app.config import MAX_RECIPIENTS

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
PersonName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class RecipientIn(BaseModel):
    name: PersonName
    email: EmailStr


class JobCreate(BaseModel):
    course_name: ShortText
    issuer: ShortText
    issue_date: date
    # list[dict], not list[RecipientIn]: typed as RecipientIn, one bad row would
    # make FastAPI reject the whole request. Rows are checked one by one instead.
    recipients: list[dict] = Field(min_length=1, max_length=MAX_RECIPIENTS)