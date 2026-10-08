"""Shared test setup.

The environment variables must be set BEFORE app.config is imported, because the
background task opens its own database session and never sees a dependency
override. Using a temp file (not sqlite:///:memory:) matters for the same reason:
an in-memory database is per-connection, so the task's thread would find no tables.
"""
import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="cert-tests-").replace("\\", "/")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["STORAGE_DIR"] = f"{_tmp}/storage"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def client():
    """A client against an empty database. TestClient runs background tasks
    before the request returns, so a job is finished by the time POST responds."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def recipients():
    return [
        {"name": "Asha Verma", "email": "asha@example.com"},
        {"name": "Rahul Singh", "email": "rahul@example.com"},
        {"name": "Meera Nair", "email": "meera@example.com"},
    ]


@pytest.fixture()
def job_body(recipients):
    def build(rows=None, **overrides):
        return {
            "course_name": "Backend Engineering Bootcamp",
            "issuer": "Acme Academy",
            "issue_date": "2026-10-08",
            "recipients": recipients if rows is None else rows,
            **overrides,
        }
    return build