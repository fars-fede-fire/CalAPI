"""
Import / export af konfiguration (ShiftCategory, ShiftType, RawShift)
som én samlet JSON-fil.

Export: GET  /config/export  → JSON download
Import: POST /config/import  → upsert baseret på name (idempotent)
"""

import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlmodel import Session, select
from typing import Optional

from database import get_session
from models import ShiftCategory, ShiftType, RawShift

router = APIRouter(prefix="/config", tags=["Config IO"])


# ── Schemas ────────────────────────────────────────────────────────────────────

class ShiftTypeExport(BaseModel):
    name: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    category: str                        # category name (not ID)
    display_order: int = 0

class RawShiftExport(BaseModel):
    name: str
    shift_type: Optional[str] = None     # shift type name (not ID)

class ConfigExport(BaseModel):
    categories: list[str]
    shift_types: list[ShiftTypeExport]
    raw_shifts: list[RawShiftExport]


# ── Export ─────────────────────────────────────────────────────────────────────

@router.get("/export", summary="Eksporter konfiguration som JSON")
def export_config(session: Session = Depends(get_session)) -> Response:
    cats    = session.exec(select(ShiftCategory)).all()
    types   = session.exec(select(ShiftType)).all()
    raws    = session.exec(select(RawShift)).all()

    cat_map  = {c.id: c.name for c in cats}
    type_map = {t.id: t.name for t in types}

    payload = ConfigExport(
        categories=[c.name for c in cats],
        shift_types=[
            ShiftTypeExport(
                name=t.name,
                start_time=str(t.start_time) if t.start_time else None,
                end_time=str(t.end_time) if t.end_time else None,
                category=cat_map.get(t.shift_category_id, ""),
                display_order=t.display_order,
            )
            for t in types
        ],
        raw_shifts=[
            RawShiftExport(
                name=r.name,
                shift_type=type_map.get(r.shift_type_id) if r.shift_type_id else None,
            )
            for r in raws
        ],
    )

    return Response(
        content=payload.model_dump_json(indent=2),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=vagtkalender_config.json"},
    )


# ── Import ─────────────────────────────────────────────────────────────────────

class ImportResult(BaseModel):
    categories_added: int
    shift_types_added: int
    raw_shifts_mapped: int
    warnings: list[str]

@router.post("/import", response_model=ImportResult, summary="Importer konfiguration fra JSON")
def import_config(
    payload: ConfigExport,
    session: Session = Depends(get_session),
) -> ImportResult:
    """
    Idempotent upsert — eksisterende poster med samme navn overskrives ikke,
    men manglende poster oprettes.  Raw shifts mappes til ShiftType via navn.
    """
    warnings: list[str] = []

    # 1. Categories
    cats_added = 0
    for name in payload.categories:
        existing = session.exec(select(ShiftCategory).where(ShiftCategory.name == name)).first()
        if not existing:
            session.add(ShiftCategory(name=name))
            cats_added += 1
    session.flush()

    # Re-fetch to get IDs
    cat_by_name = {c.name: c for c in session.exec(select(ShiftCategory)).all()}

    # 2. ShiftTypes
    types_added = 0
    for st in payload.shift_types:
        cat = cat_by_name.get(st.category)
        if not cat:
            warnings.append(f"ShiftType '{st.name}': kategori '{st.category}' ikke fundet — springer over.")
            continue
        existing = session.exec(select(ShiftType).where(ShiftType.name == st.name)).first()
        if not existing:
            from datetime import time

            def parse_time(s: Optional[str]) -> Optional[time]:
                if not s:
                    return None
                parts = s.split(":")
                return time(int(parts[0]), int(parts[1]))

            session.add(ShiftType(
                name=st.name,
                start_time=parse_time(st.start_time),
                end_time=parse_time(st.end_time),
                shift_category_id=cat.id,
                display_order=st.display_order,
            ))
            types_added += 1
    session.flush()

    type_by_name = {t.name: t for t in session.exec(select(ShiftType)).all()}

    # 3. RawShifts — upsert mapping
    raws_mapped = 0
    for rs in payload.raw_shifts:
        existing = session.exec(select(RawShift).where(RawShift.name == rs.name)).first()
        if not existing:
            existing = RawShift(name=rs.name)
            session.add(existing)
            session.flush()

        if rs.shift_type:
            st = type_by_name.get(rs.shift_type)
            if st:
                if existing.shift_type_id != st.id:
                    existing.shift_type_id = st.id
                    raws_mapped += 1
            else:
                warnings.append(f"RawShift '{rs.name}': vagttype '{rs.shift_type}' ikke fundet — mapping springer over.")

    session.commit()

    return ImportResult(
        categories_added=cats_added,
        shift_types_added=types_added,
        raw_shifts_mapped=raws_mapped,
        warnings=warnings,
    )