from typing import Optional

from pydantic import AwareDatetime
from sqlmodel import SQLModel

from server.core.domain.exception.domain_exception import InvalidQueryException


class Query(SQLModel):

    id: Optional[int] = None
    title: str
    description: Optional[str] = None
    purpose_id: int
    tags: str = ""
    sql_text: str
    version: int = 1
    created_at: Optional[AwareDatetime] = None
    updated_at: Optional[AwareDatetime] = None

    def validate(self) -> None:
        if not self.title or not self.title.strip():
            raise InvalidQueryException("제목은 필수입니다")
        if not self.sql_text or not self.sql_text.strip():
            raise InvalidQueryException("SQL은 필수입니다")
