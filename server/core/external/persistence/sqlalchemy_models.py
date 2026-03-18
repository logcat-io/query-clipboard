from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field
from sqlalchemy import Column, DateTime, func


class QueryTable(SQLModel, table=True):
    __tablename__ = "queries"

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    description: Optional[str] = None
    purpose: str
    tags: str = Field(default="")
    sql_text: str
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime, default=func.now(), server_default=func.now()),
    )
