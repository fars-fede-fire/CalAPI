import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, select

from database import get_session
from models import (
    Employee,
    CalendarSubscription,
    SubscriptionCategory,
    ShiftCategory,
)
from schemas import SubscriptionCreate, SubscriptionRead
from services.ics_writer import write_ics_for_subscription, delete_ics_file

router = APIRouter(tags=["Calendar"])


# ── Helper ─────────────────────────────────────────────────────────────────────

def _sub_to_read(
    sub: CalendarSubscription,
    session: Session,
    request: Optional[Request] = None,
) -> SubscriptionRead:
    cats = session.exec(
        select(SubscriptionCategory).where(
            SubscriptionCategory.subscription_id == sub.id
        )
    ).all()
    ics_url = f"/calendar/{sub.token}.ics"
    if request:
        ics_url = str(request.base_url).rstrip("/") + ics_url
    return SubscriptionRead(
        id=sub.id,
        employee_id=sub.employee_id,
        label=sub.label,
        token=sub.token,
        all_day_events=sub.all_day_events,
        show_day_roster=sub.show_day_roster,
        category_ids=[c.category_id for c in cats],
        ics_url=ics_url,
    )


# ── List subscriptions for an employee ────────────────────────────────────────

@router.get(
    "/employees/{employee_id}/subscriptions",
    response_model=list[SubscriptionRead],
    summary="List alle kalenderabonnementer for en medarbejder",
)
def list_subscriptions(
    employee_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> list[SubscriptionRead]:
    if not session.get(Employee, employee_id):
        raise HTTPException(404, "Medarbejder ikke fundet.")
    subs = session.exec(
        select(CalendarSubscription).where(
            CalendarSubscription.employee_id == employee_id
        )
    ).all()
    return [_sub_to_read(s, session, request) for s in subs]


# ── Create a new subscription ──────────────────────────────────────────────────

@router.post(
    "/employees/{employee_id}/subscriptions",
    response_model=SubscriptionRead,
    status_code=201,
    summary="Opret nyt kalenderabonnement for en medarbejder",
)
def create_subscription(
    employee_id: int,
    payload: SubscriptionCreate,
    request: Request,
    session: Session = Depends(get_session),
) -> SubscriptionRead:
    if not session.get(Employee, employee_id):
        raise HTTPException(404, "Medarbejder ikke fundet.")
    for cid in payload.category_ids:
        if not session.get(ShiftCategory, cid):
            raise HTTPException(404, f"ShiftCategory {cid} ikke fundet.")

    sub = CalendarSubscription(
        employee_id=employee_id,
        label=payload.label,
        token=secrets.token_urlsafe(32),
        all_day_events=payload.all_day_events,
        show_day_roster=payload.show_day_roster,
    )
    session.add(sub)
    session.flush()

    for cid in payload.category_ids:
        session.add(SubscriptionCategory(subscription_id=sub.id, category_id=cid))

    session.commit()
    session.refresh(sub)
    write_ics_for_subscription(sub.token, session)
    return _sub_to_read(sub, session, request)


# ── Delete a single subscription by ID ────────────────────────────────────────

@router.delete(
    "/subscriptions/{subscription_id}",
    status_code=204,
    summary="Slet ét kalenderabonnement",
)
def delete_subscription(
    subscription_id: int,
    session: Session = Depends(get_session),
):
    sub = session.get(CalendarSubscription, subscription_id)
    if not sub:
        raise HTTPException(404, "Abonnement ikke fundet.")

    links = session.exec(
        select(SubscriptionCategory).where(
            SubscriptionCategory.subscription_id == sub.id
        )
    ).all()
    for link in links:
        session.delete(link)

    delete_ics_file(sub.token)
    session.delete(sub)
    session.commit()