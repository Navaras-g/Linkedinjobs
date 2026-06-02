"""Database CRUD helpers for jobs and scraper run tracking."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from backend.db.models import Job, ScrapeRun


def create_job(session: Session, job_data: dict[str, Any]) -> Job:
    """Create a new job row if its LinkedIn ID is not already present."""
    linkedin_id = job_data.get("linkedin_id")
    if linkedin_id:
        existing = session.query(Job).filter(Job.linkedin_id == linkedin_id).first()
        if existing:
            return existing

    job = Job(**job_data)
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def get_jobs(
    session: Session,
    *,
    seen: bool | None = None,
    saved: bool | None = None,
    hidden: bool = False,
    keyword: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> tuple[list[Job], int]:
    """Return filtered/paginated jobs with the total matched count."""
    page = max(1, page)
    per_page = max(1, per_page)

    query = session.query(Job)

    if seen is not None:
        query = query.filter(Job.seen == seen)
    if saved is not None:
        query = query.filter(Job.saved == saved)
    if hidden is not None:
        query = query.filter(Job.hidden == hidden)
    if keyword:
        like_term = f"%{keyword.strip()}%"
        query = query.filter(or_(Job.title.ilike(like_term), Job.company.ilike(like_term)))

    total = query.count()
    jobs = (
        query.order_by(Job.scraped_at.desc(), Job.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return jobs, total


def update_job(
    session: Session,
    job_id: int,
    *,
    seen: bool | None = None,
    saved: bool | None = None,
    hidden: bool | None = None,
) -> Job | None:
    """Update mutable job flags and return the updated record."""
    job = session.query(Job).filter(Job.id == job_id).first()
    if not job:
        return None

    if seen is not None:
        job.seen = seen
    if saved is not None:
        job.saved = saved
    if hidden is not None:
        job.hidden = hidden

    session.commit()
    session.refresh(job)
    return job


def get_stats(session: Session) -> dict[str, Any]:
    """Return dashboard summary counts and latest scrape timestamp."""
    total_jobs = session.query(func.count(Job.id)).scalar() or 0
    unseen_count = session.query(func.count(Job.id)).filter(Job.seen.is_(False)).scalar() or 0
    saved_count = session.query(func.count(Job.id)).filter(Job.saved.is_(True)).scalar() or 0
    last_scraped_at = session.query(func.max(Job.scraped_at)).scalar()

    return {
        "total_jobs": total_jobs,
        "unseen_count": unseen_count,
        "saved_count": saved_count,
        "last_scraped_at": last_scraped_at,
    }


def create_scrape_run(
    session: Session,
    *,
    status: str = "running",
    started_at: datetime | None = None,
    jobs_found: int = 0,
    jobs_new: int = 0,
    error: str | None = None,
) -> ScrapeRun:
    """Create and persist a scrape run record."""
    scrape_run = ScrapeRun(
        status=status,
        started_at=started_at or datetime.utcnow(),
        jobs_found=jobs_found,
        jobs_new=jobs_new,
        error=error,
    )
    session.add(scrape_run)
    session.commit()
    session.refresh(scrape_run)
    return scrape_run


def update_scrape_run(
    session: Session,
    run_id: int,
    *,
    status: str | None = None,
    finished_at: datetime | None = None,
    jobs_found: int | None = None,
    jobs_new: int | None = None,
    error: str | None = None,
) -> ScrapeRun | None:
    """Update scrape run fields and return the updated record."""
    scrape_run = session.query(ScrapeRun).filter(ScrapeRun.id == run_id).first()
    if not scrape_run:
        return None

    if status is not None:
        scrape_run.status = status
    if finished_at is not None:
        scrape_run.finished_at = finished_at
    if jobs_found is not None:
        scrape_run.jobs_found = jobs_found
    if jobs_new is not None:
        scrape_run.jobs_new = jobs_new
    if error is not None:
        scrape_run.error = error

    session.commit()
    session.refresh(scrape_run)
    return scrape_run
