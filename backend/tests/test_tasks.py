"""Unit tests for task dependency and timeline logic."""
from app.models.models import Task, TaskStatus
from app.services.event_service import compute_task_readiness


def _make_task(title: str, status: str, depends_on: list[str]) -> Task:
    t = Task()
    t.title = title
    t.status = status
    t.depends_on = depends_on
    t.priority = 5
    t.due_date = None
    return t


class TestTaskDependencies:
    def test_task_with_no_deps_is_ready(self):
        tasks = [_make_task("Book Venue", TaskStatus.pending, [])]
        result = compute_task_readiness(tasks)
        assert result[0]["is_ready"] is True
        assert result[0]["blocked_by"] == []

    def test_task_with_incomplete_dep_is_not_ready(self):
        tasks = [
            _make_task("Book Venue", TaskStatus.pending, []),
            _make_task("Send Invitations", TaskStatus.pending, ["Book Venue"]),
        ]
        result = compute_task_readiness(tasks)
        inv = next(r for r in result if r["task"].title == "Send Invitations")
        assert inv["is_ready"] is False
        assert "Book Venue" in inv["blocked_by"]

    def test_task_with_completed_dep_is_ready(self):
        tasks = [
            _make_task("Book Venue", TaskStatus.completed, []),
            _make_task("Send Invitations", TaskStatus.pending, ["Book Venue"]),
        ]
        result = compute_task_readiness(tasks)
        inv = next(r for r in result if r["task"].title == "Send Invitations")
        assert inv["is_ready"] is True
        assert inv["blocked_by"] == []

    def test_completed_task_is_not_ready(self):
        tasks = [_make_task("Done Task", TaskStatus.completed, [])]
        result = compute_task_readiness(tasks)
        assert result[0]["is_ready"] is False

    def test_blocked_task_is_not_ready(self):
        tasks = [_make_task("Blocked Task", TaskStatus.blocked, [])]
        result = compute_task_readiness(tasks)
        assert result[0]["is_ready"] is False

    def test_chain_of_dependencies(self):
        tasks = [
            _make_task("Step 1", TaskStatus.completed, []),
            _make_task("Step 2", TaskStatus.completed, ["Step 1"]),
            _make_task("Step 3", TaskStatus.pending, ["Step 2"]),
        ]
        result = compute_task_readiness(tasks)
        step3 = next(r for r in result if r["task"].title == "Step 3")
        assert step3["is_ready"] is True


class TestTaskRoutes:
    def test_task_status_update(self, auth_client, sample_event, db):
        event_id = sample_event["id"]
        from app.models.models import Event
        event = db.query(Event).filter(Event.id == event_id).first()
        from app.services.event_service import bulk_create_tasks
        tasks = bulk_create_tasks(event_id, event.owner_id, [
            {"title": "Test Task", "category": "general", "priority": 5}
        ], db)
        db.commit()
        task_id = tasks[0].id

        resp = auth_client.patch(f"/api/events/{event_id}/tasks/{task_id}", json={"status": "completed"})
        assert resp.status_code == 200

    def test_invalid_task_status_rejected(self, auth_client, sample_event):
        event_id = sample_event["id"]
        resp = auth_client.patch(f"/api/events/{event_id}/tasks/nonexistent", json={"status": "flying"})
        assert resp.status_code == 400
