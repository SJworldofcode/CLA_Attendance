# calendar_ui.py
from flask import Blueprint, render_template, request
from flask_login import login_required
from datetime import date, timedelta
from calendar import monthrange
from models import SchoolCalendar, SchoolYear

calendar_ui = Blueprint("calendar_ui", __name__)

@calendar_ui.route("/calendar/month")
@login_required
def calendar_month():
    today = date.today()
    y = int(request.args.get("year", today.year))
    m = int(request.args.get("month", today.month))

    if m < 1:
        y, m = y - 1, 12
    if m > 12:
        y, m = y + 1, 1

    first = date(y, m, 1)
    last_day = monthrange(y, m)[1]
    # Sunday-start 6-week grid
    days_back = (first.weekday() + 1) % 7
    grid_start = first - timedelta(days=days_back)
    grid_days = [grid_start + timedelta(days=i) for i in range(42)]
    weeks = [grid_days[i:i+7] for i in range(0, 42, 7)]

    q_start, q_end = grid_days[0], grid_days[-1]
    rows = (SchoolCalendar.query
        .filter(SchoolCalendar.date >= q_start, SchoolCalendar.date <= q_end)
        .order_by(SchoolCalendar.date)
        .all())

    by_date = {}
    for r in rows:
        by_date.setdefault(r.date, []).append(r)

    classes = {
        "Holiday": "bg-danger",
        "In-service": "bg-warning",
        "Closed": "bg-secondary",
        "Regular": "bg-success",
    }

    prev_y, prev_m = (y - 1, 12) if m == 1 else (y, m - 1)
    next_y, next_m = (y + 1, 1) if m == 12 else (y, m + 1)

    years = SchoolYear.query.order_by(SchoolYear.start_date).all()

    return render_template(
        "calendar_month.html",
        year=y, month=m, today=today,
        weeks=weeks, in_month=lambda d: d.month == m,
        by_date=by_date, classes=classes,
        prev_y=prev_y, prev_m=prev_m, next_y=next_y, next_m=next_m,
        years=years
    )
