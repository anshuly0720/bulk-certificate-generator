from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
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