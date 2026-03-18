from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class CreateQueryCommand(BaseModel):
    title: str
    description: Optional[str] = None
    purpose: str
    tags: str = ""
    sql_text: str


class UpdateQueryCommand(BaseModel):
    title: str
    description: Optional[str] = None
    purpose: str
    tags: str = ""
    sql_text: str


class QueryResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: Optional[str] = None
    purpose: str
    tags: str = ""
    sql_text: str
    created_at: datetime


class QuerySearchCriteria(BaseModel):
    purpose: Optional[str] = None
    search: Optional[str] = None
