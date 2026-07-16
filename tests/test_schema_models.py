from app.models import Event, Invitation, InvitationEventPermission, RSVP


def test_table_names_match_production_schema():
    assert Invitation.__tablename__ == "invitations"
    assert Event.__tablename__ == "events"
    assert InvitationEventPermission.__tablename__ == "invitation_event_permissions"
    assert RSVP.__tablename__ == "rsvps"


def test_composite_permission_key_matches_production_schema():
    primary_keys = {column.name for column in InvitationEventPermission.__table__.primary_key}
    assert primary_keys == {"invitation_id", "event_id"}


def test_rsvp_unique_key_matches_production_schema():
    unique_sets = {
        tuple(constraint.columns.keys())
        for constraint in RSVP.__table__.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert ("invitation_id", "event_id") in unique_sets
