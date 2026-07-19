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

    # A private link must always stop on its invitation landing page first.
    # Do not let a previously authenticated invitation bypass this screen.
    session.pop("invitation_id", None)

    return render_template(
        "invitation/open.html",
        invitation=invitation,
        invite_token=invite_token,
    )


@invitations_bp.post("/invite/<invite_token>/open")
def enter_invitation(invite_token: str):
    invitation = InvitationRepository.get_active_by_token(invite_token)

    if invitation is None:
        return render_template("invitation/invalid.html"), 404

    establish_invitation_session(invitation)

    return redirect(
        url_for(
            "dashboard.shell",
            tab="welcome",
            login="success",
        )
    )


@invitations_bp.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("invitations.home"))
