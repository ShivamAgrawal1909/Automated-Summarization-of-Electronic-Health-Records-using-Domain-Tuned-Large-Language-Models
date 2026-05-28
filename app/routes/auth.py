from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user
from sqlalchemy import select

from app import db
from app.models import User

bp = Blueprint("auth", __name__)


def _home_for_user(u: User):
    if u.role == "admin":
        return url_for("admin.dashboard")
    return url_for("user.dashboard")


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(_home_for_user(current_user))
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        phone = (request.form.get("phone") or "").strip()
        password = request.form.get("password") or ""
        designation = (request.form.get("role") or "clinician").strip()[:80]
        if not name or not email or not password:
            flash("Name, email, and password are required.", "error")
            return render_template("auth_register.html")
        existing = db.session.scalar(select(User).where(User.email == email))
        if existing:
            flash("An account with this email already exists.", "error")
            return render_template("auth_register.html")
        u = User(
            name=name,
            email=email,
            phone=phone,
            role="user",
            designation=designation,
        )
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        flash("Registration successful. You can sign in now.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth_register.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(_home_for_user(current_user))
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        user = db.session.scalar(select(User).where(User.email == email))
        if not user or not user.check_password(password):
            flash("Invalid email or password.", "error")
            return render_template("auth_login.html")
        if user.is_blocked:
            flash("Your account is blocked. Contact an administrator.", "error")
            return render_template("auth_login.html")
        login_user(user, remember=True)
        flash("Welcome back.", "success")
        next_url = request.args.get("next")
        if next_url and next_url.startswith("/"):
            return redirect(next_url)
        return redirect(_home_for_user(user))
    return render_template("auth_login.html")


@bp.route("/logout")
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("main.index"))

