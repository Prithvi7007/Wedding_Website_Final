"""Family seating uses isolated test records, never the production guest list."""
from datetime import date, time
import csv
from io import StringIO
import re

import pytest

from app.extensions import db
from app.models import AdminAuditLog, Event, Invitation, InvitationEventPermission, RSVP

TOKEN = "seating-test-shared-guest-link-long-enough-001"
BASE = f"/photos/{TOKEN}"


def login(client, user="prithvi"):
    passwords = {"prithvi": "test-admin-password-for-testing",
                 "adlin_fam": "test-adlin-family-password"}
    assert client.post("/admin/login", data={"username": user, "password": passwords[user]}).status_code == 302


@pytest.fixture()
def seating_data(app, tmp_path):
    root = tmp_path / "photos"
    (root / "files").mkdir(parents=True)
    (root / "metadata").mkdir()
    app.config.update(PUBLIC_BASE_URL="http://localhost", WEDDING_PHOTO_SHARE_TOKEN=TOKEN,
                      WEDDING_PHOTO_ENABLED=True, WEDDING_PHOTO_GALLERY_ENABLED=True,
                      WEDDING_PHOTO_BACKEND="local", WEDDING_PHOTO_STORAGE_DIR=str(root))
    with app.app_context():
        db.session.add_all([Event(event_id=e, title=t, event_date=date(2026, 11, 21),
                                  start_time=time(18), end_time=time(22), location="Tampa")
                            for e, t in [("reception", "Reception"), ("haldi", "Haldi")]])
        families = [Invitation(first_name="María", last_name="Alvarez", partner_name="José Alvarez",
                               display_name="Alvarez Family", invite_token="private-alvarez-invitation-token",
                               email="private-contact@example.test", phone="555-private", is_active=True),
                    Invitation(first_name="Alex", last_name="Brown", display_name="Brown Family",
                               invite_token="private-brown-invitation-token", is_active=True),
                    Invitation(first_name="Hidden", display_name="Inactive Family",
                               invite_token="private-inactive-token", is_active=False),
                    Invitation(first_name="Unknown", display_name="Uninvited Family",
                               invite_token="private-uninvited-token", is_active=True)]
        db.session.add_all(families); db.session.flush()
        ids = [item.invitation_id for item in families]
        db.session.add_all([InvitationEventPermission(invitation_id=i, event_id="reception", max_guests=n)
                            for i, n in zip(ids[:3], [5, 2, 2])])
        db.session.add(InvitationEventPermission(invitation_id=ids[1], event_id="haldi", max_guests=2))
        db.session.add(RSVP(invitation_id=ids[0], event_id="reception", attending="Yes", guest_count=3,
                            notes="private RSVP information"))
        db.session.commit()
    return ids


def create_table(client, app, *, event="reception", name="Table 7", capacity="4"):
    response = client.post("/admin/seating/tables", data={"event_id": event, "name": name, "capacity": capacity})
    assert response.status_code == 303
    from app.models import SeatingTable
    with app.app_context():
        return db.session.scalar(db.select(SeatingTable.table_id).where(
            SeatingTable.event_id == event, SeatingTable.name == name))


def assign(client, ids, table_id, event="reception"):
    return client.post("/admin/seating/assign", data={"event_id": event,
                       "invitation_ids": [str(i) for i in ids], "table_id": str(table_id) if table_id else ""})


def test_shared_hub_links_seating_and_existing_photo_features(client, seating_data):
    response = client.get(BASE + "/welcome")
    assert response.status_code == 200
    assert (BASE + "/seating").encode() in response.data
    assert (BASE + "/gallery").encode() in response.data
    assert b"Find your table" in response.data and b"Share photos" in response.data
    assert b"Alvarez Family" not in response.data
    assert response.headers["Cache-Control"].startswith("private, no-store")
    assert response.headers["X-Robots-Tag"].startswith("noindex")
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert client.get("/photos/wrong-seating-token-that-is-long/welcome").status_code == 404


def test_seating_is_independent_of_photo_switches(client, app, seating_data):
    app.config.update(WEDDING_PHOTO_ENABLED=False, WEDDING_PHOTO_GALLERY_ENABLED=False)
    assert client.get(BASE + "/welcome").status_code == 200
    page = client.get(BASE + "/seating")
    assert page.status_code == 200
    assert b"seating" in page.data.lower()
    assert client.get("/photos/wrong-seating-token-that-is-long/seating").status_code == 404


def test_host_assignment_is_immediately_discoverable_by_family_or_partner(client, app, seating_data):
    login(client)
    table_id = create_table(client, app)
    assert assign(client, [seating_data[0]], table_id).status_code == 303
    for name in ["alvarez", "MARIA", "jose", "María Alvarez"]:
        response = client.get(BASE + "/seating", query_string={"event": "reception", "q": name})
        assert response.status_code == 200
        assert b"Alvarez Family" in response.data and b"Table 7" in response.data
        for private in [b"private-contact", b"555-private", b"private-alvarez-invitation-token",
                        b"private RSVP", b'"invitation_id"']:
            assert private not in response.data
    blank = client.get(BASE + "/seating?event=reception")
    assert b"Alvarez Family" not in blank.data


def test_moves_unassignment_table_edit_delete_and_audit(client, app, seating_data):
    login(client)
    first = create_table(client, app)
    second = create_table(client, app, name="Garden", capacity="")
    assert assign(client, seating_data[:2], first).status_code == 303
    assert assign(client, [seating_data[0]], second).status_code == 303
    assert client.post(f"/admin/seating/tables/{second}/update",
                       data={"name": "Orchid", "capacity": "10"}).status_code == 303
    page = client.get(BASE + "/seating?q=alvarez&event=reception")
    assert b"Orchid" in page.data
    assert assign(client, [seating_data[0]], None).status_code == 303
    page = client.get(BASE + "/seating?q=alvarez&event=reception")
    assert b"assignment is coming" in page.data.lower()
    assert client.post(f"/admin/seating/tables/{first}/delete").status_code == 303
    from app.models import SeatingAssignment, SeatingTable
    with app.app_context():
        assert db.session.get(SeatingAssignment, (seating_data[1], "reception")) is None
        assert db.session.get(SeatingTable, first) is None
        audits = db.session.scalars(db.select(AdminAuditLog).where(AdminAuditLog.action.like("seating.%"))).all()
        assert {a.action for a in audits} >= {"seating.table.create", "seating.table.update",
                                             "seating.table.delete", "seating.assignment.update"}
        assert all(a.details["actor_username"] == "prithvi" for a in audits)
    assert client.get("/admin/audit").status_code == 200


def test_event_isolation_and_invalid_bulk_selection_are_atomic(client, app, seating_data):
    login(client)
    reception = create_table(client, app)
    haldi = create_table(client, app, event="haldi", name="Haldi VIP")
    assert assign(client, [seating_data[1]], reception).status_code == 303
    assert assign(client, [seating_data[1]], haldi, "haldi").status_code == 303
    assert assign(client, [seating_data[0]], haldi).status_code == 400
    for invalid in [seating_data[2], seating_data[3], 999999]:
        assert assign(client, [seating_data[0], invalid], reception).status_code == 400
    from app.models import SeatingAssignment
    with app.app_context():
        assert db.session.get(SeatingAssignment, (seating_data[0], "reception")) is None
        assert db.session.get(SeatingAssignment, (seating_data[1], "reception")).table_id == reception
        assert db.session.get(SeatingAssignment, (seating_data[1], "haldi")).table_id == haldi
    assert b"Alvarez Family" not in client.get(BASE + "/seating?event=haldi&q=alvarez").data


@pytest.mark.parametrize("removed", ["active", "permission"])
def test_ineligible_saved_assignments_hide_and_restore(client, app, seating_data, removed):
    login(client)
    table_id = create_table(client, app)
    assert assign(client, [seating_data[0]], table_id).status_code == 303
    with app.app_context():
        if removed == "active":
            db.session.get(Invitation, seating_data[0]).is_active = False
        else:
            db.session.delete(db.session.get(InvitationEventPermission, (seating_data[0], "reception")))
        db.session.commit()
    assert b"Alvarez Family" not in client.get(BASE + "/seating?q=alvarez&event=reception").data
    from app.models import SeatingAssignment
    from app.seating.services import table_summaries
    with app.app_context():
        assert db.session.get(SeatingAssignment, (seating_data[0], "reception")) is not None
        assert table_summaries("reception")[0]["planned_count"] == 0
        if removed == "active":
            db.session.get(Invitation, seating_data[0]).is_active = True
        else:
            db.session.add(InvitationEventPermission(invitation_id=seating_data[0], event_id="reception", max_guests=5))
        db.session.commit()
    assert b"Table 7" in client.get(BASE + "/seating?q=alvarez&event=reception").data


def test_capacity_warns_without_blocking_and_counts_follow_rsvps(client, app, seating_data):
    login(client)
    table_id = create_table(client, app, capacity="4")
    assert assign(client, seating_data[:2], table_id).status_code == 303
    from app.seating.services import table_summaries
    with app.app_context():
        summary = table_summaries("reception")[0]
        assert (summary["planned_count"], summary["estimated_count"], summary["over_capacity"]) == (5, 2, True)
        db.session.scalar(db.select(RSVP).where(RSVP.invitation_id == seating_data[0])).guest_count = 1
        db.session.commit()
        summary = table_summaries("reception")[0]
        assert (summary["planned_count"], summary["estimated_count"], summary["over_capacity"]) == (3, 2, False)


def test_table_validation_and_csv_formula_protection(client, app, seating_data):
    login(client)
    create_table(client, app, name="Table 7", capacity="0")
    assert client.post("/admin/seating/tables", data={"event_id": "reception", "name": "table 7"}).status_code == 400
    for capacity in ["-1", "bad"]:
        assert client.post("/admin/seating/tables", data={"event_id": "reception", "name": "Other", "capacity": capacity}).status_code == 400
    with app.app_context():
        db.session.get(Invitation, seating_data[0]).display_name = " \t=SUM(1,2)"
        db.session.commit()
    response = client.get("/admin/seating/export.csv?event=reception")
    assert response.status_code == 200
    rows = list(csv.reader(StringIO(response.get_data(as_text=True))))
    assert any(row[0].startswith("' \t=SUM") for row in rows[1:])
    assert "private" not in response.get_data(as_text=True)


def test_matching_names_are_paginated_without_a_total_cutoff(client, app, seating_data):
    login(client)
    create_table(client, app)
    with app.app_context():
        for n in range(30):
            inv = Invitation(first_name=f"Person {n}", last_name="Rivera", display_name=f"Rivera Family {n:02}",
                             invite_token=f"private-rivera-{n}", is_active=True)
            db.session.add(inv); db.session.flush()
            db.session.add(InvitationEventPermission(invitation_id=inv.invitation_id, event_id="reception", max_guests=1))
        db.session.commit()
    first = client.get(BASE + "/seating?q=rivera&event=reception&page=1")
    second = client.get(BASE + "/seating?q=rivera&event=reception&page=2")
    assert first.status_code == second.status_code == 200
    assert b"Rivera Family 00" in first.data and b"Rivera Family 29" in second.data
    assert b"Next" in first.data


def test_existing_roles_protect_seating_writes(client, app, seating_data):
    assert client.get("/admin/seating").status_code == 302
    login(client, "adlin_fam")
    assert client.get("/admin/seating?event=reception").status_code == 200
    assert client.post("/admin/seating/tables", data={"event_id": "reception", "name": "Denied"}).status_code == 302


def test_strict_https_csrf_protects_seating_writes(client, app, seating_data):
    login(client)
    app.config.update(WTF_CSRF_ENABLED=True, WTF_CSRF_SSL_STRICT=True, PUBLIC_BASE_URL="https://localhost", SESSION_COOKIE_SECURE=True)
    page = client.get("/admin/seating?event=reception", base_url="https://localhost")
    token = re.search(rb'name="csrf_token" value="([^"]+)"', page.data).group(1).decode()
    payload = {"event_id": "reception", "name": "Secure Table", "csrf_token": token}
    assert client.post("/admin/seating/tables", base_url="https://localhost", data=payload).status_code == 400
    assert client.post("/admin/seating/tables", base_url="https://localhost", data=payload,
                       headers={"Referer": "https://localhost/admin/seating"}).status_code == 303


def test_missing_schema_is_graceful_and_photo_routes_continue(client, app, seating_data):
    login(client)
    assert client.get("/admin/seating").status_code == 200
    from app.models import SeatingAssignment, SeatingTable
    with app.app_context():
        SeatingAssignment.__table__.drop(db.engine)
        SeatingTable.__table__.drop(db.engine)
    assert client.get("/admin/seating").status_code == 503
    assert client.get(BASE + "/seating").status_code == 503
    assert client.get(BASE + "/welcome").status_code == 200
    assert client.get(BASE).status_code == 200


def test_guest_navigation_and_shared_qr_are_available(client, seating_data):
    page = client.get(BASE)
    assert (BASE + "/welcome").encode() in page.data
    assert (BASE + "/seating").encode() in page.data
    login(client)
    pytest.importorskip("qrcode")
    assert client.get("/admin/seating/qr.svg").status_code == 200
    admin = client.get("/admin/photos")
    assert (BASE + "/welcome").encode() in admin.data


def test_guest_results_escape_host_labels_and_never_search_contact_fields(client, app, seating_data):
    login(client)
    table_id = create_table(client, app, name='<script>alert("table")</script>')
    assert assign(client, [seating_data[0]], table_id).status_code == 303
    page = client.get(BASE + "/seating?q=alvarez&event=reception")
    assert b"&lt;script&gt;" in page.data
    assert b'<script>alert("table")</script>' not in page.data
    assert b"Alvarez Family" not in client.get(BASE + "/seating?q=private-contact&event=reception").data
    assert client.get("/photos/%C3%A9-invalid-token/seating").status_code == 404


def test_database_rejects_an_assignment_to_another_events_table(client, app, seating_data):
    from sqlalchemy.exc import IntegrityError
    from app.models import SeatingAssignment
    login(client)
    table_id = create_table(client, app, event="haldi", name="Haldi table")
    with app.app_context():
        db.session.connection().exec_driver_sql("PRAGMA foreign_keys=ON")
        db.session.add(SeatingAssignment(invitation_id=seating_data[0], event_id="reception",
                                        table_id=table_id, updated_by="test"))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_seating_schema_setup_is_additive_and_idempotent(app, seating_data):
    from app.models import SeatingAssignment, SeatingTable
    from sqlalchemy import func
    with app.app_context():
        before = [db.session.scalar(db.select(func.count()).select_from(model))
                  for model in (Invitation, Event, RSVP)]
        db.session.commit()
        SeatingAssignment.__table__.drop(db.engine)
        SeatingTable.__table__.drop(db.engine)
        from scripts.apply_seating_schema import apply_schema
        assert set(apply_schema(db.engine)) == {"seating_tables", "seating_assignments"}
        assert apply_schema(db.engine) == []
        assert before == [db.session.scalar(db.select(func.count()).select_from(model))
                          for model in (Invitation, Event, RSVP)]


def test_malformed_existing_seating_schema_is_not_silently_accepted(app, seating_data):
    from app.models import SeatingAssignment, SeatingTable
    from sqlalchemy import inspect
    with app.app_context():
        SeatingAssignment.__table__.drop(db.engine)
        SeatingTable.__table__.drop(db.engine)
        with db.engine.begin() as conn:
            conn.exec_driver_sql("CREATE TABLE seating_tables (table_id INTEGER PRIMARY KEY)")
        from scripts.apply_seating_schema import apply_schema
        with pytest.raises(RuntimeError, match="schema"):
            apply_schema(db.engine)
        assert not inspect(db.engine).has_table("seating_assignments")


@pytest.mark.parametrize("expression", ["capacity", "event_id, lower(capacity)", "event_id, lower(name)) WHERE capacity > 0 --"])
def test_schema_rejects_a_misdefined_unique_name_index(app, seating_data, expression):
    from scripts.apply_seating_schema import apply_schema
    with app.app_context():
        with db.engine.begin() as conn:
            conn.exec_driver_sql("DROP INDEX seating_tables_event_name_key")
            conn.exec_driver_sql(f"CREATE UNIQUE INDEX seating_tables_event_name_key ON seating_tables ({expression})")
        with pytest.raises(RuntimeError, match="schema"):
            apply_schema(db.engine)
