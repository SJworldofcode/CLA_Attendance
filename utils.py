# utils.py
import csv, io
from flask import Response
from datetime import date, timedelta
from typing import Iterable, Tuple
from icalendar import Calendar, Event

def csv_response(rows, filename, header):
    """rows = iterable of sequences (matching header order)"""
    si = io.StringIO()
    writer = csv.writer(si)
    writer.writerow(header)
    writer.writerows(rows)
    out = si.getvalue()
    si.close()
    return Response(
        out,
        mimetype="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


# Map our types to an iCal CATEGORY (and vice versa)
ICAL_TYPE_MAP = {
    "Holiday": "Holiday",
    "In-service": "In-Service",
    "Closed": "Closed",
    "Regular": "Regular"
}
ICAL_TYPE_MAP_REVERSE = {v.lower(): k for k, v in ICAL_TYPE_MAP.items()}

def calendar_rows_to_ics(rows: Iterable[Tuple[date, str, str]]) -> bytes:
    """
    rows: iterable of (day, type, description)
    Returns .ics bytes with all-day VEVENTs. dtend is exclusive (next day).
    """
    cal = Calendar()
    cal.add("prodid", "-//CLA Attendance//Calendar Export//EN")
    cal.add("version", "2.0")

    for d, t, desc in rows:
        ev = Event()
        # all-day event: date-only DTSTART/DTEND
        ev.add("dtstart", d)
        ev.add("dtend", d + timedelta(days=1))  # exclusive end
        # Summary: "Holiday – Labor Day" (or just "Holiday")
        summary = t if not desc else f"{t} – {desc}"
        ev.add("summary", summary)
        # categories to carry the type
        ev.add("categories", ICAL_TYPE_MAP.get(t, t))
        cal.add_component(ev)

    return cal.to_ical()

def ics_to_calendar_rows(ics_bytes: bytes) -> Iterable[Tuple[date, str, str]]:
    """
    Parse .ics and yield (date, type, description) for all-day events.
    If a VEVENT spans multiple days, yield each day.
    Type is taken from CATEGORIES (if present) or guessed from SUMMARY.
    """
    cal = Calendar.from_ical(ics_bytes)
    for comp in cal.walk():
        if comp.name != "VEVENT":
            continue
        dtstart = comp.get("dtstart")
        dtend = comp.get("dtend")
        if not dtstart:
            continue

        # Normalize to date objects (handle datetime too)
        def _as_date(x):
            v = x.dt if hasattr(x, "dt") else x
            if hasattr(v, "date"):
                return v.date()
            return v

        start_d = _as_date(dtstart)
        # Default end = start+1 if missing
        end_d = _as_date(dtend) if dtend else (start_d + timedelta(days=1))
        # Ensure date-only (strip tz)
        if not isinstance(start_d, date):
            start_d = start_d.date()
        if not isinstance(end_d, date):
            end_d = end_d.date()

        # Title/type
        summary = str(comp.get("summary", "")).strip()
        categories = comp.get("categories")
        cat = ""
        if categories:
            # categories may be list-like
            cat = str(categories[0] if isinstance(categories, (list, tuple)) else categories).strip()
        # Map back to our types; fall back to guessing from summary
        t = ICAL_TYPE_MAP_REVERSE.get(cat.lower()) if cat else None
        if not t:
            lower_sum = summary.lower()
            if "holiday" in lower_sum:
                t = "Holiday"
            elif "service" in lower_sum or "in service" in lower_sum:
                t = "In-service"
            elif "closed" in lower_sum:
                t = "Closed"
            else:
                t = "Regular"

        # Derive description = part after " – " if present
        desc = ""
        if "–" in summary:
            desc = summary.split("–", 1)[1].strip()
        elif "-" in summary:
            # some feeds use hyphen
            parts = summary.split("-", 1)
            if len(parts) == 2:
                desc = parts[1].strip()

        # Expand multi-day (dtend exclusive)
        cur = start_d
        while cur < end_d:
            yield (cur, t, desc)
            cur += timedelta(days=1)
