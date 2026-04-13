"""Admin todo task manager — JSON file-backed CRUD API."""

import asyncio
import contextlib
import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import require_auth

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/todos", tags=["admin"])

# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

DATA_DIR = Path(
    os.environ.get(
        "RAILWAY_VOLUME_MOUNT_PATH",
        str(Path(__file__).resolve().parent.parent.parent / "data"),
    )
)
TODOS_FILE = DATA_DIR / "todo-tasks.json"
_lock = asyncio.Lock()


def _read_sync() -> list[dict]:
    if not TODOS_FILE.exists():
        return []
    try:
        return json.loads(TODOS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        logger.warning("Failed to read %s, returning empty list", TODOS_FILE)
        return []


def _write_sync(todos: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=DATA_DIR, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(todos, f, indent=2, default=str)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, TODOS_FILE)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class TodoCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    category: str = "content"
    priority: str = Field(default="p2", pattern="^(p0|p1|p2|p3)$")
    description: str | None = None
    steps: list[str] | None = None
    roadmap_link: str | None = None
    concept_link: str | None = None
    target_date: str | None = None
    owner: str | None = None


class TodoUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    status: str | None = Field(None, pattern="^(not_started|in_progress|done)$")
    priority: str | None = Field(None, pattern="^(p0|p1|p2|p3)$")
    category: str | None = None
    description: str | None = None
    steps: list[str] | None = None
    roadmap_link: str | None = None
    concept_link: str | None = None
    target_date: str | None = None
    owner: str | None = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("")
async def list_todos(
    status: str | None = None,
    user: dict = Depends(require_auth),
):
    async with _lock:
        todos = _read_sync()
    if status:
        todos = [t for t in todos if t.get("status") == status]
    todos.sort(key=lambda t: t.get("updated_at", ""), reverse=True)
    return todos


@router.post("", status_code=201)
async def create_todo(
    body: TodoCreate,
    user: dict = Depends(require_auth),
):
    now = datetime.now(timezone.utc).isoformat()
    todo = {
        "id": str(uuid4()),
        "title": body.title,
        "category": body.category,
        "status": "not_started",
        "priority": body.priority,
        "owner": body.owner,
        "description": body.description,
        "steps": body.steps,
        "roadmap_link": body.roadmap_link,
        "concept_link": body.concept_link,
        "target_date": body.target_date,
        "created_at": now,
        "updated_at": now,
    }
    async with _lock:
        todos = _read_sync()
        todos.append(todo)
        _write_sync(todos)
    return todo


@router.patch("/{todo_id}")
async def update_todo(
    todo_id: str,
    body: TodoUpdate,
    user: dict = Depends(require_auth),
):
    async with _lock:
        todos = _read_sync()
        target = next((t for t in todos if t["id"] == todo_id), None)
        if target is None:
            raise HTTPException(status_code=404, detail="Todo not found")
        changes = body.model_dump(exclude_none=True)
        if not changes:
            return target
        target.update(changes)
        target["updated_at"] = datetime.now(timezone.utc).isoformat()
        _write_sync(todos)
        return target


@router.delete("/{todo_id}", status_code=204)
async def delete_todo(
    todo_id: str,
    user: dict = Depends(require_auth),
):
    async with _lock:
        todos = _read_sync()
        original_len = len(todos)
        todos = [t for t in todos if t["id"] != todo_id]
        if len(todos) == original_len:
            raise HTTPException(status_code=404, detail="Todo not found")
        _write_sync(todos)
