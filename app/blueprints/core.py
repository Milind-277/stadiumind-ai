"""app/blueprints/core.py — Landing page and role selection."""
from flask import Blueprint, render_template, redirect, url_for, session, request, jsonify
from app.middleware.role_guard import VALID_ROLES

bp = Blueprint("core", __name__)


@bp.route("/")
def landing():
    """Landing page — role selector."""
    current_role = session.get("role")
    if current_role in VALID_ROLES:
        return redirect(url_for(f"{current_role}.index"))
    return render_template("landing.html")


@bp.route("/select-role", methods=["POST"])
def select_role():
    """Set role in signed session cookie and redirect to persona home."""
    role = request.form.get("role", "").strip().lower()
    if role not in VALID_ROLES:
        return render_template("landing.html", error="Invalid role selected."), 400
    session["role"] = role
    session.permanent = False
    return redirect(url_for(f"{role}.index"))


@bp.route("/switch-role")
def switch_role():
    """Clear session and return to landing page."""
    session.clear()
    return redirect(url_for("core.landing"))


@bp.route("/health")
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok", "service": "StadiumMind AI"}), 200
