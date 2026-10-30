"""Guards the public API contract against regressing to untyped dicts."""
import pytest

from app.main import app

_TYPED_RESPONSES = [
    ("/api/events/{event_id}/tasks", "get", "TaskListResponse"),
    ("/api/events/{event_id}/tasks/generate", "post", "TaskListResponse"),
    ("/api/events/{event_id}/plan-health", "get", "PlanHealthResponse"),
    ("/api/events/{event_id}/plan-health/crisis", "post", "CrisisProposalResponse"),
    ("/api/events/{event_id}/budget/scenario", "post", "AIReplanDiff"),
    ("/api/events/{event_id}/chat/ideas", "get", "AIIdeas"),
    ("/api/events/{event_id}/guests/import-csv", "post", "GuestImportResponse"),
    ("/api/demo/load", "post", "DemoLoadResponse"),
    ("/api/auth/login", "post", "LoginResponse"),
]


@pytest.fixture(scope="module")
def openapi_schema():
    return app.openapi()


@pytest.mark.parametrize("path,method,model", _TYPED_RESPONSES)
def test_success_response_is_documented_with_a_model(openapi_schema, path, method, model):
    responses = openapi_schema["paths"][path][method]["responses"]
    success = responses.get("201") or responses["200"]
    schema = success["content"]["application/json"]["schema"]

    assert schema == {"$ref": f"#/components/schemas/{model}"}
    assert model in openapi_schema["components"]["schemas"]


def test_ai_routes_document_the_source_header(openapi_schema):
    operation = openapi_schema["paths"]["/api/events/{event_id}/chat/ideas"]["get"]

    assert "X-AI-Source" in str(operation.get("responses", ""))
