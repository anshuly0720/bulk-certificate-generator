"""Brief: 'Retrieving generated certificates'."""
import io
import zipfile


def test_list_certificates_for_a_job(client, job_body):
    job_id = client.post("/api/v1/jobs", json=job_body()).json()["job_id"]
    data = client.get(f"/api/v1/jobs/{job_id}/certificates").json()

    assert [i["row_index"] for i in data["items"]] == [0, 1, 2]
    assert [i["name"] for i in data["items"]] == ["Asha Verma", "Rahul Singh", "Meera Nair"]


def test_list_supports_paging_and_filtering(client, job_body, recipients):
    job_id = client.post("/api/v1/jobs", json=job_body(
        recipients + [{"name": "", "email": "bad"}])).json()["job_id"]

    page = client.get(f"/api/v1/jobs/{job_id}/certificates",
                      params={"limit": 2, "offset": 1}).json()
    assert [i["row_index"] for i in page["items"]] == [1, 2]

    generated = client.get(f"/api/v1/jobs/{job_id}/certificates",
                           params={"status": "generated"}).json()["items"]
    assert len(generated) == 3  # the filter is case-insensitive


def test_download_a_single_certificate(client, job_body):
    job_id = client.post("/api/v1/jobs", json=job_body()).json()["job_id"]
    item = client.get(f"/api/v1/jobs/{job_id}/certificates").json()["items"][0]

    r = client.get(item["download_url"])
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")


def test_download_the_whole_job_as_a_zip(client, job_body):
    job_id = client.post("/api/v1/jobs", json=job_body()).json()["job_id"]

    r = client.get(f"/api/v1/jobs/{job_id}/download")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"

    names = zipfile.ZipFile(io.BytesIO(r.content)).namelist()
    assert names == ["00001-Asha_Verma.pdf", "00002-Rahul_Singh.pdf", "00003-Meera_Nair.pdf"]


def test_zip_skips_rows_that_produced_no_file(client, job_body, recipients):
    job_id = client.post("/api/v1/jobs", json=job_body(
        recipients + [{"name": "", "email": "bad"}])).json()["job_id"]

    r = client.get(f"/api/v1/jobs/{job_id}/download")
    assert len(zipfile.ZipFile(io.BytesIO(r.content)).namelist()) == 3


def test_retrieval_errors(client, job_body):
    assert client.get("/api/v1/jobs/nope/certificates").status_code == 404
    assert client.get("/api/v1/jobs/nope/download").status_code == 404
    assert client.get("/api/v1/certificates/nope/download").status_code == 404

    job_id = client.post("/api/v1/jobs", json=job_body(
        [{"name": "", "email": "bad"}])).json()["job_id"]
    r = client.get(f"/api/v1/jobs/{job_id}/download")
    assert r.status_code == 409  # nothing was generated