"""Integration tests for /admin/todos routes.

Todos use JSON file persistence (not the database), so these tests
patch the file path to a temp directory to avoid touching real data.
"""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch


@pytest.fixture(autouse=True)
def _isolate_todos_file(tmp_path):
    """Redirect todo persistence to a temp dir so tests are isolated."""
    todos_file = tmp_path / "todo-tasks.json"
    with patch("app.routes.todos.DATA_DIR", tmp_path), \
         patch("app.routes.todos.TODOS_FILE", todos_file):
        yield


@pytest.mark.integration
class TestListTodos:
    def test_returns_empty_list_initially(self, client):
        resp = client.get("/admin/todos")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_filter_by_status(self, client):
        """Only returns todos matching the ?status= filter."""
        client.post("/admin/todos", json={"title": "Task A"})
        post_resp = client.post("/admin/todos", json={"title": "Task B"})
        todo_id = post_resp.json()["id"]

        # Mark Task B as done
        client.patch(f"/admin/todos/{todo_id}", json={"status": "done"})

        resp = client.get("/admin/todos?status=done")
        assert resp.status_code == 200
        todos = resp.json()
        assert len(todos) == 1
        assert todos[0]["title"] == "Task B"


@pytest.mark.integration
class TestCreateTodo:
    def test_create_returns_201(self, client):
        resp = client.post("/admin/todos", json={"title": "Write tests"})
        assert resp.status_code == 201

    def test_create_returns_todo_with_defaults(self, client):
        resp = client.post("/admin/todos", json={"title": "Write tests"})
        todo = resp.json()
        assert todo["title"] == "Write tests"
        assert todo["status"] == "not_started"
        assert todo["category"] == "content"
        assert todo["priority"] == "p2"
        assert "id" in todo
        assert "created_at" in todo
        assert "updated_at" in todo

    def test_create_with_all_fields(self, client):
        body = {
            "title": "Full todo",
            "category": "engineering",
            "priority": "p0",
            "description": "A detailed description",
            "steps": ["Step 1", "Step 2"],
            "roadmap_link": "https://example.com/roadmap",
            "concept_link": "https://example.com/concept",
            "target_date": "2026-05-01",
            "owner": "jimmy",
        }
        resp = client.post("/admin/todos", json=body)
        assert resp.status_code == 201
        todo = resp.json()
        assert todo["category"] == "engineering"
        assert todo["priority"] == "p0"
        assert todo["steps"] == ["Step 1", "Step 2"]
        assert todo["owner"] == "jimmy"

    def test_create_persists_to_list(self, client):
        client.post("/admin/todos", json={"title": "Persisted task"})
        resp = client.get("/admin/todos")
        assert len(resp.json()) == 1
        assert resp.json()[0]["title"] == "Persisted task"

    def test_create_empty_title_returns_422(self, client):
        resp = client.post("/admin/todos", json={"title": ""})
        assert resp.status_code == 422

    def test_create_invalid_priority_returns_422(self, client):
        resp = client.post("/admin/todos", json={"title": "Bad prio", "priority": "p9"})
        assert resp.status_code == 422


@pytest.mark.integration
class TestUpdateTodo:
    def test_patch_status(self, client):
        post_resp = client.post("/admin/todos", json={"title": "Update me"})
        todo_id = post_resp.json()["id"]

        resp = client.patch(
            f"/admin/todos/{todo_id}",
            json={"status": "in_progress"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "in_progress"

    def test_patch_title(self, client):
        post_resp = client.post("/admin/todos", json={"title": "Old title"})
        todo_id = post_resp.json()["id"]

        resp = client.patch(
            f"/admin/todos/{todo_id}",
            json={"title": "New title"},
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "New title"

    def test_patch_updates_updated_at(self, client):
        post_resp = client.post("/admin/todos", json={"title": "Timestamp check"})
        todo_id = post_resp.json()["id"]
        original_updated = post_resp.json()["updated_at"]

        resp = client.patch(
            f"/admin/todos/{todo_id}",
            json={"status": "done"},
        )
        assert resp.json()["updated_at"] >= original_updated

    def test_patch_no_changes_returns_original(self, client):
        post_resp = client.post("/admin/todos", json={"title": "No change"})
        todo_id = post_resp.json()["id"]

        resp = client.patch(f"/admin/todos/{todo_id}", json={})
        assert resp.status_code == 200
        assert resp.json()["title"] == "No change"

    def test_patch_nonexistent_returns_404(self, client):
        resp = client.patch(
            "/admin/todos/nonexistent-uuid",
            json={"status": "done"},
        )
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_patch_invalid_status_returns_422(self, client):
        post_resp = client.post("/admin/todos", json={"title": "Bad status"})
        todo_id = post_resp.json()["id"]

        resp = client.patch(
            f"/admin/todos/{todo_id}",
            json={"status": "invalid_status"},
        )
        assert resp.status_code == 422


@pytest.mark.integration
class TestDeleteTodo:
    def test_delete_returns_204(self, client):
        post_resp = client.post("/admin/todos", json={"title": "Delete me"})
        todo_id = post_resp.json()["id"]

        resp = client.delete(f"/admin/todos/{todo_id}")
        assert resp.status_code == 204

    def test_delete_removes_from_list(self, client):
        post_resp = client.post("/admin/todos", json={"title": "Gone soon"})
        todo_id = post_resp.json()["id"]

        client.delete(f"/admin/todos/{todo_id}")

        resp = client.get("/admin/todos")
        assert resp.json() == []

    def test_delete_nonexistent_returns_404(self, client):
        resp = client.delete("/admin/todos/nonexistent-uuid")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_delete_only_removes_target(self, client):
        """Deleting one todo should not affect others."""
        resp_a = client.post("/admin/todos", json={"title": "Keep me"})
        resp_b = client.post("/admin/todos", json={"title": "Delete me"})

        client.delete(f"/admin/todos/{resp_b.json()['id']}")

        remaining = client.get("/admin/todos").json()
        assert len(remaining) == 1
        assert remaining[0]["title"] == "Keep me"
