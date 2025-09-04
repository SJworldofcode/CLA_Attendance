# admin.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from flask_login import login_required, current_user
from datetime import date, timedelta
from sqlalchemy import func, case, or_
from werkzeug.security import generate_password_hash
import csv, io
from sqlalchemy.exc import IntegrityError

from models import (
    db,
    User,
    Student,
    Attendance,
    SchoolCalendar,
    SchoolYear,
)
from utils import csv_response, calendar_rows_to_ics, ics_to_calendar_rows, parse_date_any

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

# ---------- Access control ----------
@admin_bp.before_request
def require_admin():
    """Gate admin pages: allow reports to all authenticated users; the rest admin-only."""
    from flask import request
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login"))
    # Allow any logged-in user (teacher/admin) to access reports
    if request.endpoint == "admin.reports":
        return None
    if current_user.role != "admin":
        return ("Forbidden", 403)

# ---------- Students ----------
@admin_bp.route("/students")
@login_required
def students():
    q = (request.args.get("q") or "").strip()
    query = Student.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                Student.first_name.ilike(like),
                Student.last_name.ilike(like),
                Student.current_grade.ilike(like),
            )
        )
    rows = query.order_by(Student.last_name, Student.first_name).all()
    return render_template("students.html", rows=rows, q=q)

@admin_bp.route("/students/new", methods=["GET", "POST"])
@login_required
def student_new():
    if request.method == "POST":
        s = Student(
            first_name=request.form["first_name"].strip(),
            last_name=request.form["last_name"].strip(),
            current_grade=(request.form.get("grade") or "").strip() or None,
            active=bool(request.form.get("active")),
        )
        db.session.add(s)
        db.session.commit()
        flash("Student added", "success")
        return redirect(url_for("admin.students"))
    return render_template("student_form.html", student=None)

@admin_bp.route("/students/<int:sid>/edit", methods=["GET", "POST"])
@login_required
def student_edit(sid):
    s = Student.query.get_or_404(sid)
    if request.method == "POST":
        s.first_name = request.form["first_name"].strip()
        s.last_name = request.form["last_name"].strip()
        s.current_grade = (request.form.get("grade") or "").strip() or None
        s.active = bool(request.form.get("active"))
        db.session.commit()
        flash("Student updated", "success")
        return redirect(url_for("admin.students"))
    return render_template("student_form.html", student=s)

@admin_bp.route("/students/<int:sid>/delete", methods=["POST"])
@login_required
def student_delete(sid):
    s = Student.query.get_or_404(sid)
    db.session.delete(s)
    db.session.commit()
    flash("Student deleted", "warning")
    return redirect(url_for("admin.students"))

# CSV export/import for students
@admin_bp.route("/students/export")
@login_required
def students_export():
    rows = Student.query.order_by(Student.last_name, Student.first_name).all()
    data = [
        [s.first_name, s.last_name, s.current_grade or "", "1" if s.active else "0"]
        for s in rows
    ]
    header = ["first_name", "last_name", "grade", "active"]
    return csv_response(data, "student_roster.csv", header)

@admin_bp.route("/students/import", methods=["GET", "POST"])
@login_required
def students_import():
    if request.method == "POST":
        file = request.files.get("file")
        if not file or not file.filename.lower().endswith(".csv"):
            flash("Please choose a .csv file", "danger")
            return redirect(url_for("admin.students_import"))

        stream = io.StringIO(file.stream.read().decode("utf-8-sig"))
        reader = csv.DictReader(stream)
        created = updated = 0
        for row in reader:
            fn = (row.get("first_name") or "").strip()
            ln = (row.get("last_name") or "").strip()
            gr = (row.get("grade") or "").strip() or None
            act = (row.get("active") or "1").strip()
            if not fn or not ln:
                continue
            rec = Student.query.filter_by(first_name=fn, last_name=ln).first()
            if rec:
                rec.current_grade = gr
                rec.active = act.lower() in ("1", "true", "yes")
                updated += 1
            else:
                db.session.add(
                    Student(
                        first_name=fn,
                        last_name=ln,
                        current_grade=gr,
                        active=(act.lower() in ("1", "true", "yes")),
                    )
                )
                created += 1
        db.session.commit()
        flash(f"Imported {created} new, updated {updated} students", "success")
        return redirect(url_for("admin.students"))
    return render_template("students_import.html")

# ---------- School Years ----------
@admin_bp.route("/years")
@login_required
def years_list():
    rows = SchoolYear.query.order_by(SchoolYear.start_date).all()
    return render_template("years.html", rows=rows)

@admin_bp.route("/years/new", methods=["GET", "POST"])
@login_required
def years_new():
    if request.method == "POST":
        name = request.form["name"].strip()
        start = date.fromisoformat(request.form["start_date"])
        end = date.fromisoformat(request.form["end_date"])
        active = bool(request.form.get("active"))
        db.session.add(SchoolYear(name=name, start_date=start, end_date=end, active=active))
        db.session.commit()
        flash("School year created", "success")
        return redirect(url_for("admin.years_list"))
    return render_template("years_form.html", rec=None)

@admin_bp.route("/years/<int:yid>/edit", methods=["GET", "POST"])
@login_required
def years_edit(yid):
    rec = SchoolYear.query.get_or_404(yid)
    if request.method == "POST":
        rec.name = request.form["name"].strip()
        rec.start_date = date.fromisoformat(request.form["start_date"])
        rec.end_date = date.fromisoformat(request.form["end_date"])
        rec.active = bool(request.form.get("active"))
        db.session.commit()
        flash("School year updated", "success")
        return redirect(url_for("admin.years_list"))
    return render_template("years_form.html", rec=rec)

@admin_bp.route("/years/<int:yid>/delete", methods=["POST"])
@login_required
def years_delete(yid):
    rec = SchoolYear.query.get_or_404(yid)
    db.session.delete(rec)
    db.session.commit()
    flash("School year deleted", "warning")
    return redirect(url_for("admin.years_list"))

# ---------- Calendar (list/single/bulk/delete) ----------
@admin_bp.route("/calendar")
@login_required
def calendar_list():
    year_id = request.args.get("year_id")
    q = SchoolCalendar.query
    if year_id:
        q = q.filter(SchoolCalendar.school_year_id == int(year_id))
    rows = q.order_by(SchoolCalendar.date).all()
    years = SchoolYear.query.order_by(SchoolYear.start_date).all()
    return render_template("calendar.html", rows=rows, years=years, year_id=year_id)

@admin_bp.route("/calendar/new", methods=["GET", "POST"])
@login_required
def calendar_new():
    if request.method == "POST":
        d = date.fromisoformat(request.form["date"])
        t = request.form["type"]
        desc = (request.form.get("description") or "").strip() or None

        sy = SchoolYear.query.filter(SchoolYear.start_date <= d, SchoolYear.end_date >= d).first()
        sy_id = sy.id if sy else None

        rec = SchoolCalendar.query.filter_by(date=d, school_year_id=sy_id).first()
        if not rec:
            rec = SchoolCalendar(date=d, school_year_id=sy_id)
            db.session.add(rec)
        rec.type = t
        rec.description = desc
        db.session.commit()
        flash(f"Saved calendar day {d} as {t}", "success")
        return redirect(url_for("admin.calendar_list"))
    return render_template("calendar_form.html", rec=None)

@admin_bp.route("/calendar/bulk", methods=["GET", "POST"])
@login_required
def calendar_bulk():
    if request.method == "POST":
        start = date.fromisoformat(request.form["start"])
        end = date.fromisoformat(request.form["end"])
        t = request.form["type"]
        desc = (request.form.get("description") or "").strip() or None
        if end < start:
            flash("End date must be on/after start date", "danger")
            return redirect(url_for("admin.calendar_bulk"))

        cur = start
        cnt = 0
        while cur <= end:
            sy = SchoolYear.query.filter(SchoolYear.start_date <= cur, SchoolYear.end_date >= cur).first()
            sy_id = sy.id if sy else None
            rec = SchoolCalendar.query.filter_by(date=cur, school_year_id=sy_id).first()
            if not rec:
                rec = SchoolCalendar(date=cur, school_year_id=sy_id)
                db.session.add(rec)
            rec.type = t
            rec.description = desc
            cnt += 1
            cur += timedelta(days=1)

        db.session.commit()
        flash(f"Updated {cnt} days as {t}", "success")
        return redirect(url_for("admin.calendar_list"))
    return render_template("calendar_bulk.html")

@admin_bp.route("/calendar/<int:cid>/delete", methods=["POST"])
@login_required
def calendar_delete(cid):
    rec = SchoolCalendar.query.get_or_404(cid)
    db.session.delete(rec)
    db.session.commit()
    flash("Calendar entry deleted", "warning")
    return redirect(url_for("admin.calendar_list"))

@admin_bp.route("/calendar/<int:cid>/edit", methods=["GET", "POST"])
@login_required
def calendar_edit(cid):
    rec = SchoolCalendar.query.get_or_404(cid)

    if request.method == "POST":
        # read form
        d = date.fromisoformat(request.form["date"])
        t = request.form["type"]
        desc = (request.form.get("description") or "").strip() or None

        # recompute school year based on the chosen date
        sy = SchoolYear.query.filter(SchoolYear.start_date <= d,
                                     SchoolYear.end_date >= d).first()
        sy_id = sy.id if sy else None

        # apply changes
        rec.date = d
        rec.type = t
        rec.description = desc
        rec.school_year_id = sy_id

        try:
            db.session.commit()
            flash("Calendar day updated", "success")
            return redirect(url_for("admin.calendar_list"))
        except IntegrityError:
            db.session.rollback()
            flash("Another entry already exists for that date in the same school year.", "danger")

    return render_template("calendar_form.html", rec=rec)


# ---------- Calendar ICS export/import ----------
@admin_bp.route("/calendar/export")
@login_required
def calendar_export():
    start_str = request.args.get("start")
    end_str = request.args.get("end")
    year_id = request.args.get("year_id")

    q = SchoolCalendar.query
    fname = "school_calendar.ics"

    if year_id:
        q = q.filter(SchoolCalendar.school_year_id == int(year_id))
        fname = f"school_calendar_year{year_id}.ics"

    if start_str and end_str:
        start = date.fromisoformat(start_str)
        end = date.fromisoformat(end_str)
        if end < start:
            flash("End must be on/after start", "danger")
            return redirect(url_for("admin.calendar_list"))
        q = q.filter(SchoolCalendar.date >= start, SchoolCalendar.date <= end)
        fname = f"school_calendar_{start.isoformat()}_{end.isoformat()}.ics"

    rows = q.order_by(SchoolCalendar.date).all()
    payload = calendar_rows_to_ics((r.date, r.type, r.description or "") for r in rows)

    return send_file(
        io.BytesIO(payload),
        mimetype="text/calendar",
        as_attachment=True,
        download_name=fname,
    )

@admin_bp.route("/calendar/import", methods=["GET"])
@login_required
def calendar_import_form():
    return render_template("calendar_import.html")

@admin_bp.route("/calendar/import", methods=["POST"])
@login_required
def calendar_import():
    file = request.files.get("file")
    mode = (request.form.get("mode") or "merge").lower()  # 'merge' or 'replace'

    if not file or not file.filename.lower().endswith(".ics"):
        flash("Please choose a .ics file", "danger")
        return redirect(url_for("admin.calendar_import_form"))

    ics_bytes = file.stream.read()
    rows = list(ics_to_calendar_rows(ics_bytes))
    if not rows:
        flash("No calendar events found in the .ics.", "warning")
        return redirect(url_for("admin.calendar_list"))

    # Replace: delete only the (date, year) pairs present in the file
    if mode == "replace":
        to_delete = []
        for d, _t, _desc in rows:
            sy = SchoolYear.query.filter(SchoolYear.start_date <= d, SchoolYear.end_date >= d).first()
            sy_id = sy.id if sy else None
            to_delete.append((d, sy_id))
        for d, sy_id in to_delete:
            q = SchoolCalendar.query.filter_by(date=d, school_year_id=sy_id)
            q.delete(synchronize_session=False)

    created = updated = 0
    for d, t, desc in rows:
        sy = SchoolYear.query.filter(SchoolYear.start_date <= d, SchoolYear.end_date >= d).first()
        sy_id = sy.id if sy else None
        rec = SchoolCalendar.query.filter_by(date=d, school_year_id=sy_id).first()
        if not rec:
            rec = SchoolCalendar(date=d, school_year_id=sy_id)
            db.session.add(rec)
            created += 1
        else:
            updated += 1
        rec.type = t
        rec.description = desc or None

    db.session.commit()
    flash(f"Imported {created} new, updated {updated} calendar days", "success")
    return redirect(url_for("admin.calendar_list"))

# ---------- Calendar CSV import ----------
@admin_bp.route("/calendar/import_csv", methods=["GET", "POST"])
@login_required
def calendar_import_csv():
    years = SchoolYear.query.order_by(SchoolYear.start_date).all()
    if request.method == "POST":
        file = request.files.get("file")
        target_year_id = (request.form.get("school_year_id") or "").strip()
        mode = (request.form.get("mode") or "merge").lower()

        if not file or not file.filename.lower().endswith(".csv"):
            flash("Please choose a .csv file", "danger")
            return redirect(url_for("admin.calendar_import_csv"))

        stream = io.StringIO(file.stream.read().decode("utf-8-sig"))
        reader = csv.DictReader(stream)
        created = updated = skipped = 0

        # CSV header: date,type,description,year
        for row in reader:
            try:
                d = parse_date_any(row.get("date", ""))
            except Exception:
                skipped += 1
                continue

            t = (row.get("type") or "Regular").strip()
            desc = (row.get("description") or "").strip() or None
            year_name = (row.get("year") or "").strip()

            # resolve school year
            if year_name:
                sy = SchoolYear.query.filter_by(name=year_name).first()
                if not sy:
                    flash(f"Unknown school year in CSV: {year_name}", "danger")
                    return redirect(url_for("admin.calendar_import_csv"))
            elif target_year_id:
                sy = SchoolYear.query.get(int(target_year_id))
            else:
                sy = SchoolYear.query.filter(SchoolYear.start_date <= d, SchoolYear.end_date >= d).first()
            sy_id = sy.id if sy else None

            if mode == "replace":
                q = SchoolCalendar.query.filter_by(date=d, school_year_id=sy_id)
                q.delete(synchronize_session=False)

            rec = SchoolCalendar.query.filter_by(date=d, school_year_id=sy_id).first()
            if not rec:
                rec = SchoolCalendar(date=d, school_year_id=sy_id)
                db.session.add(rec)
                created += 1
            else:
                updated += 1
            rec.type = t
            rec.description = desc

        db.session.commit()
        flash(f"Calendar CSV imported: {created} new, {updated} updated, {skipped} skipped (bad date)", "success")
        return redirect(url_for("admin.calendar_list"))

    return render_template("calendar_import_csv.html", years=years)

# ---------- Attendance CSV export/import ----------
@admin_bp.route("/attendance/export")
@login_required
def attendance_export():
    start_str = request.args.get("start")
    end_str = request.args.get("end")
    year_id = request.args.get("year_id")

    if not start_str or not end_str:
        flash("Provide start and end dates to export attendance", "danger")
        return redirect(url_for("admin.reports"))

    start = date.fromisoformat(start_str)
    end = date.fromisoformat(end_str)
    if end < start:
        flash("End must be on/after start", "danger")
        return redirect(url_for("admin.reports"))

    q = db.session.query(Attendance).filter(
        Attendance.date >= start, Attendance.date <= end
    )
    if year_id:
        q = q.filter(Attendance.school_year_id == int(year_id))
    q = q.order_by(Attendance.date, Attendance.student_id)

    data = []
    for r in q:
        s = r.student
        year_name = r.school_year.name if r.school_year else ""
        grade_out = (r.grade_at_time or s.current_grade or "")
        data.append(
            [
                r.date.isoformat(),
                s.last_name,
                s.first_name,
                grade_out,
                r.status,
                r.notes or "",
                year_name,
            ]
        )
    header = ["date", "last_name", "first_name", "grade", "status", "notes", "year"]
    fname = f"attendance_{start.isoformat()}_{end.isoformat()}.csv"
    return csv_response(data, fname, header, title="Courageous Learners Academy Attendance")

@admin_bp.route("/attendance/import_csv", methods=["GET", "POST"])
@login_required
def attendance_import_csv():
    years = SchoolYear.query.order_by(SchoolYear.start_date).all()
    if request.method == "POST":
        file = request.files.get("file")
        target_year_id = (request.form.get("school_year_id") or "").strip()

        if not file or not file.filename.lower().endswith(".csv"):
            flash("Please choose a .csv file", "danger")
            return redirect(url_for("admin.attendance_import_csv"))

        stream = io.StringIO(file.stream.read().decode("utf-8-sig"))
        reader = csv.DictReader(stream)
        created = updated = skipped = 0

        # CSV header: date,last_name,first_name,grade,status,notes,year
        for row in reader:
            # DATE (robust parse)
            try:
                d = parse_date_any(row.get("date", ""))
            except Exception:
                skipped += 1  # bad date format
                continue

            ln = (row.get("last_name") or "").strip()
            fn = (row.get("first_name") or "").strip()
            gr = (row.get("grade") or "").strip() or None
            status = (row.get("status") or "Present").strip()
            notes = (row.get("notes") or "").strip() or None
            year_name = (row.get("year") or "").strip()

            # find student by name only
            s = Student.query.filter_by(last_name=ln, first_name=fn).first()
            if not s:
                skipped += 1            # no matching student
                continue

            # resolve year
            if year_name:
                sy = SchoolYear.query.filter_by(name=year_name).first()
                if not sy:
                    skipped += 1        # unknown year name
                    continue
            elif target_year_id:
                sy = SchoolYear.query.get(int(target_year_id))
            else:
                sy = SchoolYear.query.filter(SchoolYear.start_date <= d, SchoolYear.end_date >= d).first()
            sy_id = sy.id if sy else None

            rec = Attendance.query.filter_by(student_id=s.id, date=d).first()
            if not rec:
                rec = Attendance(student_id=s.id, date=d, school_year_id=sy_id)
                db.session.add(rec)
                created += 1
            else:
                updated += 1
            rec.status = status
            rec.notes = notes
            rec.grade_at_time = gr
            if sy_id and rec.school_year_id != sy_id:
                rec.school_year_id = sy_id

        db.session.commit()
        flash(f"Attendance CSV imported: {created} new, {updated} updated, {skipped} skipped", "success")
        return redirect(url_for("admin.reports"))

    return render_template("attendance_import_csv.html", years=years)

# ---------- Reports ----------
@admin_bp.route("/reports", methods=["GET"])
@login_required
def reports():
    # Daily summary (by date)
    try:
        d = date.fromisoformat((request.args.get("date") or str(date.today())))
    except ValueError:
        d = date.today()

    # Range for per-student %
    start_str = request.args.get("start")
    end_str = request.args.get("end")
    year_id = request.args.get("year_id")

    start = date.fromisoformat(start_str) if start_str else None
    end = date.fromisoformat(end_str) if end_str else None

    # Daily summary
    daily_q = db.session.query(
        Attendance.status, func.count(Attendance.id)
    ).filter(Attendance.date == d)
    daily_records_q = db.session.query(Attendance).filter(Attendance.date == d)
    if year_id:
        daily_q = daily_q.filter(Attendance.school_year_id == int(year_id))
        daily_records_q = daily_records_q.filter(Attendance.school_year_id == int(year_id))

    daily = daily_q.group_by(Attendance.status).all()
    daily_records = daily_records_q.all()

    # Per-student % over range
    stats = []
    if start and end and end >= start:
        q = db.session.query(
            Attendance.student_id,
            func.sum(case((Attendance.status == 'Present', 1), else_=0)).label("present"),
            func.count(Attendance.id).label("total"),
        ).filter(Attendance.date >= start, Attendance.date <= end)
        if year_id:
            q = q.filter(Attendance.school_year_id == int(year_id))
        q = q.group_by(Attendance.student_id)

        for sid, present, total in q:
            pct = round((present or 0) * 100.0 / total, 1) if total else None
            stats.append((sid, present or 0, total or 0, pct))

    students_by_id = {s.id: f"{s.last_name}, {s.first_name}" for s in Student.query.all()}
    years = SchoolYear.query.order_by(SchoolYear.start_date).all()

    return render_template(
        "reports.html",
        daily=daily,
        daily_records=daily_records,
        day=d,
        stats=stats,
        start=start,
        end=end,
        students_by_id=students_by_id,
        years=years,
        year_id=year_id,
    )

# ---------- Users (admin-managed) ----------
@admin_bp.route("/users")
@login_required
def users_list():
    rows = User.query.order_by(User.username).all()
    return render_template("users.html", rows=rows)

@admin_bp.route("/users/new", methods=["GET", "POST"])
@login_required
def users_new():
    if request.method == "POST":
        username = request.form["username"].strip()
        role = request.form["role"]
        email = (request.form.get("email") or "").strip() or None
        password = request.form["password"]
        active = bool(request.form.get("active"))

        if User.query.filter_by(username=username).first():
            flash("Username already exists", "danger")
            return redirect(url_for("admin.users_new"))

        db.session.add(
            User(
                username=username,
                role=role,
                email=email,
                active=active,
                password_hash=generate_password_hash(password),
            )
        )
        db.session.commit()
        flash("User created", "success")
        return redirect(url_for("admin.users_list"))
    return render_template("users_form.html", rec=None)

@admin_bp.route("/users/<int:uid>/edit", methods=["GET", "POST"])
@login_required
def users_edit(uid):
    rec = User.query.get_or_404(uid)
    if request.method == "POST":
        rec.username = request.form["username"].strip()
        rec.role = request.form["role"]
        rec.email = (request.form.get("email") or "").strip() or None
        rec.active = bool(request.form.get("active"))
        new_pw = (request.form.get("password") or "").strip()
        if new_pw:
            rec.password_hash = generate_password_hash(new_pw)
            flash("Password reset", "info")
        db.session.commit()
        flash("User updated", "success")
        return redirect(url_for("admin.users_list"))
    return render_template("users_form.html", rec=rec)

@admin_bp.route("/users/<int:uid>/delete", methods=["POST"])
@login_required
def users_delete(uid):
    rec = User.query.get_or_404(uid)
    db.session.delete(rec)
    db.session.commit()
    flash("User deleted", "warning")
    return redirect(url_for("admin.users_list"))
