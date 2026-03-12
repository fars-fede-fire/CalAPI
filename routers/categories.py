from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from database import get_session
from models.shift_category import ShiftCategory
from schemas import ShiftCategoryCreate, ShiftCategoryRead

router = APIRouter(prefix="/shift-categories", tags=["Shift Categories"])


@router.get("", response_model=list[ShiftCategoryRead])
def list_categories(session: Session = Depends(get_session)):
    return session.exec(select(ShiftCategory)).all()


@router.post("", response_model=ShiftCategoryRead, status_code=201)
def create_category(
    payload: ShiftCategoryCreate,
    session: Session = Depends(get_session),
):
    existing = session.exec(
        select(ShiftCategory).where(ShiftCategory.name == payload.name)
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Kategori eksisterer allerede.")
    cat = ShiftCategory(name=payload.name)
    session.add(cat)
    session.commit()
    session.refresh(cat)
    return cat


@router.delete("/{category_id}", status_code=204)
def delete_category(category_id: int, session: Session = Depends(get_session)):
    cat = session.get(ShiftCategory, category_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Kategori ikke fundet.")
    session.delete(cat)
    session.commit()
