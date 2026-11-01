"""Authorization matrix: no user may reach another user's event or its children.

Every child resource lookup is scoped to both the event and the caller, so the
correct answer for an intruder is always 404 (never 403/500, which would leak
whether the resource exists).
"""
import pytest


def _event_payload(name="Test Wedding"):
    return {
        "name": name,
        "event_type": "wedding",
        "profile": {
            "occasion": "Wedding",
            "budget": 500000,
            "guest_count": 100,
            "event_date": "2027-06-15",
            "experience_level": "moderate",
            "priorities": ["catering"],
            "must_haves": ["flowers"],
            "atmosphere": "festive",
            "age_groups": ["adults"],
            "cultural_preferences": "",
            "accessibility_needs": "",
            "venue_limits": "",
        },
    }


@pytest.fixture
def owner_resources(auth_client, sample_event):
    """Create one of each child resource on the owner's event."""
    event_id = sample_event["id"]

    budget = auth_client.put(
        f"/api/events/{event_id}/budget",
        json=[{"name": "Venue", "allocated": 10_000}],
    )
    assert budget.status_code == 200
    cat_id = auth_client.get(f"/api/events/{event_id}/budget").json()[0]["id"]

    task = auth_client.post(
        f"/api/events/{event_id}/tasks", json={"title": "Book the venue"}
    )
    assert task.status_code == 201

    vendor = auth_client.post(
        f"/api/events/{event_id}/vendors",
        json={"vendor_type": "venue", "name": "Grand Hall"},
    )
    assert vendor.status_code == 201

    guest = auth_client.post(
        f"/api/events/{event_id}/guests", json={"name": "Owner Guest"}
    )
    assert guest.status_code == 201

    return {
        "event_id": event_id,
        "cat_id": cat_id,
        "task_id": task.json()["id"],
        "vendor_id": vendor.json()["id"],
        "guest_id": guest.json()["id"],
    }


@pytest.fixture
def intruder_client(owner_resources, client):
    """Log the shared client in as a second, unrelated user."""
    client.post("/api/auth/logout")
    signup = client.post(
        "/api/auth/signup",
        json={
            "email": "intruder@example.com",
            "password": "Valid@1234",
            "display_name": "Intruder",
        },
    )
    assert signup.status_code == 202
    login = client.post(
        "/api/auth/login",
        json={"email": "intruder@example.com", "password": "Valid@1234"},
    )
    assert login.status_code == 200
    return client


_CASES = [
    ("GET", "/api/events/{event_id}", None),
    ("PATCH", "/api/events/{event_id}", {"name": "Hijacked"}),
    ("DELETE", "/api/events/{event_id}", None),
    ("GET", "/api/events/{event_id}/budget", None),
    ("PUT", "/api/events/{event_id}/budget", [{"name": "Hijack", "allocated": 1}]),
    ("PATCH", "/api/events/{event_id}/budget/{cat_id}", {"spent": 1}),
    ("GET", "/api/events/{event_id}/tasks", None),
    ("POST", "/api/events/{event_id}/tasks", {"title": "Hijacked task"}),
    (
        "PATCH",
        "/api/events/{event_id}/tasks/{task_id}",
        {"status": "completed"},
    ),
    ("GET", "/api/events/{event_id}/vendors", None),
    (
        "POST",
        "/api/events/{event_id}/vendors",
        {"vendor_type": "venue", "name": "Hijacked vendor"},
    ),
    (
        "PATCH",
        "/api/events/{event_id}/vendors/{vendor_id}",
        {"is_selected": True},
    ),
    ("DELETE", "/api/events/{event_id}/vendors/{vendor_id}", None),
    ("GET", "/api/events/{event_id}/guests", None),
    ("POST", "/api/events/{event_id}/guests", {"name": "Hijacked guest"}),
    (
        "PATCH",
        "/api/events/{event_id}/guests/{guest_id}",
        {"rsvp_status": "confirmed"},
    ),
    ("DELETE", "/api/events/{event_id}/guests/{guest_id}", None),
    ("GET", "/api/events/{event_id}/plan-health", None),
    ("GET", "/api/events/{event_id}/chat", None),
]


@pytest.mark.parametrize("method,path,payload", _CASES)
def test_intruder_gets_404_for_every_owner_resource(
    intruder_client, owner_resources, method, path, payload
):
    url = path.format(**owner_resources)

    response = intruder_client.request(method, url, json=payload)

    assert response.status_code == 404, f"{method} {url} returned {response.status_code}"


def test_intruder_cannot_list_the_owner_event(intruder_client):
    response = intruder_client.get("/api/events")

    assert response.status_code == 200
    assert response.json() == []


def test_child_ids_are_scoped_to_their_own_event(auth_client, owner_resources):
    other = auth_client.post("/api/events", json=_event_payload("Second Event"))
    assert other.status_code == 201
    other_id = other.json()["id"]

    response = auth_client.patch(
        f"/api/events/{other_id}/tasks/{owner_resources['task_id']}",
        json={"status": "completed"},
    )

    assert response.status_code == 404
