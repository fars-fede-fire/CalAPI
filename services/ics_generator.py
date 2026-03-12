from datetime import datetime, timedelta, date, time
from typing import Optional
from dataclasses import dataclass, field
import pytz
from icalendar import Calendar, Event, vText
import uuid


TIMEZONE = pytz.timezone("Europe/Copenhagen")


@dataclass
class ResolvedShift:
    shift_date: date
    summary: str                            # ShiftType.name
    category: str                           # ShiftCategory.name
    start_time: Optional[time]
    end_time: Optional[time]
    # {shift_type_name: [employee_name, ...]} for every employee that day
    day_roster: dict[str, list[str]] = field(default_factory=dict)


def _build_description(shift: ResolvedShift) -> str:
    """
    Build a multi-line description:

        TX vagt: Medarbejder A
        Bagvagt: Medarbejder B
        Dagtid: Medarbejder C, D, E
    """
    if not shift.day_roster:
        return f"Kategori: {shift.category}"

    lines = []
    for shift_type_name, employees in shift.day_roster.items():
        lines.append(f"{shift_type_name}: {', '.join(sorted(employees))}")
    return "\n".join(lines)


def build_ics(
    employee_name: str,
    shifts: list[ResolvedShift],
    all_day_events: bool,
    show_day_roster: bool = True,
) -> bytes:
    cal = Calendar()
    cal.add("prodid", "-//Shift Calendar//shift_calendar//EN")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("method", "PUBLISH")
    cal.add("x-wr-calname", vText(f"{employee_name} – Vagter"))
    cal.add("x-wr-timezone", vText("Europe/Copenhagen"))
    cal.add("x-wr-caldesc", vText(f"Vagtkalender for {employee_name}"))

    for shift in shifts:
        event = Event()
        event.add("uid", str(uuid.uuid4()))
        event.add("summary", vText(shift.summary))
        event.add("description", vText(_build_description(shift) if show_day_roster else f"Kategori: {shift.category}"))

        use_timed = (
            not all_day_events
            and shift.start_time is not None
            and shift.end_time is not None
        )

        if use_timed:
            dt_start = TIMEZONE.localize(
                datetime.combine(shift.shift_date, shift.start_time)
            )
            if shift.end_time <= shift.start_time:
                dt_end = TIMEZONE.localize(
                    datetime.combine(
                        shift.shift_date + timedelta(days=1), shift.end_time
                    )
                )
            else:
                dt_end = TIMEZONE.localize(
                    datetime.combine(shift.shift_date, shift.end_time)
                )
            event.add("dtstart", dt_start)
            event.add("dtend", dt_end)
        else:
            event.add("dtstart", shift.shift_date)
            event.add("dtend", shift.shift_date + timedelta(days=1))

        event.add("dtstamp", datetime.now(tz=pytz.utc))
        cal.add_component(event)

    return cal.to_ical()