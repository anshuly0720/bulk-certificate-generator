from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Certificate, Job
from app.schemas import JobCreate
from app.validation import check_recipients

router = APIRouter(prefix="/api/v1")


@router.post("/jobs", status_code=202)
def create_job(body: JobCreate, db: Session = Depends(get_db)):
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

    return {
        "job_id": job.id,
        "status": job.status,
        "total": len(rows),
        "accepted": accepted,
        "invalid": invalid,
        "status_url": f"/api/v1/jobs/{job.id}",
    }