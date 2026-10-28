"""
Integration tests for event endpoints, validators, and AI mocking.
"""
import json
import unittest.mock as mock


class TestEventCRUD:
    def test_create_event(self, auth_client):
        resp = auth_client.post("/api/events", json={
            "name": "Birthday Party",
            "event_type": "birthday",
            "profile": {
                "occasion": "Birthday",
                "budget": 50000,
                "guest_count": 30,
                "event_date": "2027-03-15",
                "experience_level": "simple",
                "priorities": ["food"],
                "must_haves": ["cake"],
                "atmosphere": "fun",
                "age_groups": ["children"],
                "cultural_preferences": "",
                "accessibility_needs": "",
                "venue_limits": "",
            }
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Birthday Party"
        assert data["event_type"] == "birthday"
        assert data["total_budget"] == 50000

    def test_list_events(self, auth_client, sample_event):
        resp = auth_client.get("/api/events")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_get_event(self, auth_client, sample_event):
        event_id = sample_event["id"]
        resp = auth_client.get(f"/api/events/{event_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == event_id

    def test_update_event_profile_and_type(self, auth_client, sample_event):
        event_id = sample_event["id"]
        response = auth_client.patch(f"/api/events/{event_id}", json={
            "name": "Updated Celebration",
            "event_type": "birthday",
            "profile": {
                "occasion": "Milestone birthday",
                "budget": 75000,
                "guest_count": 45,
                "event_date": "2027-04-20",
                "experience_level": "premium",
                "priorities": ["food", "music"],
                "must_haves": ["accessible venue"],
                "atmosphere": "Festive Carnival",
                "age_groups": [],
                "cultural_preferences": "",
                "accessibility_needs": "",
                "venue_limits": "Garden venue",
                "location": "Grand Hall",
            },
        })

        assert response.status_code == 200
        updated = response.json()
        assert updated["name"] == "Updated Celebration"
        assert updated["event_type"] == "birthday"
        assert updated["total_budget"] == 75000
        assert updated["guest_count"] == 45
        assert updated["event_date"] == "2027-04-20"
        assert updated["profile"]["experience_level"] == "premium"
        assert updated["profile"]["venue_limits"] == "Garden venue"
        assert updated["profile"]["location"] == "Grand Hall"

    def test_delete_event(self, auth_client, sample_event):
        event_id = sample_event["id"]
        resp = auth_client.delete(f"/api/events/{event_id}")
        assert resp.status_code == 204
        get_resp = auth_client.get(f"/api/events/{event_id}")
        assert get_resp.status_code == 404

    def test_invalid_event_type_rejected(self, auth_client):
        resp = auth_client.post("/api/events", json={
            "name": "Bad Event",
            "event_type": "hackathon",
            "profile": {
                "occasion": "Hack", "budget": 1000, "guest_count": 5,
                "experience_level": "simple", "priorities": [], "must_haves": [],
                "atmosphere": "", "age_groups": [], "cultural_preferences": "",
                "accessibility_needs": "", "venue_limits": ""
            }
        })
        assert resp.status_code == 400

    def test_negative_budget_rejected(self, auth_client):
        resp = auth_client.post("/api/events", json={
            "name": "Neg Budget",
            "event_type": "wedding",
            "profile": {
                "occasion": "Wedding", "budget": -100, "guest_count": 50,
                "experience_level": "simple", "priorities": [], "must_haves": [],
                "atmosphere": "", "age_groups": [], "cultural_preferences": "",
                "accessibility_needs": "", "venue_limits": ""
            }
        })
        assert resp.status_code == 400

    def test_zero_guest_count_rejected(self, auth_client):
        resp = auth_client.post("/api/events", json={
            "name": "Zero Guests",
            "event_type": "birthday",
            "profile": {
                "occasion": "Birthday", "budget": 10000, "guest_count": 0,
                "experience_level": "simple", "priorities": [], "must_haves": [],
                "atmosphere": "", "age_groups": [], "cultural_preferences": "",
                "accessibility_needs": "", "venue_limits": ""
            }
        })
        assert resp.status_code == 400


class TestAIBudgetSplit:
    def test_ai_split_with_mocked_ai(self, auth_client, sample_event):
        event_id = sample_event["id"]

        mock_response = json.dumps({
            "categories": [
                {"name": "Venue", "allocated": 150000, "notes": "Estimated (assumption)"},
                {"name": "Catering", "allocated": 200000, "notes": "Estimated (assumption)"},
                {"name": "Misc", "allocated": 150000, "notes": "Buffer"},
            ]
        })

        with mock.patch("app.routes.budget.call_ai", return_value=mock_response):
            resp = auth_client.post(f"/api/events/{event_id}/budget/ai-split")

        assert resp.status_code == 200
        categories = resp.json()
        assert len(categories) == 3
        total = sum(c["allocated"] for c in categories)
        assert total <= 500000 + 1  # within event budget (with float tolerance)

    def test_scenario_uses_backend_request_and_response_contract(self, auth_client, sample_event):
        event_id = sample_event["id"]
        ai_response = json.dumps({
            "summary": "Catering increases, so decor allocation is reduced.",
            "budget_changes": [{
                "category_name": "Catering",
                "old_allocated": 200000,
                "new_allocated": 220000,
                "reason": "The guest count increased.",
            }],
            "task_changes": [{
                "title": "Confirm catering headcount",
                "old_due_date": "2027-06-01",
                "new_due_date": "2027-06-03",
                "new_status": "pending",
                "reason": "Updated count needs a revised confirmation.",
            }],
            "trade_offs": ["Reduce decor spending to preserve the total budget."],
        })

        with mock.patch("app.routes.budget.call_ai", return_value=ai_response):
            response = auth_client.post(
                f"/api/events/{event_id}/budget/scenario",
                json={"description": "Guest count increased"},
            )

        assert response.status_code == 200
        result = response.json()
        assert result["summary"].startswith("Catering increases")
        assert result["budget_changes"][0]["category_name"] == "Catering"
        assert result["task_changes"][0]["new_due_date"] == "2027-06-03"
        assert result["trade_offs"]

    def test_scenario_rejects_frontend_legacy_prompt_field(self, auth_client, sample_event):
        response = auth_client.post(
            f"/api/events/{sample_event['id']}/budget/scenario",
            json={"prompt": "Guest count increased"},
        )
        assert response.status_code == 400

    def test_ai_fallback_returns_503(self, auth_client, sample_event):
        event_id = sample_event["id"]
        fallback = "⚠️ The AI assistant is temporarily unavailable."

        with mock.patch("app.routes.budget.call_ai", return_value=fallback):
            with mock.patch("app.routes.budget.is_ai_fallback", return_value=True):
                resp = auth_client.post(f"/api/events/{event_id}/budget/ai-split")

        assert resp.status_code == 503

    def test_ai_invalid_json_returns_502(self, auth_client, sample_event):
        event_id = sample_event["id"]

        with mock.patch("app.routes.budget.call_ai", return_value="not json at all {{broken"):
            resp = auth_client.post(f"/api/events/{event_id}/budget/ai-split")

        assert resp.status_code == 502


class TestInputValidation:
    def test_empty_body_returns_422(self, auth_client):
        resp = auth_client.post("/api/events", json={})
        assert resp.status_code == 400

    def test_extra_large_budget_rejected(self, auth_client):
        resp = auth_client.post("/api/events", json={
            "name": "Rich Event",
            "event_type": "wedding",
            "profile": {
                "occasion": "Wedding", "budget": 999_999_999_999, "guest_count": 100,
                "experience_level": "premium", "priorities": [], "must_haves": [],
                "atmosphere": "", "age_groups": [], "cultural_preferences": "",
                "accessibility_needs": "", "venue_limits": ""
            }
        })
        assert resp.status_code == 400

    def test_invalid_date_format_rejected(self, auth_client):
        resp = auth_client.post("/api/events", json={
            "name": "Bad Date Event",
            "event_type": "wedding",
            "profile": {
                "occasion": "Wedding", "budget": 100000, "guest_count": 50,
                "event_date": "15-06-2027",  # wrong format
                "experience_level": "moderate", "priorities": [], "must_haves": [],
                "atmosphere": "", "age_groups": [], "cultural_preferences": "",
                "accessibility_needs": "", "venue_limits": ""
            }
        })
        assert resp.status_code == 400

    def test_sql_injection_attempt_in_name_handled(self, auth_client):
        """SQL injection in event name must not cause a 500."""
        resp = auth_client.post("/api/events", json={
            "name": "'; DROP TABLE events; --",
            "event_type": "wedding",
            "profile": {
                "occasion": "Test", "budget": 100000, "guest_count": 50,
                "experience_level": "moderate", "priorities": [], "must_haves": [],
                "atmosphere": "", "age_groups": [], "cultural_preferences": "",
                "accessibility_needs": "", "venue_limits": ""
            }
        })
        # Should either succeed (ORM parameterizes) or reject – never 500
        assert resp.status_code in (201, 400)


class TestGuestAndVendorContracts:
    def test_guest_fields_and_confirmed_status_match_api(self, auth_client, sample_event):
        event_id = sample_event["id"]
        response = auth_client.post(
            f"/api/events/{event_id}/guests",
            json={
                "name": "Ravi Sharma",
                "email": "ravi@example.com",
                "phone": "+91 98765 00000",
                "rsvp_status": "confirmed",
                "dietary_needs": "Vegetarian",
                "accessibility_needs": "Step-free access",
            },
        )
        assert response.status_code == 201
        assert response.json()["dietary_needs"] == "Vegetarian"
        assert response.json()["accessibility_needs"] == "Step-free access"

        invalid_status = auth_client.patch(
            f"/api/events/{event_id}/guests/{response.json()['id']}",
            json={"rsvp_status": "attending"},
        )
        assert invalid_status.status_code == 400

    def test_vendor_selection_field_matches_api(self, auth_client, sample_event):
        event_id = sample_event["id"]
        created = auth_client.post(
            f"/api/events/{event_id}/vendors",
            json={
                "vendor_type": "decorator",
                "name": "Garden Studio",
                "quoted_price": 120000,
                "inclusions": "Floral arrangements",
            },
        )
        assert created.status_code == 201

        updated = auth_client.patch(
            f"/api/events/{event_id}/vendors/{created.json()['id']}",
            json={"is_selected": True},
        )
        assert updated.status_code == 200
        assert updated.json()["is_selected"] is True

        invalid_type = auth_client.post(
            f"/api/events/{event_id}/vendors",
            json={"vendor_type": "florist", "name": "Unsupported type"},
        )
        assert invalid_type.status_code == 400


class TestVendorRoutes:
    def test_create_vendor(self, auth_client, sample_event):
        event_id = sample_event["id"]
        resp = auth_client.post(f"/api/events/{event_id}/vendors", json={
            "vendor_type": "caterer",
            "name": "Best Caterer",
            "quoted_price": 120000,
        })
        assert resp.status_code == 201
        assert resp.json()["name"] == "Best Caterer"

    def test_invalid_vendor_type_rejected(self, auth_client, sample_event):
        event_id = sample_event["id"]
        resp = auth_client.post(f"/api/events/{event_id}/vendors", json={
            "vendor_type": "magician",
            "name": "The Wizard",
        })
        assert resp.status_code == 400


class TestGuestRoutes:
    def test_add_guest(self, auth_client, sample_event):
        event_id = sample_event["id"]
        resp = auth_client.post(f"/api/events/{event_id}/guests", json={
            "name": "Ravi Kumar",
            "email": "ravi@example.com",
            "rsvp_status": "confirmed",
        })
        assert resp.status_code == 201
        assert resp.json()["name"] == "Ravi Kumar"

    def test_invalid_rsvp_status_rejected(self, auth_client, sample_event):
        event_id = sample_event["id"]
        resp = auth_client.post(f"/api/events/{event_id}/guests", json={
            "name": "Guest X",
            "rsvp_status": "maybe",
        })
        assert resp.status_code == 400

    def test_guest_list_pagination(self, auth_client, sample_event):
        event_id = sample_event["id"]
        for i in range(5):
            auth_client.post(f"/api/events/{event_id}/guests", json={"name": f"Guest {i}"})

        resp = auth_client.get(f"/api/events/{event_id}/guests?page=1&page_size=3")
        assert resp.status_code == 200
        data = resp.json()
        assert "guests" in data
        assert "total" in data
        assert len(data["guests"]) <= 3
