"""Integration coverage for the evaluator demo flow."""

from app.models.models import Event, Guest, Task, User, Vendor
from app.services.demo_seeder import _DEMO_EMAIL


def test_demo_load_seeds_once_and_sets_session_cookies(client, db):
    first = client.post("/api/demo/load")

    assert first.status_code == 200
    event_id = first.json()["event_id"]
    assert first.cookies.get("access_token")
    assert first.cookies.get("refresh_token")
    assert "httponly" in first.headers["set-cookie"].lower()

    second = client.post("/api/demo/load")

    assert second.status_code == 200
    assert second.json()["event_id"] == event_id
    assert db.query(User).filter(User.email == _DEMO_EMAIL).count() == 1
    assert db.query(Event).filter(Event.is_demo.is_(True)).count() == 1
    assert db.query(Task).filter(Task.event_id == event_id).count() > 0
    assert db.query(Vendor).filter(Vendor.event_id == event_id).count() > 0
    assert db.query(Guest).filter(Guest.event_id == event_id).count() > 0
