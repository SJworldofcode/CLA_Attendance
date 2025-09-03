# models.py
from datetime import date
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

# --- Users ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="teacher")  # admin/teacher
    active = db.Column(db.Boolean, nullable=False, default=True)
    email = db.Column(db.String(255))  # optional

# --- School Years ---
class SchoolYear(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(40), unique=True, nullable=False)  # e.g., "2024-25", "Summer 2025"
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    active = db.Column(db.Boolean, nullable=False, default=True)

    def includes(self, d: date) -> bool:
        return self.start_date <= d <= self.end_date

# --- Students ---
class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100), nullable=False, index=True)
    last_name  = db.Column(db.String(100), nullable=False, index=True)
    # canonical current grade on the roster
    current_grade = db.Column(db.String(10), nullable=True, index=True)
    # roster status
    active = db.Column(db.Boolean, nullable=False, default=True)

    # Identity = name (you can add an external_id later if needed)
    __table_args__ = (
        db.UniqueConstraint('first_name','last_name', name='uq_student_identity'),
    )


# --- Attendance ---
class Attendance(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False, index=True)
    date       = db.Column(db.Date, nullable=False, index=True)
    status     = db.Column(db.String(20), nullable=False)  # Present/Absent/Tardy
    notes      = db.Column(db.Text)
    # snapshot of grade at the time of attendance (optional, filled by imports or UI)
    grade_at_time = db.Column(db.String(10), nullable=True)

    # partition by school year for reports/exports
    school_year_id = db.Column(db.Integer, db.ForeignKey('school_year.id'), index=True)

    student = db.relationship("Student", backref="attendance_records", lazy=True)
    school_year = db.relationship("SchoolYear", lazy=True)

    __table_args__ = (
        db.UniqueConstraint("student_id", "date", name="uq_attendance_student_date"),
    )

# --- School Calendar ---
class SchoolCalendar(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    school_year_id = db.Column(db.Integer, db.ForeignKey("school_year.id"), index=True)
    date = db.Column(db.Date, nullable=False, index=True)
    type = db.Column(db.String(20), nullable=False, default="Regular")  # Regular/Holiday/In-service/Closed
    description = db.Column(db.String(255))

    school_year = db.relationship("SchoolYear", lazy=True)
    __table_args__ = (db.UniqueConstraint("date", "school_year_id", name="uq_cal_date_year"),)

# -------- Helpers --------
NON_SCHOOL_TYPES = {"Holiday", "In-service", "Closed"}

def get_school_year_for_date(d: date):
    return SchoolYear.query.filter(SchoolYear.start_date <= d, SchoolYear.end_date >= d).first()

def is_school_day(d: date, school_year_id: int | None = None) -> bool:
    # weekends off unless explicitly marked Regular in calendar
    if d.weekday() >= 5:
        q = SchoolCalendar.query.filter_by(date=d)
        if school_year_id:
            q = q.filter_by(school_year_id=school_year_id)
        cal = q.first()
        return bool(cal and cal.type == "Regular")

    q = SchoolCalendar.query.filter_by(date=d)
    if school_year_id:
        q = q.filter_by(school_year_id=school_year_id)
    cal = q.first()
    if cal and cal.type in NON_SCHOOL_TYPES:
        return False
    return True
