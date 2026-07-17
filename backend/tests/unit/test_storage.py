"""Local filesystem storage.

The path-traversal tests are the point. Keys will eventually come from user
input — an admin naming an upload, a URL segment — and a key that escapes the
storage root turns "read a preview" into "read any file the process can".
"""

from pathlib import Path

import pytest

from app.integrations.storage.base import ObjectNotFound, StorageError
from app.integrations.storage.local import LocalStorage


@pytest.fixture
def storage(tmp_path: Path) -> LocalStorage:
    return LocalStorage(tmp_path / "root")


def test_put_then_get_round_trips(storage: LocalStorage) -> None:
    storage.put("a/b/c.txt", b"salut")

    assert storage.get("a/b/c.txt") == b"salut"


def test_get_missing_raises_object_not_found(storage: LocalStorage) -> None:
    with pytest.raises(ObjectNotFound):
        storage.get("nope.txt")


def test_put_overwrites(storage: LocalStorage) -> None:
    storage.put("k", b"first")
    storage.put("k", b"second")

    assert storage.get("k") == b"second"


def test_exists(storage: LocalStorage) -> None:
    assert storage.exists("k") is False
    storage.put("k", b"x")
    assert storage.exists("k") is True


def test_delete_is_idempotent(storage: LocalStorage) -> None:
    storage.put("k", b"x")
    storage.delete("k")
    storage.delete("k")  # must not raise

    assert storage.exists("k") is False


def test_nested_keys_create_directories(storage: LocalStorage) -> None:
    storage.put("previews/abc/full-1.png", b"png")

    assert storage.get("previews/abc/full-1.png") == b"png"


def test_no_partial_file_is_left_behind(storage: LocalStorage, tmp_path: Path) -> None:
    """put() writes to a temp file and renames, so readers never see a half file."""
    storage.put("k", b"data")

    leftovers = list((tmp_path / "root").rglob("*.tmp"))
    assert leftovers == []


# ─── Path traversal ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "key",
    [
        "../escape.txt",
        "../../etc/passwd",
        "a/../../escape.txt",
        "/etc/passwd",
        "a/b/../../../escape.txt",
    ],
)
def test_keys_cannot_escape_the_root(storage: LocalStorage, key: str) -> None:
    with pytest.raises(StorageError, match="escapes the storage root"):
        storage.put(key, b"owned")


@pytest.mark.parametrize("key", ["../escape.txt", "/etc/passwd"])
def test_reading_outside_the_root_is_refused(storage: LocalStorage, key: str) -> None:
    with pytest.raises(StorageError, match="escapes the storage root"):
        storage.get(key)


def test_traversal_does_not_write_outside_the_root(tmp_path: Path) -> None:
    """The assertion that actually matters: nothing lands on disk.

    A test that only checks the exception would still pass if the file had
    already been written before the check.
    """
    storage = LocalStorage(tmp_path / "root")
    victim = tmp_path / "victim.txt"

    with pytest.raises(StorageError):
        storage.put("../victim.txt", b"owned")

    assert not victim.exists()
