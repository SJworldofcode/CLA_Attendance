from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from models import db, Student, Attendance, get_school_year_for_date, is_school_day

teacher_bp = Blueprint("teacher", __name__, url_prefix="/attendance")

@teacher_bp.route("/", methods=["GET", "POST"])
@login_required
def take_attendance():
    try:
        selected = date.fromisoformat(request.values.get("date") or str(date.today()))
    except ValueError:
        selected = date.today()

    # derive school year from date
    sy = get_school_year_for_date(selected)
    sy_id = sy.id if sy else None
    non_school = not is_school_day(selected, school_year_id=sy_id)

    students = Student.query.filter_by(active=True).order_by(Student.last_name, Student.first_name).all()

    if request.method == "POST" and not non_school:
        for s in students:
            status = request.form.get(f"status_{s.id}", "Present")
            notes = request.form.get(f"notes_{s.id}", "").strip() or None
            rec = Attendance.query.filter_by(student_id=s.id, date=selected).first()
            if not rec:
                rec = Attendance(student_id=s.id, date=selected, school_year_id=sy_id)
                db.session.add(rec)
            rec.status = status
            rec.notes = notes
            if sy_id and rec.school_year_id != sy_id:
                rec.school_year_id = sy_id
        db.session.commit()
        flash(f"Attendance saved for {selected.isoformat()}", "success")
        return redirect(url_for("teacher.take_attendance", date=selected.isoformat()))

    existing = {r.student_id: r for r in Attendance.query.filter_by(date=selected).all()}
    return render_template("attendance.html",
                           students=students, selected=selected, existing=existing,
                           non_school=non_school, school_year=sy)
