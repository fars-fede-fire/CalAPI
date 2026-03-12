import json
import secrets

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from database import get_session
from models import Employee, ShiftEntry, RawShift, UploadSession
from services import ExcelParser
from services.ics_writer import write_ics_for_all

router = APIRouter(prefix="/upload", tags=["Upload"])


# ── Schemas ────────────────────────────────────────────────────────────────────

class ParseResponse(BaseModel):
    session_token: str
    all_columns: list[str]
    known_employees: list[str]
    new_columns: list[str]


class ConfirmEmployeesRequest(BaseModel):
    session_token: str
    confirmed_employees: list[str]


class ConfirmEmployeesResponse(BaseModel):
    employees_added: list[str]
    shift_entries_added: int
    unmapped_raw_values: list[str]


# ── Step 1: Parse ──────────────────────────────────────────────────────────────

@router.post("/parse", response_model=ParseResponse)
async def parse_excel(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> ParseResponse:
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(400, "Kun .xlsx / .xls filer accepteres.")

    file_bytes = await file.read()

    try:
        parser = ExcelParser(file_bytes)
        parser.parse()
    except TypeError as exc:
        raise HTTPException(422, str(exc))

    all_columns = parser.get_employees()
    shifts = parser.dataframe_to_shift(all_columns)

    known: list[str] = []
    new: list[str] = []
    for col in all_columns:
        exists = session.exec(select(Employee).where(Employee.name == col)).first()
        if exists:
            known.append(col)
        else:
            new.append(col)

    token = secrets.token_urlsafe(24)
    upload_session = UploadSession(
        token=token,
        shifts_json=json.dumps(
            [{"date": s["date"].isoformat(), "employee": s["employee"], "raw_shift": s["raw_shift"]} for s in shifts]
        ),
        all_columns_json=json.dumps(all_columns),
        known_employees_json=json.dumps(known),
        new_columns_json=json.dumps(new),
        employees_confirmed=False,
    )
    session.add(upload_session)
    session.commit()

    return ParseResponse(session_token=token, all_columns=all_columns, known_employees=known, new_columns=new)


# ── Step 2: Confirm employees ──────────────────────────────────────────────────

@router.post("/confirm-employees", response_model=ConfirmEmployeesResponse)
def confirm_employees(
    payload: ConfirmEmployeesRequest,
    session: Session = Depends(get_session),
) -> ConfirmEmployeesResponse:
    us = session.exec(select(UploadSession).where(UploadSession.token == payload.session_token)).first()
    if not us:
        raise HTTPException(404, "Upload session ikke fundet.")
    if us.employees_confirmed:
        raise HTTPException(409, "Denne session er allerede bekraeftet.")

    known_employees: list[str] = json.loads(us.known_employees_json)
    new_columns: list[str] = json.loads(us.new_columns_json)

    invalid = set(payload.confirmed_employees) - set(new_columns)
    if invalid:
        raise HTTPException(422, f"Ukendte kolonner: {sorted(invalid)}")

    all_employee_names = known_employees + payload.confirmed_employees
    employee_map: dict[str, int] = {}
    added_names: list[str] = []

    for name in all_employee_names:
        existing = session.exec(select(Employee).where(Employee.name == name)).first()
        if existing:
            employee_map[name] = existing.id
        else:
            emp = Employee(name=name)
            session.add(emp)
            session.flush()
            employee_map[name] = emp.id
            added_names.append(name)

    raw_shifts = json.loads(us.shifts_json)
    employee_set = set(all_employee_names)

    from datetime import date as date_type
    dates_in_file = {date_type.fromisoformat(s["date"]) for s in raw_shifts if s["employee"] in employee_set}
    emp_ids = list(employee_map.values())

    if emp_ids and dates_in_file:
        existing_entries = session.exec(
            select(ShiftEntry).where(
                ShiftEntry.employee_id.in_(emp_ids),
                ShiftEntry.date.in_(dates_in_file),
            )
        ).all()
        for e in existing_entries:
            session.delete(e)
        session.flush()

    added_count = 0
    for s in raw_shifts:
        if s["employee"] not in employee_set:
            continue
        raw_value = str(s["raw_shift"]).upper().strip()
        if raw_value and raw_value != "NAN":
            existing_raw = session.exec(select(RawShift).where(RawShift.name == raw_value)).first()
            if not existing_raw:
                session.add(RawShift(name=raw_value))
        entry = ShiftEntry(employee_id=employee_map[s["employee"]], date=date_type.fromisoformat(s["date"]), raw_value=raw_value)
        session.add(entry)
        added_count += 1

    us.employees_confirmed = True
    session.commit()

    # Regenerate all ICS files so existing subscribers get updated shifts
    write_ics_for_all(session)

    all_raw = session.exec(select(RawShift)).all()
    unmapped = [r.name for r in all_raw if r.shift_type_id is None and r.name != "NAN"]

    return ConfirmEmployeesResponse(employees_added=added_names, shift_entries_added=added_count, unmapped_raw_values=unmapped)