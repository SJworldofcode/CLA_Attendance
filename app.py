import os
from flask import Flask, render_template, redirect, url_for
from flask_login import LoginManager, current_user, login_required
from werkzeug.security import generate_password_hash
from models import db, User
from config import Config
from auth import auth_bp
from admin import admin_bp
from teacher import teacher_bp

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

    return app
