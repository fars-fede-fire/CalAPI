from typing import Optional, List
from datetime import time, date
from pydantic import BaseModel


# ── ShiftCategory ──────────────────────────────────────────────────────────────

class ShiftCategoryCreate(BaseModel):
    name: str


class ShiftCategoryRead(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


# ── ShiftType ──────────────────────────────────────────────────────────────────

class ShiftTypeCreate(BaseModel):
    name: str
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    shift_category_id: int
    display_order: int = 0


class ShiftTypeRead(BaseModel):
    id: int
    name: str
    start_time: Optional[time]
    end_time: Optional[time]
    shift_category_id: int
    display_order: int

    model_config = {"from_attributes": True}


# ── RawShift ───────────────────────────────────────────────────────────────────

class RawShiftRead(BaseModel):
    id: int
    name: str
    shift_type_id: Optional[int]

    model_config = {"from_attributes": True}


class RawShiftMap(BaseModel):
    """Map a raw cell value to a ShiftType."""
    raw_name: str
    shift_type_id: Optional[int]  # None = unmap / mark as irrelevant


# ── Employee ───────────────────────────────────────────────────────────────────

class EmployeeRead(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


# ── Upload ─────────────────────────────────────────────────────────────────────

class UploadResult(BaseModel):
    employees_found: List[str]
    shift_entries_added: int
    unmapped_raw_values: List[str]


# ── CalendarSubscription ───────────────────────────────────────────────────────

class SubscriptionCreate(BaseModel):
    """Create a new calendar subscription for an employee."""
    label: str = "Min kalender"
    all_day_events: bool = True
    show_day_roster: bool = True
    # Category IDs to include. Empty list = include ALL categories.
    category_ids: List[int] = []


class SubscriptionRead(BaseModel):
    id: int
    employee_id: int
    label: str
    token: str
    all_day_events: bool
    show_day_roster: bool
    category_ids: List[int]
    ics_url: str

    model_config = {"from_attributes": True}