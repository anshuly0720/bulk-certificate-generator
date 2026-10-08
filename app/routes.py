import io
import re
import zipfile

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Certificate, Job
from app.processor import job_counts, process_job
from app.schemas import JobCreate
from app.validation import check_recipients

router = APIRouter(prefix="/api/v1")


@router.post("/jobs", status_code=202)
def create_job(body: JobCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    job = Job(
        course_name=body.course_name,
        issuer=body.issuer,
        issue_date=body.issue_date,
        status="PENDING",
    )
    db.add(job)
    db.flush()  # gives the job its id before the certificate rows reference it

    rows = []
    accepted = invalid = 0
    for result in check_recipients(body.recipients):
        if result["error"]:
            invalid += 1
            status = "INVALID"
        else:
            accepted += 1
            status = "PENDING"
        rows.append(Certificate(
            job_id=job.id,
            row_index=result["index"],
            name=result["name"],
            email=result["email"],
            status=status,
            error=result["error"],
        ))
    db.add_all(rows)
    db.commit()
    background_tasks.add_task(process_job, job.id)
    return {
        "job_id": job.id,
        "status": job.status,
        "total": len(rows),
        "accepted": accepted,
        "invalid": invalid,
        "status_url": f"/api/v1/jobs/{job.id}",
    }
@router.get("/jobs/{job_id}")
def get_job(job_id: str, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "Job not found")

    counts = job_counts(db, job_id)
    total = sum(counts.values())
    done = total - counts["PENDING"]
    return {
        "job_id": job.id,
        "status": job.status,
        "course_name": job.course_name,
        "issuer": job.issuer,
        "issue_date": job.issue_date,
        "counts": {
            "total": total,
            "pending": counts["PENDING"],
            "generated": counts["GENERATED"],
            "failed": counts["FAILED"],
            "invalid": counts["INVALID"],
        },
        "progress_percent": round(100 * done / total, 1) if total else 100.0,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
    }

@router.get("/jobs/{job_id}/certificates")
def list_certificates(
    job_id: str,
    status: str | None = Query(None, description="Filter by PENDING, GENERATED, FAILED or INVALID"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    if db.get(Job, job_id) is None:
        raise HTTPException(404, "Job not found")

    query = select(Certificate).where(Certificate.job_id == job_id)
    if status:
        query = query.where(Certificate.status == status.upper())
    certs = db.scalars(query.order_by(Certificate.row_index).limit(limit).offset(offset)).all()

    return {
        "job_id": job_id,
        "limit": limit,
        "offset": offset,
        "items": [
            {
                "certificate_id": c.id,
                "row_index": c.row_index,
                "name": c.name,
                "email": c.email,
                "status": c.status,
                "error": c.error,
                "download_url": (
                    f"/api/v1/certificates/{c.id}/download" if c.status == "GENERATED" else None
                ),
            }
            for c in certs
        ],
    }


@router.get("/certificates/{certificate_id}/download")
def download_certificate(certificate_id: str, db: Session = Depends(get_db)):
    cert = db.get(Certificate, certificate_id)
    if cert is None:
        raise HTTPException(404, "Certificate not found")
    if cert.status != "GENERATED":
        raise HTTPException(409, f"Certificate is {cert.status}; there is no file to download")
    return FileResponse(
        cert.file_path,
        media_type="application/pdf",
        filename=f"certificate-{cert.id}.pdf",
    )


@router.get("/jobs/{job_id}/download")
def download_job_zip(job_id: str, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    if job.status in ("PENDING", "PROCESSING"):
        raise HTTPException(409, "Job is still running; try again when it has finished")

    certs = db.scalars(
        select(Certificate)
        .where(Certificate.job_id == job_id, Certificate.status == "GENERATED")
        .order_by(Certificate.row_index)
    ).all()
    if not certs:
        raise HTTPException(409, "This job produced no certificates")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for c in certs:
            safe = re.sub(r"[^A-Za-z0-9_-]+", "_", c.name or "").strip("_")[:60] or "certificate"
            archive.write(c.file_path, arcname=f"{c.row_index + 1:05d}-{safe}.pdf")

    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="certificates-{job_id}.zip"'},
    )