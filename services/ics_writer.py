"""
Shared helper: resolve and write an ICS file for one subscription to disk.
"""

from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Optional

from sqlmodel import Session, select

from models import (
    CalendarSubscription,
    SubscriptionCategory,
    Employee,
    ShiftEntry,
    RawShift,
    ShiftType,
    ShiftCategory,
)
from services.ics_generator import build_ics, ResolvedShift

import os
CALENDAR_DIR = Path(os.getenv("CALENDAR_DIR", str(Path(__file__).parent.parent / "static" / "calendars")))


def _build_global_roster(session: Session) -> dict[date, dict[str, list[str]]]:
    """
    Build a lookup: {date: {shift_type_name: [employee_name, ...]}}
    covering every mapped ShiftEntry across ALL employees.
    Called once per ICS write so queries are batched.
    """
    # Load everything we need in bulk
    all_entries   = session.exec(select(ShiftEntry)).all()
    all_employees = {e.id: e.name for e in session.exec(select(Employee)).all()}
    all_raws      = {r.name: r for r in session.exec(select(RawShift)).all()}
    all_types     = {t.id: t for t in session.exec(select(ShiftType)).all()}

    # {date: {shift_type_name: [employee_name, ...]}}
    roster: dict[date, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))

    for entry in all_entries:
        raw = all_raws.get(entry.raw_value)
        if raw is None or raw.shift_type_id is None:
            continue
        shift_type = all_types.get(raw.shift_type_id)
        if shift_type is None:
            continue
        emp_name = all_employees.get(entry.employee_id)
        if emp_name is None:
            continue
        roster[entry.date][shift_type.name].append(emp_name)

    # Sort each day's dict by display_order of the matching ShiftType
    name_to_order = {t.name: t.display_order for t in all_types.values()}
    return {
        d: dict(sorted(types.items(), key=lambda kv: name_to_order.get(kv[0], 0)))
        for d, types in roster.items()
    }


def write_ics_for_subscription(token: str, session: Session) -> None:
    CALENDAR_DIR.mkdir(parents=True, exist_ok=True)

    sub = session.exec(
        select(CalendarSubscription).where(CalendarSubscription.token == token)
    ).first()
    if not sub:
        return

    emp = session.get(Employee, sub.employee_id)
    if not emp:
        return

    cat_links = session.exec(
        select(SubscriptionCategory).where(
            SubscriptionCategory.subscription_id == sub.id
        )
    ).all()
    allowed: Optional[set[int]] = (
        {lnk.category_id for lnk in cat_links} if cat_links else None
    )

    entries = session.exec(
        select(ShiftEntry)
        .where(ShiftEntry.employee_id == sub.employee_id)
        .order_by(ShiftEntry.date)
    ).all()

    # Build the full daily roster once (used in every event description)
    global_roster = _build_global_roster(session)

    all_raws  = {r.name: r for r in session.exec(select(RawShift)).all()}
    all_types = {t.id: t for t in session.exec(select(ShiftType)).all()}
    all_cats  = {c.id: c for c in session.exec(select(ShiftCategory)).all()}

    resolved: list[ResolvedShift] = []
    for entry in entries:
        raw = all_raws.get(entry.raw_value)
        if raw is None or raw.shift_type_id is None:
            continue

        shift_type = all_types.get(raw.shift_type_id)
        if shift_type is None:
            continue

        if allowed is not None and shift_type.shift_category_id not in allowed:
            continue

        category = all_cats.get(shift_type.shift_category_id)
        resolved.append(
            ResolvedShift(
                shift_date=entry.date,
                summary=shift_type.name,
                category=category.name if category else "Ukendt",
                start_time=shift_type.start_time,
                end_time=shift_type.end_time,
                day_roster=global_roster.get(entry.date, {}),
            )
        )

    ics_bytes = build_ics(
        employee_name=emp.name,
        shifts=resolved,
        all_day_events=sub.all_day_events,
        show_day_roster=sub.show_day_roster,
    )

    (CALENDAR_DIR / f"{token}.ics").write_bytes(ics_bytes)


def write_ics_for_all(session: Session) -> None:
    """Regenerate all ICS files. Builds the global roster once and reuses it."""
    CALENDAR_DIR.mkdir(parents=True, exist_ok=True)

    subs      = session.exec(select(CalendarSubscription)).all()
    employees = {e.id: e.name for e in session.exec(select(Employee)).all()}
    all_raws  = {r.name: r for r in session.exec(select(RawShift)).all()}
    all_types = {t.id: t for t in session.exec(select(ShiftType)).all()}
    all_cats  = {c.id: c for c in session.exec(select(ShiftCategory)).all()}

    global_roster = _build_global_roster(session)

    for sub in subs:
        emp = employees.get(sub.employee_id)
        if not emp:
            continue

        cat_links = session.exec(
            select(SubscriptionCategory).where(
                SubscriptionCategory.subscription_id == sub.id
            )
        ).all()
        allowed: Optional[set[int]] = (
            {lnk.category_id for lnk in cat_links} if cat_links else None
        )

        entries = session.exec(
            select(ShiftEntry)
            .where(ShiftEntry.employee_id == sub.employee_id)
            .order_by(ShiftEntry.date)
        ).all()

        resolved: list[ResolvedShift] = []
        for entry in entries:
            raw = all_raws.get(entry.raw_value)
            if raw is None or raw.shift_type_id is None:
                continue
            shift_type = all_types.get(raw.shift_type_id)
            if shift_type is None:
                continue
            if allowed is not None and shift_type.shift_category_id not in allowed:
                continue
            category = all_cats.get(shift_type.shift_category_id)
            resolved.append(
                ResolvedShift(
                    shift_date=entry.date,
                    summary=shift_type.name,
                    category=category.name if category else "Ukendt",
                    start_time=shift_type.start_time,
                    end_time=shift_type.end_time,
                    day_roster=global_roster.get(entry.date, {}),
                )
            )

        ics_bytes = build_ics(
            employee_name=emp,
            shifts=resolved,
            all_day_events=sub.all_day_events,
            show_day_roster=sub.show_day_roster,
        )
        (CALENDAR_DIR / f"{sub.token}.ics").write_bytes(ics_bytes)


def delete_ics_file(token: str) -> None:
    path = CALENDAR_DIR / f"{token}.ics"
    if path.exists():
        path.unlink()