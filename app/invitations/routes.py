from flask import Blueprint, redirect, render_template, session, url_for

from app.repositories import InvitationRepository
from app.services import establish_invitation_session


invitations_bp = Blueprint("invitations", __name__)


@invitations_bp.get("/")
def home():
    return render_template("invitation/home.html")


@invitations_bp.get("/invite/<invite_token>")
def open_invitation(invite_token: str):
    invitation = InvitationRepository.get_active_by_token(invite_token)

    if invitation is None:
        return render_template("invitation/invalid.html"), 404

    establish_invitation_session(invitation)
    return redirect(url_for("dashboard.shell", login="success"))


@invitations_bp.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("invitations.home"))
