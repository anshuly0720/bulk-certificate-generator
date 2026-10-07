from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import STORAGE_DIR
from app.database import SessionLocal
from app.generator import render_certificate
from app.models import Certificate, Job


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def job_counts(db: Session, job_id: str) -> dict[str, int]:
    counts = {"PENDING": 0, "GENERATED": 0, "FAILED": 0, "INVALID": 0}
    rows = db.execute(
        select(Certificate.status, func.count())
        .where(Certificate.job_id == job_id)
        .group_by(Certificate.status)
    ).all()
    for status, n in rows:
        counts[status] = n
    return counts


def process_job(job_id: str) -> None:
    """Runs outside the request. Takes only an id and opens its own session,
    so a queue worker or a restart hook could call it unchanged."""
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if job is None:
            return
        job.status = "PROCESSING"
        job.started_at = utcnow()
        db.commit()

        pending = db.scalars(
            select(Certificate)
            .where(Certificate.job_id == job_id, Certificate.status == "PENDING")
            .order_by(Certificate.row_index)
        ).all()

        out_dir = STORAGE_DIR / job_id
        out_dir.mkdir(parents=True, exist_ok=True)

        for cert in pending:
            try:
                path = out_dir / f"{cert.id}.pdf"
                render_certificate(
                    path,
                    name=cert.name,
                    course_name=job.course_name,
                    issuer=job.issuer,
                    issue_date=job.issue_date,
                    certificate_id=cert.id,
                )
                cert.status = "GENERATED"
                cert.file_path = str(path)
            except Exception as exc:  # one bad certificate must not stop the rest
                cert.status = "FAILED"
                cert.error = f"{type(exc).__name__}: {exc}"[:500]
            db.commit()  # after each row, so progress is visible while it runs

        counts = job_counts(db, job_id)
        if counts["GENERATED"] == 0:
            job.status = "FAILED"
        elif counts["FAILED"] or counts["INVALID"]:
            job.status = "COMPLETED_WITH_ERRORS"
        else:
            job.status = "COMPLETED"
        job.completed_at = utcnow()
        db.commit()