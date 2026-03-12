from typing import Optional
from datetime import date
from sqlmodel import SQLModel, Field


class ShiftEntry(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    employee_id: int = Field(foreign_key="employee.id", index=True)
    date: date
    raw_value: str  # The raw cell value, uppercased and stripped
