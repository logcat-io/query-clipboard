from typing import Optional

from pydantic import AwareDatetime
from sqlmodel import SQLModel


class CreateQueryCommand(SQLModel):
    title: str
    description: Optional[str] = None
    purpose_id: int
    tags: str = ""
    sql_text: str


class UpdateQueryCommand(SQLModel):
    title: str
    description: Optional[str] = None
    purpose_id: int
    tags: str = ""
    sql_text: str


class QueryResult(SQLModel):
    id: int
    title: str
    description: Optional[str] = None
    purpose_id: int
    purpose_name: str = ""
    tags: str = ""
    sql_text: str
    version: int = 1
    created_at: AwareDatetime
    updated_at: Optional[AwareDatetime] = None


class QuerySearchCriteria(SQLModel):
    purpose_id: Optional[int] = None
    search: Optional[str] = None
