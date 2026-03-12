from typing import Optional
from sqlmodel import SQLModel, Field


class UploadSession(SQLModel, table=True):
    """
    Temporary storage for a parsed-but-not-yet-confirmed Excel upload.
    Holds JSON blobs so the confirmation step can reference the same parse.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    # URL-safe session token sent to the client
    token: str = Field(unique=True, index=True)
    # JSON: list of {date, employee, raw_shift} dicts
    shifts_json: str
    # JSON: list of all column names found in the file
    all_columns_json: str
    # JSON: list of column names already confirmed as Employee in the DB
    known_employees_json: str
    # JSON: list of column names NOT yet in DB (need user review)
    new_columns_json: str
    # True once the employee confirmation step is done
    employees_confirmed: bool = Field(default=False)
