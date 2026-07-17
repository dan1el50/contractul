"""The storage interface.

Files are addressed by opaque key, never by path. Today a key resolves to a
file in a Docker volume; tomorrow it may resolve to an S3 object. Callers must
not be able to tell, which is why nothing here returns a Path.

Nothing outside app.integrations.storage may import a concrete implementation.
Depend on Storage; take the implementation as an argument. The moment a service
imports LocalStorage by name, the abstraction is decorative.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


class StorageError(RuntimeError):
    """A file could not be read or written."""


class ObjectNotFound(StorageError):
    """No object exists under that key."""


@runtime_checkable
class Storage(Protocol):
    def put(self, key: str, data: bytes) -> None:
        """Write an object, replacing any existing one at that key."""
        ...

    def get(self, key: str) -> bytes:
        """Read an object. Raises ObjectNotFound if it is not there."""
        ...

    def exists(self, key: str) -> bool: ...

    def delete(self, key: str) -> None:
        """Remove an object. Silent if it does not exist — deletion is idempotent."""
        ...
