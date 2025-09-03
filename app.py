import os
from flask import Flask, render_template, redirect, url_for
from flask_login import LoginManager, current_user, login_required
from werkzeug.security import generate_password_hash
from models import db, User
from config import Config
from auth import auth_bp
from admin import admin_bp
from teacher import teacher_bp
from sqlalchemy import text

def create_app():
    app = Flask(__name__, instance_relative_config=True, static_folder="static", template_folder="templates")
    app.config.from_object(Config)

    # Ensure instance dir exists (for SQLite)
    os.makedirs(app.instance_path, exist_ok=True)

    # SQLAlchemy
    db.init_app(app)

    # Login
    login_manager = LoginManager()
    login_manager.login_view = "auth.login"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(teacher_bp)

    # Simple dashboard
    @app.route("/")
    @login_required
    def dashboard():
        return render_template("dashboard.html", user=current_user)

    # CLI: init-db and create admin
    @app.cli.command("init-db")
    def init_db():
        with app.app_context():
            db.create_all()
            print("Initialized the database.")

    @app.cli.command("create-admin")
    def create_admin():
        with app.app_context():
            if not User.query.filter_by(username="admin").first():
                u = User(username="admin", role="admin",
                         password_hash=generate_password_hash("nimda"))
                db.session.add(u)
                db.session.commit()
                print("Created admin user: admin / nimda")
            else:
                print("Admin already exists.")

    @app.route("/reports")
    @login_required
    def reports_alias():
        # Reuse the admin.reports view; admin.before_request already allows it for any logged-in user
        return redirect(url_for("admin.reports"))

    @app.cli.command("upgrade-db")
    def upgrade_db():
        """Create new tables + add missing columns (SQLite-safe)."""
        # Ensure tables exist first
        db.create_all()

        engine = db.engine  # <- reliable in Flask-SQLAlchemy 3.x

        def has_col(table: str, col: str) -> bool:
            with engine.connect() as conn:
                rows = conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
                # row: (cid, name, type, notnull, dflt_value, pk)
                return any(r[1] == col for r in rows)

        # do schema changes in a transaction
        with engine.begin() as conn:
            # student.active
            if not has_col("student", "active"):
                conn.exec_driver_sql("ALTER TABLE student ADD COLUMN active BOOLEAN DEFAULT 1")

            # student.current_grade (also copy from old 'grade' if present)
            if not has_col("student", "current_grade"):
                conn.exec_driver_sql("ALTER TABLE student ADD COLUMN current_grade VARCHAR(10)")
                try:
                    # if an old 'grade' column exists, copy it
                    conn.exec_driver_sql("UPDATE student SET current_grade = grade WHERE current_grade IS NULL")
                except Exception:
                    pass

            # attendance.grade_at_time
            if not has_col("attendance", "grade_at_time"):
                conn.exec_driver_sql("ALTER TABLE attendance ADD COLUMN grade_at_time VARCHAR(10)")

            # attendance.school_year_id
            if not has_col("attendance", "school_year_id"):
                conn.exec_driver_sql("ALTER TABLE attendance ADD COLUMN school_year_id INTEGER")

        print("upgrade-db: schema updated")

    @app.cli.command("backfill-years")
    def backfill_years():
        """Set attendance.school_year_id based on date + SchoolYear ranges."""
        from models import Attendance, SchoolYear

        updated = 0
        for r in Attendance.query.filter(Attendance.school_year_id.is_(None)).all():
            sy = SchoolYear.query.filter(SchoolYear.start_date <= r.date,
                                         SchoolYear.end_date >= r.date).first()
            if sy:
                r.school_year_id = sy.id
                updated += 1
        db.session.commit()
        print(f"backfill-years: set year for {updated} attendance rows")

    return app
