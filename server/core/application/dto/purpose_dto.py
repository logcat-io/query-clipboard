from typing import Optional

from sqlmodel import SQLModel


class CreatePurposeCommand(SQLModel):
    name: str
    sort_order: int = 0


class PurposeResult(SQLModel):
    id: int
    name: str
    sort_order: int = 0
