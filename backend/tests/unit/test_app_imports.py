"""The application actually starts.

This exists because of a real bug that 83 passing tests did not catch.

app.db.base imported the models, and the models import app.db.base. Python
resolves that cycle when app.db.base is imported first and raises ImportError
when a model is imported first. conftest imports app.db.base early, so the
whole suite was green — while uvicorn, which reaches app.main first, could not
start the server at all.

Importing app.main inside this file would prove nothing: pytest has already
imported half the package by then, in conftest's order. The only honest check
is a fresh interpreter importing the way production does, which is why these
tests shell out to a subprocess.
"""

import subprocess
import sys


def _import_in_fresh_interpreter(module: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def test_app_main_imports_cleanly() -> None:
    """What uvicorn does. If this fails, the server does not boot."""
    result = _import_in_fresh_interpreter("app.main")

    assert result.returncode == 0, f"app.main failed to import:\n{result.stderr}"


def test_models_can_be_imported_first() -> None:
    """The exact order that used to fail.

    Reaching a model before app.db.base must work, because a route importing
    a model is the most ordinary thing in this codebase.
    """
    result = _import_in_fresh_interpreter("app.models.user")

    assert result.returncode == 0, f"app.models.user failed to import:\n{result.stderr}"


def test_deps_can_be_imported_first() -> None:
    """app.api.deps reaches models before anything touches app.db.base."""
    result = _import_in_fresh_interpreter("app.api.deps")

    assert result.returncode == 0, f"app.api.deps failed to import:\n{result.stderr}"


def test_model_registry_imports_cleanly() -> None:
    """What Alembic relies on to see the schema."""
    result = _import_in_fresh_interpreter("app.models")

    assert result.returncode == 0, f"app.models failed to import:\n{result.stderr}"


def test_every_model_is_registered_for_alembic() -> None:
    """A model missing from app.models is invisible to autogenerate.

    Alembic would then diff the database against metadata that omits it and
    write a migration dropping its table — data loss, generated automatically
    and looking entirely routine in review.
    """
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import app.models; from app.db.base import Base; "
            "print(','.join(sorted(Base.metadata.tables)))",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    tables = set(result.stdout.strip().split(","))
    assert {"users", "sessions"} <= tables, f"Missing from the registry: {tables}"
