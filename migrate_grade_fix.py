# run in: flask shell
from app import create_app
from models import db

app = create_app()
with app.app_context():
    # --- Add columns if missing (SQLite allows simple ADD COLUMN) ---
    # student.current_grade
    try:
        db.session.execute(db.text("ALTER TABLE student ADD COLUMN current_grade TEXT"))
        print("Added student.current_grade")
    except Exception as e:
        print("student.current_grade maybe already exists:", e)

    # attendance.grade_at_time
    try:
        db.session.execute(db.text("ALTER TABLE attendance ADD COLUMN grade_at_time TEXT"))
        print("Added attendance.grade_at_time")
    except Exception as e:
        print("attendance.grade_at_time maybe already exists:", e)

    # --- Backfill: copy existing student.grade -> student.current_grade
    try:
        db.session.execute(db.text("""
            UPDATE student
               SET current_grade = COALESCE(current_grade, grade)
        """))
        print("Backfilled student.current_grade from student.grade")
    except Exception as e:
        print("Backfill for student.current_grade skipped:", e)

    # --- (Optional) Backfill grade_at_time for existing attendance from student.grade
    try:
        db.session.execute(db.text("""
            UPDATE attendance
               SET grade_at_time = (
                   SELECT grade FROM student
                   WHERE student.id = attendance.student_id
               )
             WHERE grade_at_time IS NULL
        """))
        print("Backfilled attendance.grade_at_time from student.grade")
    except Exception as e:
        print("Backfill for attendance.grade_at_time skipped:", e)

    db.session.commit()
    print("Migration complete.")
