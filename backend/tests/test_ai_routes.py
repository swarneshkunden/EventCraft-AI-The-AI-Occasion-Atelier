"""Integration tests for AI-backed event routes with the external provider stubbed."""
import json

from app.services.ai_service import _AI_FALLBACK


def _mock_ai(monkeypatch, route_module, response):
    async def fake_call_ai(*_args, **_kwargs):
        return response

    monkeypatch.setattr(f"app.routes.{route_module}.call_ai", fake_call_ai)


def test_chat_persists_user_and_assistant_messages(auth_client, sample_event, monkeypatch):
    _mock_ai(monkeypatch, "chat", "Start by confirming the venue and guest count.")
    event_id = sample_event["id"]

    response = auth_client.post(
        f"/api/events/{event_id}/chat",
        json={"message": "What should I plan first?"},
    )

    assert response.status_code == 200
    assert response.json()["role"] == "assistant"
    history = auth_client.get(f"/api/events/{event_id}/chat")
    assert [message["role"] for message in history.json()] == ["user", "assistant"]
    assert history.json()[0]["content"] == "What should I plan first?"


def test_chat_ideas_validate_and_return_structured_output(
    auth_client, sample_event, monkeypatch
):
    expected = {"themes": [], "decor": [], "menu": [], "activities": []}
    _mock_ai(monkeypatch, "chat", json.dumps(expected))

    response = auth_client.get(f"/api/events/{sample_event['id']}/chat/ideas")

    assert response.status_code == 200
    assert response.json() == expected


def test_chat_ideas_reject_malformed_ai_output(auth_client, sample_event, monkeypatch):
    _mock_ai(monkeypatch, "chat", "This is not JSON.")

    response = auth_client.get(f"/api/events/{sample_event['id']}/chat/ideas")

    assert response.status_code == 502
    assert response.json()["detail"] == "Request could not be completed"


def test_budget_split_is_clamped_to_event_budget(auth_client, sample_event, monkeypatch):
    ai_response = json.dumps({
        "categories": [
            {"name": "Venue", "allocated": 400000},
            {"name": "Catering", "allocated": 400000},
        ]
    })
    _mock_ai(monkeypatch, "budget", ai_response)

    response = auth_client.post(f"/api/events/{sample_event['id']}/budget/ai-split")

    assert response.status_code == 200
    assert sum(category["allocated"] for category in response.json()) == 500000


def test_task_generation_validates_and_stores_tasks(auth_client, sample_event, monkeypatch):
    ai_response = json.dumps({
        "tasks": [
            {
                "title": "Confirm the venue",
                "category": "venue",
                "priority": 1,
                "due_date": "2027-01-01",
            }
        ]
    })
    _mock_ai(monkeypatch, "tasks", ai_response)

    response = auth_client.post(f"/api/events/{sample_event['id']}/tasks/generate")

    assert response.status_code == 200
    assert response.json()["tasks"][0]["title"] == "Confirm the venue"
    assert response.json()["tasks"][0]["is_ready"] is True


def test_vendor_questions_validate_and_persist_ai_data(
    auth_client, sample_event, monkeypatch
):
    event_id = sample_event["id"]
    created = auth_client.post(
        f"/api/events/{event_id}/vendors",
        json={"vendor_type": "caterer", "name": "Garden Catering"},
    )
    assert created.status_code == 201
    _mock_ai(
        monkeypatch,
        "vendors",
        json.dumps({
            "checklist": ["Confirm vegetarian options"],
            "questions": ["Can you serve 100 guests?"],
        }),
    )

    response = auth_client.post(
        f"/api/events/{event_id}/vendors/{created.json()['id']}/generate-questions"
    )

    assert response.status_code == 200
    assert response.json()["ai_checklist"] == ["Confirm vegetarian options"]
    assert response.json()["ai_questions"] == ["Can you serve 100 guests?"]


def test_ai_routes_return_service_unavailable_on_provider_fallback(
    auth_client, sample_event, monkeypatch
):
    _mock_ai(monkeypatch, "tasks", _AI_FALLBACK)

    response = auth_client.post(f"/api/events/{sample_event['id']}/tasks/generate")

    assert response.status_code == 503
