from __future__ import annotations

from flask import session

from app.models import Invitation
from app.repositories import InvitationRepository


SESSION_INVITATION_ID = "invitation_id"


def establish_invitation_session(invitation: Invitation) -> None:
    session.clear()
    session.permanent = True
    session[SESSION_INVITATION_ID] = invitation.invitation_id


def current_invitation() -> Invitation | None:
    invitation_id = session.get(SESSION_INVITATION_ID)
    if invitation_id is None:
        return None

    try:
        normalized_id = int(invitation_id)
    except (TypeError, ValueError):
        session.clear()
        return None

    invitation = InvitationRepository.get_active_by_id(normalized_id)
    if invitation is None:
        session.clear()

    return invitation
