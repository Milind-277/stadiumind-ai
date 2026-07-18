"""
app/blueprints/core.py — Landing page, role selection, and health check.

Responsibilities:
    * Render the landing page and auto-redirect already-authenticated users.
    * Accept the role-selection form POST and write the role to the session.
    * Provide a ``/switch-role`` route that clears the session.
    * Expose a ``/health`` endpoint for load-balancer / uptime monitoring.
"""

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

from app.constants import ALL_ROLES, SESSION_ROLE_KEY

bp = Blueprint("core", __name__)


# ── Page Routes ────────────────────────────────────────────────────────────────


@bp.route("/")
def landing():
    """Landing page — renders the role selector.

    If the session already contains a valid role the user is redirected directly
    to their persona dashboard, avoiding an unnecessary landing-page round-trip.
    """
    current_role = session.get(SESSION_ROLE_KEY)
    if current_role in ALL_ROLES:
        return redirect(url_for(f"{current_role}.index"))
    return render_template("landing.html")


@bp.route("/select-role", methods=["POST"])
def select_role():
    """Write the chosen role to a signed session cookie, then redirect.

    Returns:
        A redirect to the selected persona's dashboard (HTTP 302), or a
        400 response if the submitted role is not in :data:`ALL_ROLES`.
    """
    role = request.form.get("role", "").strip().lower()
    if role not in ALL_ROLES:
        return render_template("landing.html", error="Invalid role selected."), 400
    session[SESSION_ROLE_KEY] = role
    session.permanent = False
    return redirect(url_for(f"{role}.index"))


@bp.route("/switch-role")
def switch_role():
    """Clear the session and return to the landing page.

    Allows a user to switch persona without closing the browser.
    """
    session.clear()
    return redirect(url_for("core.landing"))


# ── Utility Routes ─────────────────────────────────────────────────────────────


@bp.route("/health")
def health():
    """Health check endpoint consumed by load balancers and uptime monitors.

    Returns:
        JSON ``{"status": "ok", "service": "StadiumMind AI"}`` with HTTP 200.
    """
    return jsonify({"status": "ok", "service": "StadiumMind AI"}), 200
