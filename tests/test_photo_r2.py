"""R2 wedding photo tests using a credential-free in-memory S3 test double."""
from io import BytesIO
import json

import pytest

Image = pytest.importorskip("PIL.Image", reason="CI installs Pillow")

from app.photos import r2


TOKEN = "test-r2-photo-qr-token-private-long-enough-001"
PATH = f"/photos/{TOKEN}"


class MissingRemoteObject(Exception):
    response = {"Error": {"Code": "NoSuchKey"}}


class FakeR2Client:
    def __init__(self):
        self.objects = {}
        self.fail_next_photo = False

    def put_object(self, *, Bucket, Key, Body, **kwargs):
        assert Bucket == "adlin-prithvi-private-photos"
        assert Key.startswith("wedding/")
        if self.fail_next_photo and Key.startswith("wedding/photos/"):
            self.fail_next_photo = False
            raise RuntimeError("simulated R2 write outage")
        self.objects[Key] = bytes(Body)
        return {"ETag": '"test"'}

    def get_object(self, *, Bucket, Key):
        if Key not in self.objects:
            raise MissingRemoteObject()
        return {"Body": BytesIO(self.objects[Key])}

    def delete_object(self, *, Bucket, Key):
        self.objects.pop(Key, None)
        return {}


@pytest.fixture()
def cloud_storage(app, tmp_path, monkeypatch):
    root = tmp_path / "private-photo-records"
    (root / "metadata").mkdir(parents=True)
    fake = FakeR2Client()
    app.config.update(
        WEDDING_PHOTO_BACKEND="r2",
        WEDDING_PHOTO_ENABLED=True,
        WEDDING_PHOTO_GALLERY_ENABLED=True,
        WEDDING_PHOTO_STORAGE_DIR=str(root),
        WEDDING_PHOTO_SHARE_TOKEN=TOKEN,
        PUBLIC_BASE_URL="http://localhost",
        WEDDING_R2_ACCOUNT_ID="a" * 32,
        WEDDING_R2_BUCKET="adlin-prithvi-private-photos",
        WEDDING_R2_ACCESS_KEY_ID="mock-access-key-id",
        WEDDING_R2_SECRET_ACCESS_KEY="mock-secret-access-key",
    )
    monkeypatch.setattr(r2, "_client", lambda: fake)
    return root, fake


def jpeg():
    out = BytesIO()
    Image.new("RGB", (500, 300), color=(119, 77, 45)).save(out, "JPEG")
    out.seek(0)
    return out


def upload(client):
    return client.post(PATH, data={
        "guest_name": "Photographer",
        "moment": "Reception",
        "gallery_consent": "yes",
        "photos": (jpeg(), "party.jpg"),
    }, content_type="multipart/form-data")


def host_login(client):
    result = client.post("/admin/login", data={
        "username": "prithvi", "password": "test-admin-password-for-testing",
    })
    assert result.status_code == 302


def test_r2_shares_on_upload_and_respects_host_visibility_changes(client, cloud_storage):
    root, fake = cloud_storage
    assert client.get(PATH).status_code == 200
    assert upload(client).status_code == 303
    records = list((root / "metadata").glob("*.json"))
    assert len(records) == 1
    photo_id = records[0].stem
    assert not (root / "files").exists()
    assert f"wedding/photos/{photo_id}.jpg" in fake.objects
    assert f"wedding/metadata/{photo_id}.json" in fake.objects
    with Image.open(BytesIO(fake.objects[f"wedding/photos/{photo_id}.jpg"])) as image:
        assert image.getexif() == {}
    image_path = f"{PATH}/gallery/{photo_id}.jpg"
    mirrored = json.loads(fake.objects[f"wedding/metadata/{photo_id}.json"])
    assert mirrored["status"] == "approved"
    assert mirrored["published_at"]
    assert mirrored["gallery_consent"] is True
    host_login(client)
    result = client.get(image_path)
    assert result.status_code == 200
    assert result.mimetype == "image/jpeg"
    assert result.headers["Cache-Control"].startswith("private, no-store")
    assert client.post(f"/admin/photos/{photo_id}/hide").status_code == 302
    assert client.get(image_path).status_code == 404
    assert client.post(f"/admin/photos/{photo_id}/show").status_code == 302
    assert client.get(image_path).status_code == 200
    assert client.post(f"/admin/photos/{photo_id}/delete").status_code == 302
    assert f"wedding/photos/{photo_id}.jpg" not in fake.objects
    assert client.get(image_path).status_code == 404
    assert json.loads(fake.objects[f"wedding/metadata/{photo_id}.json"])["status"] == "deleted"


def test_invalid_r2_configuration_is_fail_closed(client, app, cloud_storage):
    app.config["WEDDING_R2_ACCESS_KEY_ID"] = ""
    assert client.get(PATH).status_code == 404
    assert client.get(PATH + "/gallery").status_code == 404
    app.config["WEDDING_R2_ACCESS_KEY_ID"] = "mock-access-key-id"
    app.config["WEDDING_R2_ACCOUNT_ID"] = "untrusted/endpoint"
    assert client.get(PATH).status_code == 404


def test_cloud_outage_does_not_claim_upload_succeeded(client, cloud_storage):
    root, fake = cloud_storage
    fake.fail_next_photo = True
    result = client.post(PATH, data={
        "gallery_consent": "yes", "moment": "Reception",
        "photos": (jpeg(), "photo.jpg"),
    }, content_type="multipart/form-data", headers={"Accept": "application/json"})
    assert result.status_code == 503
    assert result.json["success"] is False
    assert not list((root / "metadata").glob("*.json"))
    assert not any(key.startswith("wedding/photos/") for key in fake.objects)


def test_missing_remote_photo_returns_404(client, cloud_storage):
    root, fake = cloud_storage
    assert upload(client).status_code == 303
    photo_id = next((root / "metadata").glob("*.json")).stem
    host_login(client)
    fake.objects.pop(f"wedding/photos/{photo_id}.jpg")
    assert client.get(f"{PATH}/gallery/{photo_id}.jpg").status_code == 404


def test_bad_photo_identifier_does_not_access_remote_objects(client, cloud_storage):
    root, fake = cloud_storage
    assert client.get(f"{PATH}/gallery/../../bad.jpg").status_code in (404, 308)
    assert not fake.objects


def test_second_cloud_write_failure_rolls_back_the_entire_shared_batch(client, cloud_storage, monkeypatch):
    root, fake = cloud_storage
    original_put = fake.put_object
    photo_writes = 0

    def fail_second_photo(**kwargs):
        nonlocal photo_writes
        if kwargs["Key"].startswith("wedding/photos/"):
            photo_writes += 1
            if photo_writes == 2:
                raise RuntimeError("second photo write failed")
        return original_put(**kwargs)

    monkeypatch.setattr(fake, "put_object", fail_second_photo)
    result = client.post(PATH, data={
        "gallery_consent": "yes", "moment": "Reception",
        "photos": [(jpeg(), "one.jpg"), (jpeg(), "two.jpg")],
    }, content_type="multipart/form-data", headers={"Accept": "application/json"})
    assert result.status_code == 503
    assert result.json["success"] is False
    assert not list((root / "metadata").glob("*.json"))
    assert fake.objects == {}
    assert b"photo-gallery-photo" not in client.get(PATH + "/gallery").data


@pytest.mark.parametrize("view", ["gallery", "image"])
def test_guest_read_waits_for_failed_batch_rollback(app, cloud_storage, monkeypatch, view):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    root, fake = cloud_storage
    second_write = Event()
    allow_failure = Event()
    reader_started = Event()
    original_put = fake.put_object
    photo_writes = 0

    def pause_then_fail_second_photo(**kwargs):
        nonlocal photo_writes
        if kwargs["Key"].startswith("wedding/photos/"):
            photo_writes += 1
            if photo_writes == 2:
                second_write.set()
                assert allow_failure.wait(5)
                raise RuntimeError("second photo write failed")
        return original_put(**kwargs)

    monkeypatch.setattr(fake, "put_object", pause_then_fail_second_photo)

    def batch_upload():
        with app.test_client() as guest:
            return guest.post(PATH, data={
                "gallery_consent": "yes", "moment": "Reception",
                "photos": [(jpeg(), "one.jpg"), (jpeg(), "two.jpg")],
            }, content_type="multipart/form-data")

    def read_gallery():
        with app.test_client() as guest:
            reader_started.set()
            suffix = "/gallery" if view == "gallery" else f"/gallery/{first_id}.jpg"
            return guest.get(PATH + suffix)

    with ThreadPoolExecutor(max_workers=2) as pool:
        writer = pool.submit(batch_upload)
        try:
            assert second_write.wait(5)
            first_id = next((root / "metadata").glob("*.json")).stem
            reader = pool.submit(read_gallery)
            assert reader_started.wait(5)
            # Confirm that an in-flight batch cannot be observed, even though
            # its first metadata record already exists on disk.
            from concurrent.futures import TimeoutError
            with pytest.raises(TimeoutError):
                reader.result(timeout=0.2)
        finally:
            allow_failure.set()
        assert writer.result(timeout=5).status_code == 503
        gallery = reader.result(timeout=5)
    assert gallery.status_code == (200 if view == "gallery" else 404)
    assert first_id.encode() not in gallery.data
    assert fake.objects == {}
