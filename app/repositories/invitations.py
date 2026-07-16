from __future__ import annotations

from sqlalchemy import select

from app.extensions import db
from app.models import Invitation


class InvitationRepository:
    @staticmethod
    def get_active_by_token(invite_token: str) -> Invitation | None:
        statement = select(Invitation).where(
            Invitation.invite_token == invite_token,
            Invitation.is_active.is_(True),
        )
        return db.session.scalar(statement)

    @staticmethod
    def get_active_by_id(invitation_id: int) -> Invitation | None:
        statement = select(Invitation).where(
            Invitation.invitation_id == invitation_id,
            Invitation.is_active.is_(True),
        )
        return db.session.scalar(statement)
