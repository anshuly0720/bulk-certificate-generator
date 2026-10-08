"""Brief: 'Creating a generation job'."""


def test_create_job_returns_202_with_counts(client, job_body):
    r = client.post("/api/v1/jobs", json=job_body())
    assert r.status_code == 202

    data = r.json()
    assert data["total"] == 3
    assert data["accepted"] == 3
    assert data["invalid"] == 0
    assert data["status"] == "PENDING"
    assert data["status_url"].endswith(data["job_id"])


def test_create_job_gives_each_job_its_own_id(client, job_body):
    first = client.post("/api/v1/jobs", json=job_body()).json()["job_id"]
    second = client.post("/api/v1/jobs", json=job_body()).json()["job_id"]
    assert first != second
    assert len(first) == 36  # uuid4, not a guessable counter


def test_create_job_accepts_a_bulk_request(client, job_body):
    rows = [{"name": f"Student {i}", "email": f"s{i}@example.com"} for i in range(250)]
    r = client.post("/api/v1/jobs", json=job_body(rows))
    assert r.status_code == 202
    assert r.json()["accepted"] == 250