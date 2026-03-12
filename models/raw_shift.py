from typing import Optional
from sqlmodel import SQLModel, Field


class RawShift(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    # The raw cell value from Excel (stored uppercase, stripped)
    name: str = Field(index=True, unique=True)
    shift_type_id: Optional[int] = Field(default=None, foreign_key="shifttype.id")
