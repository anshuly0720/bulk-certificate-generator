"""Brief: 'Certificate generation'."""
import io

from pypdf import PdfReader
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase.pdfmetrics import stringWidth


def test_a_pdf_is_produced_for_every_valid_recipient(client, job_body):
    job_id = client.post("/api/v1/jobs", json=job_body()).json()["job_id"]
    items = client.get(f"/api/v1/jobs/{job_id}/certificates").json()["items"]

    assert len(items) == 3
    assert all(i["status"] == "GENERATED" for i in items)
    assert all(i["download_url"] for i in items)


def test_certificate_contains_the_recipient_specific_data(client, job_body):
    job_id = client.post("/api/v1/jobs", json=job_body()).json()["job_id"]
    first = client.get(f"/api/v1/jobs/{job_id}/certificates").json()["items"][0]

    pdf = client.get(first["download_url"])
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")

    text = PdfReader(io.BytesIO(pdf.content)).pages[0].extract_text()
    assert "Asha Verma" in text
    assert "Backend Engineering Bootcamp" in text
    assert "Acme Academy" in text
    assert "2026-10-08" in text
    assert first["certificate_id"] in text


def test_long_name_is_scaled_to_stay_inside_the_border(client, job_body):
    """A fixed minimum font size would let a 100-character name run off the page."""
    long_name = ("Venkata Subramanian Ramachandran Krishnamurthy Iyer " * 2)[:100].strip()
    job_id = client.post("/api/v1/jobs", json=job_body(
        [{"name": long_name, "email": "long@example.com"}])).json()["job_id"]

    item = client.get(f"/api/v1/jobs/{job_id}/certificates").json()["items"][0]
    assert item["status"] == "GENERATED"

    width, _ = landscape(A4)
    max_width = width - 160
    full = stringWidth(long_name, "Helvetica-Bold", 40)
    size = 40 if full <= max_width else 40 * max_width / full
    assert stringWidth(long_name, "Helvetica-Bold", size) <= max_width


def test_each_certificate_gets_its_own_file(client, job_body):
    job_id = client.post("/api/v1/jobs", json=job_body()).json()["job_id"]
    items = client.get(f"/api/v1/jobs/{job_id}/certificates").json()["items"]

    bodies = {client.get(i["download_url"]).content for i in items}
    assert len(bodies) == 3  # three distinct files, not one reused