from typing import Optional
from sqlmodel import SQLModel, Field


class CalendarSubscription(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    employee_id: int = Field(foreign_key="employee.id", index=True)
    label: str = Field(default="Min kalender")
    token: str = Field(unique=True, index=True)
    all_day_events: bool = Field(default=True)
    show_day_roster: bool = Field(default=True)


class SubscriptionCategory(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    subscription_id: int = Field(foreign_key="calendarsubscription.id", index=True)
    category_id: int = Field(foreign_key="shiftcategory.id")