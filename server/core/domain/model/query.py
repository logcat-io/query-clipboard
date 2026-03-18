from datetime import datetime
from typing import ClassVar, Optional

from pydantic import BaseModel, ConfigDict

from server.core.domain.exception.domain_exception import InvalidQueryException


class Query(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    title: str
    description: Optional[str] = None
    purpose: str  # 조회 | 수정 | 삭제 | 집계 | 기타
    tags: str = ""
    sql_text: str
    created_at: Optional[datetime] = None

    VALID_PURPOSES: ClassVar[tuple] = ("조회", "수정", "삭제", "집계", "기타")

    def validate(self) -> None:
        if not self.title or not self.title.strip():
            raise InvalidQueryException("제목은 필수입니다")
        if self.purpose not in self.VALID_PURPOSES:
            raise InvalidQueryException(f"유효하지 않은 용도: {self.purpose}")
        if not self.sql_text or not self.sql_text.strip():
            raise InvalidQueryException("SQL은 필수입니다")
