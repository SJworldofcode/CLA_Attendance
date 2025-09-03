# utils.py
from datetime import datetime, date, timedelta
from flask import Response
import csv as _csv
import io as _io

# ---------- CSV helper ----------
def csv_response(rows, filename, header, title: str | None = None):
    """Return a Flask Response containing CSV.
    - rows: iterable of sequences matching header
    - filename: download name
    - header: list[str]
    - title: optional first line (then a blank line)
    """
    sio = _io.StringIO()
    w = _csv.writer(sio)
    if title:
        w.writerow([title])
        w.writerow([])
    w.writerow(header)
    for r in rows:
        w.writerow(list(r))
    data = sio.getvalue()
    sio.close()
    return Response(data, mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename={filename}"})

# ---------- Date parsing (flexible) ----------
_DATE_FORMATS = [
    "%Y-%m-%d",  # 2024-08-15
    "%m/%d/%Y",  # 8/15/2024
    "%m-%d-%Y",
    "%m/%d/%y",
    "%Y/%m/%d",
    "%m-%d-%y",
]

def _try_excel_serial(s: str):
    try:
        n = int(s)
    except Exception:
        return None
    # Excel 1900-date system: 1 -> 1899-12-31; common workaround base is 1899-12-30
    if 1 <= n <= 100000:
        return date(1899, 12, 30) + timedelta(days=n)
    return None

def parse_date_any(value: str) -> date:
    s = (value or "").strip()
    # ISO fast-path
    try:
        return date.fromisoformat(s)
    except Exception:
        pass
    # Excel serials
    d = _try_excel_serial(s)
    if d:
        return d
    # Common formats
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unsupported date format: {value!r}")

# ---------- ICS helpers ----------
def calendar_rows_to_ics(rows):
    """Build a simple ICS bytes payload from rows of (date, type, description).
    Creates all-day events (DTSTART/DTEND date values). Avoids DTSTAMP to
    sidestep parser quirks.
    """
    def fmt(d: date) -> str:
        return d.strftime("%Y%m%d")

    def clean(s: str) -> str:
        return "".join(ch for ch in s if ch.isalnum())

    lines = []
    add = lines.append
    add("BEGIN:VCALENDAR")
    add("PRODID:-//CLA Attendance//Calendar Export//EN")
    add("VERSION:2.0")
    add("CALSCALE:GREGORIAN")
    add("METHOD:PUBLISH")

    for d, t, desc in rows:
        dtstart = fmt(d)
        dtend = fmt(d + timedelta(days=1))  # exclusive end
        uid = f"{dtstart}-{clean(t)}-CLA@local"
        add("BEGIN:VEVENT")
        add(f"UID:{uid}")
        # Encode type + description into SUMMARY and CATEGORIES
        summary = t if not desc else f"{t} – {desc}"
        add(f"SUMMARY:{summary}")
        add(f"CATEGORIES:{t}")
        add(f"DTSTART;VALUE=DATE:{dtstart}")
        add(f"DTEND;VALUE=DATE:{dtend}")
        add("END:VEVENT")

    add("END:VCALENDAR")
    text = "\r\n".join(lines) + "\r\n"
    return text.encode("utf-8")

def ics_to_calendar_rows(ics_bytes: bytes):
    """Parse a simple ICS (all-day events). Yield (date, type, description).
    Recognizes DTSTART, SUMMARY, CATEGORIES. SUMMARY like "Type – Desc" is split.
    """
    text = ics_bytes.decode("utf-8", errors="ignore")
    # Unfold folded lines (RFC 5545)
    unfolded = []
    for line in text.splitlines():
        if (line.startswith(" ") or line.startswith("\t")) and unfolded:
            unfolded[-1] += line.lstrip()
        else:
            unfolded.append(line)

    cur_date = None
    cur_type = None
    cur_desc = ""
    in_event = False

    for line in unfolded:
        ls = line.strip()
        if ls == "BEGIN:VEVENT":
            cur_date, cur_type, cur_desc = None, None, ""
            in_event = True
            continue
        if ls == "END:VEVENT":
            if cur_date and cur_type:
                yield (cur_date, cur_type, cur_desc or "")
            in_event = False
            continue
        if not in_event:
            continue

        if ls.startswith("DTSTART"):  # DTSTART;VALUE=DATE:YYYYMMDD or DTSTART:YYYYMMDD
            parts = ls.split(":", 1)
            if len(parts) == 2:
                ymd = parts[1]
                try:
                    y, m, d = int(ymd[:4]), int(ymd[4:6]), int(ymd[6:8])
                    cur_date = date(y, m, d)
                except Exception:
                    cur_date = None
            continue

        if ls.startswith("CATEGORIES:"):
            cur_type = ls.split(":", 1)[1].strip()
            continue

        if ls.startswith("SUMMARY:"):
            val = ls.split(":", 1)[1].strip()
            if " – " in val:
                maybe_t, maybe_desc = val.split(" – ", 1)
                if not cur_type:
                    cur_type = maybe_t.strip()
                cur_desc = maybe_desc.strip()
            else:
                if not cur_type:
                    cur_type = val
                else:
                    cur_desc = val
            continue
