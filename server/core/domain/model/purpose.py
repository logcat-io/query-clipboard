from typing import Optional

from sqlmodel import SQLModel

from server.core.domain.exception.domain_exception import InvalidPurposeException


class Purpose(SQLModel):

    id: Optional[int] = None
    name: str
    sort_order: int = 0

    def validate(self) -> None:
        if not self.name or not self.name.strip():
            raise InvalidPurposeException("용도 이름은 필수입니다")
