from __future__ import annotations

import hashlib
import hmac

from flask import current_app, session

from app.models import Invitation
from app.repositories import InvitationRepository


SESSION_INVITATION_ID = "invitation_id"
SESSION_INVITATION_BINDING = "invitation_token_binding"


def _invitation_binding(invitation: Invitation) -> str:
    """Bind a guest session to the current private link, without storing it.

    Flask's session cookie is signed but is not encrypted. A keyed digest
    prevents the invite token itself from appearing in the browser cookie.
    """
    secret_key = current_app.config["SECRET_KEY"]
    key = secret_key.encode("utf-8") if isinstance(secret_key, str) else secret_key
    return hmac.new(
        key,
        invitation.invite_token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def establish_invitation_session(invitation: Invitation) -> None:
    session.clear()
    session.permanent = True
    session[SESSION_INVITATION_ID] = invitation.invitation_id
    session[SESSION_INVITATION_BINDING] = _invitation_binding(invitation)


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
    stored_binding = session.get(SESSION_INVITATION_BINDING)
    if (
        invitation is None
        or not isinstance(stored_binding, str)
        or not hmac.compare_digest(
            stored_binding,
            _invitation_binding(invitation),
        )
    ):
        # A rotated link, deactivated invitation or legacy session loses
        # guest access immediately, including all AJAX and calendar routes.
        session.clear()
        return None

    return invitation
