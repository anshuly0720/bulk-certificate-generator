"""Brief: 'Input validation'.

Two levels: a malformed request is rejected whole; a bad row is recorded as
INVALID while the rest of the job carries on.
"""
import pytest


def test_malformed_request_is_rejected(client, job_body):
    assert client.post("/api/v1/jobs", json=job_body([])).status_code == 422
    assert client.post("/api/v1/jobs", json=job_body(["not-an-object"])).status_code == 422
    assert client.post("/api/v1/jobs", json=job_body(issue_date="08-10-2026")).status_code == 422
    assert client.post("/api/v1/jobs", json=job_body(issuer="   ")).status_code == 422

    missing_course = job_body()
    del missing_course["course_name"]
    assert client.post("/api/v1/jobs", json=missing_course).status_code == 422


def test_request_over_the_recipient_cap_is_rejected(client, job_body):
    from app.config import MAX_RECIPIENTS

    rows = [{"name": "A", "email": f"a{i}@example.com"} for i in range(MAX_RECIPIENTS + 1)]
    assert client.post("/api/v1/jobs", json=job_body(rows)).status_code == 422


@pytest.mark.parametrize("row,reason", [
    ({"name": "", "email": "blank@example.com"}, "at least 1 character"),
    ({"name": "No Email"}, "Field required"),
    ({"name": "Bad Email", "email": "not-an-email"}, "valid email"),
    ({"name": "x" * 101, "email": "long@example.com"}, "at most 100 characters"),
])
def test_invalid_rows_are_recorded_with_a_reason(client, job_body, recipients, row, reason):
    r = client.post("/api/v1/jobs", json=job_body(recipients + [row]))
    assert r.status_code == 202
    assert r.json() == {**r.json(), "accepted": 3, "invalid": 1}

    items = client.get(f"/api/v1/jobs/{r.json()['job_id']}/certificates",
                       params={"status": "INVALID"}).json()["items"]
    assert len(items) == 1
    assert reason in items[0]["error"]


def test_duplicate_email_in_one_request_is_invalid(client, job_body, recipients):
    r = client.post("/api/v1/jobs", json=job_body(
        recipients + [{"name": "Impostor", "email": "ASHA@example.com"}]))
    assert r.json()["invalid"] == 1

    items = client.get(f"/api/v1/jobs/{r.json()['job_id']}/certificates",
                       params={"status": "INVALID"}).json()["items"]
    assert "duplicate email" in items[0]["error"]


def test_name_the_font_cannot_draw_is_invalid(client, job_body, recipients):
    """The built-in PDF font silently draws black boxes outside cp1252,
    so these rows are rejected rather than producing a broken certificate."""
    r = client.post("/api/v1/jobs", json=job_body(
        recipients + [{"name": "अंशुल", "email": "dev@example.com"}]))
    assert r.json()["invalid"] == 1

    items = client.get(f"/api/v1/jobs/{r.json()['job_id']}/certificates",
                       params={"status": "INVALID"}).json()["items"]
    assert "cannot draw" in items[0]["error"]


def test_invalid_rows_never_get_a_file(client, job_body, recipients):
    r = client.post("/api/v1/jobs", json=job_body(recipients + [{"name": "", "email": "x"}]))
    items = client.get(f"/api/v1/jobs/{r.json()['job_id']}/certificates",
                       params={"status": "INVALID"}).json()["items"]
    assert items[0]["download_url"] is None