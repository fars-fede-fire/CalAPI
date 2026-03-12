from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from database import get_session
from services.ics_writer import write_ics_for_all
from models import RawShift, ShiftType
from schemas import RawShiftRead, RawShiftMap

router = APIRouter(prefix="/raw-shifts", tags=["Raw Shifts"])


@router.get("", response_model=list[RawShiftRead])
def list_raw_shifts(session: Session = Depends(get_session)):
    """List all raw cell values found across all uploaded files."""
    return session.exec(select(RawShift)).all()


@router.get("/unmapped", response_model=list[RawShiftRead])
def list_unmapped(session: Session = Depends(get_session)):
    """Raw values that have not yet been mapped to a ShiftType."""
    return session.exec(
        select(RawShift).where(RawShift.shift_type_id == None)  # noqa: E711
    ).all()


@router.post("/map", response_model=RawShiftRead)
def map_raw_shift(
    payload: RawShiftMap,
    session: Session = Depends(get_session),
):
    """
    Map (or unmap) a raw cell value to a ShiftType.

    Send `shift_type_id: null` to remove an existing mapping.
    """
    raw_name = payload.raw_name.upper().strip()
    raw = session.exec(select(RawShift).where(RawShift.name == raw_name)).first()

    if not raw:
        # Auto-create the raw shift entry if it doesn't exist yet
        raw = RawShift(name=raw_name)
        session.add(raw)

    if payload.shift_type_id is not None:
        if not session.get(ShiftType, payload.shift_type_id):
            raise HTTPException(status_code=404, detail="ShiftType ikke fundet.")

    raw.shift_type_id = payload.shift_type_id
    session.commit()
    session.refresh(raw)
    write_ics_for_all(session)
    return raw


@router.post("/map/bulk", response_model=list[RawShiftRead])
def bulk_map(
    mappings: list[RawShiftMap],
    session: Session = Depends(get_session),
):
    """Map multiple raw values in one request."""
    results = []
    for payload in mappings:
        raw_name = payload.raw_name.upper().strip()
        raw = session.exec(select(RawShift).where(RawShift.name == raw_name)).first()
        if not raw:
            raw = RawShift(name=raw_name)
            session.add(raw)

        if payload.shift_type_id is not None:
            if not session.get(ShiftType, payload.shift_type_id):
                raise HTTPException(
                    status_code=404,
                    detail=f"ShiftType {payload.shift_type_id} ikke fundet.",
                )
        raw.shift_type_id = payload.shift_type_id
        results.append(raw)

    session.commit()
    for r in results:
        session.refresh(r)
    write_ics_for_all(session)
    return results