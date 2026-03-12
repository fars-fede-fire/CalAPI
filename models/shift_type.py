from typing import Optional
from datetime import time
from sqlmodel import SQLModel, Field


class ShiftType(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    shift_category_id: int = Field(foreign_key="shiftcategory.id")
    # Lower number = appears first in day roster description (default 0)
    display_order: int = Field(default=0)