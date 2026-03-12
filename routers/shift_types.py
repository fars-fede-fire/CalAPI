from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from database import get_session
from models import ShiftType, ShiftCategory
from schemas import ShiftTypeCreate, ShiftTypeRead

router = APIRouter(prefix="/shift-types", tags=["Shift Types"])


@router.get("", response_model=list[ShiftTypeRead])
def list_shift_types(session: Session = Depends(get_session)):
    return session.exec(select(ShiftType)).all()


@router.post("", response_model=ShiftTypeRead, status_code=201)
def create_shift_type(
    payload: ShiftTypeCreate,
    session: Session = Depends(get_session),
):
    # Validate category exists
    if not session.get(ShiftCategory, payload.shift_category_id):
        raise HTTPException(status_code=404, detail="ShiftCategory ikke fundet.")

    existing = session.exec(
        select(ShiftType).where(ShiftType.name == payload.name)
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="ShiftType eksisterer allerede.")

    st = ShiftType(**payload.model_dump())
    session.add(st)
    session.commit()
    session.refresh(st)
    return st


@router.put("/{shift_type_id}", response_model=ShiftTypeRead)
def update_shift_type(
    shift_type_id: int,
    payload: ShiftTypeCreate,
    session: Session = Depends(get_session),
):
    st = session.get(ShiftType, shift_type_id)
    if not st:
        raise HTTPException(status_code=404, detail="ShiftType ikke fundet.")
    if not session.get(ShiftCategory, payload.shift_category_id):
        raise HTTPException(status_code=404, detail="ShiftCategory ikke fundet.")

    for key, value in payload.model_dump().items():
        setattr(st, key, value)
    session.commit()
    session.refresh(st)
    return st


@router.delete("/{shift_type_id}", status_code=204)
def delete_shift_type(shift_type_id: int, session: Session = Depends(get_session)):
    st = session.get(ShiftType, shift_type_id)
    if not st:
        raise HTTPException(status_code=404, detail="ShiftType ikke fundet.")
    session.delete(st)
    session.commit()

@router.patch("/{shift_type_id}/order", response_model=ShiftTypeRead)
def update_display_order(
    shift_type_id: int,
    display_order: int,
    session: Session = Depends(get_session),
):
    """Update the display_order of a ShiftType (used in day roster description)."""
    st = session.get(ShiftType, shift_type_id)
    if not st:
        raise HTTPException(status_code=404, detail="ShiftType ikke fundet.")
    st.display_order = display_order
    session.commit()
    session.refresh(st)
    return st