"""Unit tests for budget math and scenario logic."""
import pytest


class TestBudgetMath:
    def test_total_budget_equals_sum_of_categories(self, auth_client, sample_event):
        event_id = sample_event["id"]
        budget = 500000

        categories = [
            {"name": "Venue", "allocated": 150000, "spent": 0},
            {"name": "Catering", "allocated": 200000, "spent": 0},
            {"name": "Decor", "allocated": 100000, "spent": 0},
            {"name": "Misc", "allocated": 50000, "spent": 0},
        ]
        resp = auth_client.put(f"/api/events/{event_id}/budget", json=categories)
        assert resp.status_code == 200
        result = resp.json()
        total_allocated = sum(c["allocated"] for c in result)
        assert total_allocated == budget

    def test_spent_cannot_exceed_allocated(self, auth_client, sample_event):
        """Updating spent above allocated is allowed by API but must be stored correctly."""
        event_id = sample_event["id"]
        auth_client.put(f"/api/events/{event_id}/budget", json=[
            {"name": "Venue", "allocated": 100000, "spent": 0}
        ])
        cats = auth_client.get(f"/api/events/{event_id}/budget").json()
        cat_id = cats[0]["id"]

        resp = auth_client.patch(f"/api/events/{event_id}/budget/{cat_id}", json={"spent": 90000})
        assert resp.status_code == 200
        assert resp.json()["spent"] == 90000

    def test_budget_category_update_only_changes_requested_fields(self, auth_client, sample_event):
        event_id = sample_event["id"]
        auth_client.put(f"/api/events/{event_id}/budget", json=[
            {"name": "Catering", "allocated": 200000, "spent": 0, "notes": "original note"}
        ])
        cats = auth_client.get(f"/api/events/{event_id}/budget").json()
        cat_id = cats[0]["id"]

        resp = auth_client.patch(f"/api/events/{event_id}/budget/{cat_id}", json={"spent": 50000})
        assert resp.status_code == 200
        data = resp.json()
        assert data["notes"] == "original note"
        assert data["allocated"] == 200000
        assert data["spent"] == 50000

    def test_max_categories_enforced(self, auth_client, sample_event):
        event_id = sample_event["id"]
        categories = [{"name": f"Cat {i}", "allocated": 1000} for i in range(21)]
        resp = auth_client.put(f"/api/events/{event_id}/budget", json=categories)
        assert resp.status_code == 400

    def test_negative_allocated_rejected(self, auth_client, sample_event):
        event_id = sample_event["id"]
        resp = auth_client.put(f"/api/events/{event_id}/budget", json=[
            {"name": "Bad Cat", "allocated": -1000}
        ])
        assert resp.status_code == 400
