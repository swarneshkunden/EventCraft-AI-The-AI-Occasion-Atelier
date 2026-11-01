"""Guest CRUD and CSV import route coverage."""

import io


def _create_guest(client, event_id, **overrides):
    payload = {"name": "Asha Rao", "email": "asha@example.com", **overrides}
    response = client.post(f"/api/events/{event_id}/guests", json=payload)
    assert response.status_code == 201
    return response.json()


def test_patch_guest_updates_only_the_requested_fields(auth_client, sample_event):
    guest = _create_guest(
        auth_client,
        sample_event["id"],
        dietary_needs="Vegetarian",
        accessibility_needs="Step-free access",
    )

    response = auth_client.patch(
        f"/api/events/{sample_event['id']}/guests/{guest['id']}",
        json={"rsvp_status": "confirmed"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["rsvp_status"] == "confirmed"
    assert body["dietary_needs"] == "Vegetarian"
    assert body["accessibility_needs"] == "Step-free access"


def test_patch_missing_guest_returns_404(auth_client, sample_event):
    response = auth_client.patch(
        f"/api/events/{sample_event['id']}/guests/does-not-exist",
        json={"rsvp_status": "confirmed"},
    )

    assert response.status_code == 404


def test_delete_guest_removes_it_from_the_list(auth_client, sample_event):
    event_id = sample_event["id"]
    guest = _create_guest(auth_client, event_id)

    deleted = auth_client.delete(f"/api/events/{event_id}/guests/{guest['id']}")

    assert deleted.status_code == 204
    listing = auth_client.get(f"/api/events/{event_id}/guests").json()
    assert listing["total"] == 0
    assert listing["guests"] == []


def test_delete_missing_guest_returns_404(auth_client, sample_event):
    response = auth_client.delete(f"/api/events/{sample_event['id']}/guests/does-not-exist")

    assert response.status_code == 404


def test_csv_import_reports_imported_and_skipped_rows(auth_client, sample_event):
    csv_body = (
        "name,email,rsvp_status\nRavi,ravi@example.com,confirmed\nNo Email,not-an-email,pending\n"
    )

    response = auth_client.post(
        f"/api/events/{sample_event['id']}/guests/import-csv",
        files={"file": ("guests.csv", io.BytesIO(csv_body.encode()), "text/csv")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "imported": 1,
        "skipped": 1,
        "message": "Imported 1 guests.",
    }

    listing = auth_client.get(f"/api/events/{sample_event['id']}/guests").json()
    assert [guest["name"] for guest in listing["guests"]] == ["Ravi"]
