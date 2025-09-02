# auth.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from models import db, User

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        user = User.query.filter_by(username=username).first()
        if user and user.active and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for("dashboard"))
        # Deliberately vague error to avoid leaking which field failed
        flash("Invalid username or password", "danger")
    return render_template("login.html")

@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))

@auth_bp.route("/profile/password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        cur = request.form["current"]
        new1 = request.form["new1"]
        new2 = request.form["new2"]
        if not check_password_hash(current_user.password_hash, cur):
            flash("Current password is incorrect", "danger")
            return redirect(url_for("auth.change_password"))
        if new1 != new2 or len(new1) < 6:
            flash("New passwords must match and be at least 6 characters", "danger")
            return redirect(url_for("auth.change_password"))
        current_user.password_hash = generate_password_hash(new1)
        db.session.commit()
        flash("Password changed", "success")
        return redirect(url_for("dashboard"))
    return render_template("change_password.html")

    if request.method == "POST":
        cur = request.form["current"]
        new1 = request.form["new1"]
        new2 = request.form["new2"]
        if not check_password_hash(current_user.password_hash, cur):
            flash("Current password is incorrect", "danger")
            return redirect(url_for("auth.change_password"))
        if new1 != new2 or len(new1) < 6:
            flash("New passwords must match and be at least 6 chars", "danger")
            return redirect(url_for("auth.change_password"))
        current_user.password_hash = generate_password_hash(new1)
        db.session.commit()
        flash("Password changed", "success")
        return redirect(url_for("dashboard"))
    return render_template("change_password.html")