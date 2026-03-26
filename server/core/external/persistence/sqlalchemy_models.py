from datetime import datetime, timezone
from typing import Optional

from pydantic import AwareDatetime
from sqlalchemy_utc import UtcDateTime
from sqlalchemy import Text
from sqlmodel import SQLModel, Field, func


class PurposeTable(SQLModel, table=True):
    __tablename__ = "purposes"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=20, unique=True)
    sort_order: int = Field(default=0)


class QueryTable(SQLModel, table=True):
    __tablename__ = "queries"

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    description: Optional[str] = Field(default=None, sa_type=Text)
    purpose_id: int = Field(foreign_key="purposes.id")
    tags: str = Field(default="", max_length=500)
    sql_text: str = Field(sa_type=Text)
    version: int = Field(default=1)
    created_at: Optional[AwareDatetime] = Field(
        default=None,
        nullable=False,
        sa_type=UtcDateTime,
        sa_column_kwargs={
            "server_default": func.now(),
        },
    )
    updated_at: Optional[AwareDatetime] = Field(
        default=None,
        sa_type=UtcDateTime,
        sa_column_kwargs={
            "server_default": func.now(),
            "onupdate": lambda: datetime.now(timezone.utc),
        },
    )
