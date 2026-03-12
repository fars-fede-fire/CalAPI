from typing import Optional
from sqlmodel import SQLModel, Field


class ShiftCategory(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
