from __future__ import annotations

from sqlalchemy import func, select

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
        # PostgreSQL's ON CONFLICT turns two simultaneous first responses
        # into one durable RSVP rather than a duplicate-key error. SQLite
        # supports the same statement in our disposable test database.
        dialect = db.session.get_bind().dialect.name
        if dialect == "postgresql":
            from sqlalchemy.dialects.postgresql import insert
        elif dialect == "sqlite":
            from sqlalchemy.dialects.sqlite import insert
        else:
            raise RuntimeError(f"Unsupported RSVP database dialect: {dialect}")

        statement = insert(RSVP).values(
            invitation_id=invitation_id,
            event_id=event_id,
            attending=attending,
            guest_count=guest_count,
            notes=notes,
        )
        statement = statement.on_conflict_do_update(
            index_elements=[RSVP.invitation_id, RSVP.event_id],
            set_={
                "attending": statement.excluded.attending,
                "guest_count": statement.excluded.guest_count,
                "notes": statement.excluded.notes,
                "updated_at": func.current_timestamp(),
            },
        )
        # RETURNING gives the saved row without a second query after commit.
        # Refresh a previously loaded ORM instance if the RSVP was updated.
        saved = db.session.scalar(
            statement.returning(RSVP).execution_options(populate_existing=True)
        )
        if saved is None:
            raise RuntimeError("The RSVP upsert returned no saved row.")
        db.session.commit()
        return saved
