"""Filesystem-backed storage.

Keys become paths under a root directory. Backed by a Docker volume in
development; the S3 implementation arrives when we deploy somewhere that
warrants it.
"""

from __future__ import annotations

import logging
from pathlib import Path

from app.integrations.storage.base import ObjectNotFound, StorageError

logger = logging.getLogger(__name__)


class LocalStorage:
    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        """Map a key to a path, refusing anything that escapes the root.

        Keys will eventually come from user input — an admin naming an upload,
        a URL segment. A key of "../../etc/passwd" must not read /etc/passwd,
        and a key of "/etc/passwd" must not either. Checking the *resolved*
        path is what makes this hold: symlinks and .. are already collapsed by
        then, so there is nothing clever left to smuggle past it.
        """
        candidate = (self._root / key).resolve()

        if not candidate.is_relative_to(self._root):
            raise StorageError(f"Key escapes the storage root: {key!r}")

        return candidate

    def put(self, key: str, data: bytes) -> None:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Write to a temp file and rename. Rename is atomic on POSIX, so a
        # concurrent reader sees either the old object or the new one, never a
        # half-written file — which for a PDF someone paid for matters.
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_bytes(data)
        temp.replace(path)

    def get(self, key: str) -> bytes:
        path = self._resolve(key)
        try:
            return path.read_bytes()
        except FileNotFoundError as exc:
            raise ObjectNotFound(key) from exc

    def exists(self, key: str) -> bool:
        return self._resolve(key).is_file()

    def delete(self, key: str) -> None:
        self._resolve(key).unlink(missing_ok=True)
