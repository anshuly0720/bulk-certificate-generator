"""Brief: 'Job status/progress'."""


def test_status_reports_counts_and_progress(client, job_body):
    job_id = client.post("/api/v1/jobs", json=job_body()).json()["job_id"]
    job = client.get(f"/api/v1/jobs/{job_id}").json()

    assert job["status"] == "COMPLETED"
    assert job["counts"] == {"total": 3, "pending": 0, "generated": 3, "failed": 0, "invalid": 0}
    assert job["progress_percent"] == 100.0
    assert job["started_at"] and job["completed_at"]


def test_status_echoes_the_job_details(client, job_body):
    job_id = client.post("/api/v1/jobs", json=job_body()).json()["job_id"]
    job = client.get(f"/api/v1/jobs/{job_id}").json()

    assert job["course_name"] == "Backend Engineering Bootcamp"
    assert job["issuer"] == "Acme Academy"
    assert job["issue_date"] == "2026-10-08"


def test_a_job_with_some_invalid_rows_is_completed_with_errors(client, job_body, recipients):
    job_id = client.post("/api/v1/jobs", json=job_body(
        recipients + [{"name": "", "email": "nope"}])).json()["job_id"]
    job = client.get(f"/api/v1/jobs/{job_id}").json()

    assert job["status"] == "COMPLETED_WITH_ERRORS"
    assert job["counts"]["generated"] == 3
    assert job["counts"]["invalid"] == 1


def test_a_job_where_nothing_could_be_generated_is_failed(client, job_body):
    job_id = client.post("/api/v1/jobs", json=job_body(
        [{"name": "", "email": "nope"}])).json()["job_id"]
    assert client.get(f"/api/v1/jobs/{job_id}").json()["status"] == "FAILED"


def test_unknown_job_returns_404(client):
    assert client.get("/api/v1/jobs/does-not-exist").status_code == 404