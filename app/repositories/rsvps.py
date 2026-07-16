from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.extensions import db
from app.models import RSVP


class RSVPRepository:
    @staticmethod
    def saved_for_invitation(invitation_id: int) -> dict[str, RSVP]:
        statement = select(RSVP).where(RSVP.invitation_id == invitation_id)
        records = db.session.scalars(statement).all()
        return {record.event_id: record for record in records}

    @staticmethod
    def get_for_event(invitation_id: int, event_id: str) -> RSVP | None:
        statement = select(RSVP).where(
            RSVP.invitation_id == invitation_id,
            RSVP.event_id == event_id,
        )
        return db.session.scalar(statement)

    @staticmethod
    def save(
        *,
        invitation_id: int,
        event_id: str,
        attending: str,
        guest_count: int,
        notes: str,
    ) -> RSVP:
        record = RSVPRepository.get_for_event(invitation_id, event_id)
        if record is None:
            record = RSVP(
                invitation_id=invitation_id,
                event_id=event_id,
                attending=attending,
                guest_count=guest_count,
                notes=notes,
            )
            db.session.add(record)
        else:
            record.attending = attending
            record.guest_count = guest_count
            record.notes = notes
            record.updated_at = datetime.now()

        db.session.commit()
        return record
