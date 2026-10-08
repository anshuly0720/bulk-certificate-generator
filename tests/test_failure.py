"""Brief: 'Handling an individual certificate failure'.

The requirement: one failure must not stop the other valid certificates in the
same job. The generator is patched to raise for one recipient only.
"""
import app.processor as processor


def test_one_failure_does_not_stop_the_rest(client, job_body, monkeypatch):
    real = processor.render_certificate

    def flaky(path, **kwargs):
        if kwargs["name"] == "Rahul Singh":
            raise RuntimeError("disk full (simulated)")
        return real(path, **kwargs)

    # patched where process_job looks the name up, not where it is defined
    monkeypatch.setattr(processor, "render_certificate", flaky)

    job_id = client.post("/api/v1/jobs", json=job_body()).json()["job_id"]
    job = client.get(f"/api/v1/jobs/{job_id}").json()

    assert job["status"] == "COMPLETED_WITH_ERRORS"
    assert job["counts"]["generated"] == 2
    assert job["counts"]["failed"] == 1


def test_the_failure_is_recorded_against_the_right_row(client, job_body, monkeypatch):
    real = processor.render_certificate

    def flaky(path, **kwargs):
        if kwargs["name"] == "Rahul Singh":
            raise RuntimeError("disk full (simulated)")
        return real(path, **kwargs)

    monkeypatch.setattr(processor, "render_certificate", flaky)
    job_id = client.post("/api/v1/jobs", json=job_body()).json()["job_id"]

    failed = client.get(f"/api/v1/jobs/{job_id}/certificates",
                        params={"status": "FAILED"}).json()["items"]
    assert len(failed) == 1
    assert failed[0]["name"] == "Rahul Singh"
    assert failed[0]["row_index"] == 1
    assert "disk full" in failed[0]["error"]
    assert failed[0]["download_url"] is None


def test_downloading_a_failed_certificate_returns_409(client, job_body, monkeypatch):
    def always_raises(path, **kwargs):
        raise OSError("no space left on device")

    monkeypatch.setattr(processor, "render_certificate", always_raises)
    job_id = client.post("/api/v1/jobs", json=job_body()).json()["job_id"]

    items = client.get(f"/api/v1/jobs/{job_id}/certificates").json()["items"]
    r = client.get(f"/api/v1/certificates/{items[0]['certificate_id']}/download")
    assert r.status_code == 409


def test_a_job_where_every_row_raises_is_failed(client, job_body, monkeypatch):
    def always_raises(path, **kwargs):
        raise OSError("no space left on device")

    monkeypatch.setattr(processor, "render_certificate", always_raises)
    job_id = client.post("/api/v1/jobs", json=job_body()).json()["job_id"]
    job = client.get(f"/api/v1/jobs/{job_id}").json()

    assert job["status"] == "FAILED"
    assert job["counts"]["failed"] == 3
    assert job["counts"]["generated"] == 0