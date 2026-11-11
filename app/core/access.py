"""Dataset visibility. Public demo rows are readable by anyone. Private uploads require the owner token."""

from __future__ import annotations

from contextvars import ContextVar
from uuid import uuid4

from app.core.errors import NotFoundError

_owner: ContextVar[str | None] = ContextVar("owner_token", default=None)


def set_owner_token(token: str | None) -> None:
    cleaned = (token or "").strip()
    _owner.set(cleaned or None)


def current_owner() -> str | None:
    return _owner.get()


def new_owner_token() -> str:
    return uuid4().hex


def can_read(dataset, token: str | None = None) -> bool:
    token = current_owner() if token is None else token
    visibility = getattr(dataset, "visibility", None) or "public"
    owner = getattr(dataset, "owner_token", None)
    if visibility == "public" or not owner:
        return True
    return bool(token) and token == owner


def assert_can_read(dataset) -> None:
    if dataset is None or not can_read(dataset):
        raise NotFoundError("Dataset was not found.")
