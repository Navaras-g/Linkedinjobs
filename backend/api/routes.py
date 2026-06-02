"""FastAPI route definitions for jobs, scrape control, and dashboard stats."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.db.crud import create_scrape_run, get_jobs, get_stats, update_job
from backend.db.database import SessionLocal
from backend.db.models import Job, ScrapeRun
from backend.scraper.scheduler import scrape_scheduler


router = APIRouter(prefix="/api", tags=["api"])


def get_db() -> Session:
    """Provide a per-request database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _job_to_dict(job: Job) -> dict[str, Any]:
    """Serialize Job ORM model to JSON-safe dict."""
    return {
        "id": job.id,
        "linkedin_id": job.linkedin_id,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "url": job.url,
        "posted_at": job.posted_at,
        "easy_apply": job.easy_apply,
        "description_html": job.description_html,
        "seen": job.seen,
        "saved": job.saved,
        "hidden": job.hidden,
        "scraped_at": job.scraped_at.isoformat() if job.scraped_at else None,
    }


def _scrape_run_to_dict(run: ScrapeRun) -> dict[str, Any]:
    """Serialize ScrapeRun ORM model to JSON-safe dict."""
    return {
        "id": run.id,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "jobs_found": run.jobs_found,
        "jobs_new": run.jobs_new,
        "status": run.status,
        "error": run.error,
    }


class JobPatchPayload(BaseModel):
    """Allowed mutable flags for a job card."""

    seen: bool | None = None
    saved: bool | None = None
    hidden: bool | None = None


@router.get("/jobs")
def list_jobs(
    seen: bool | None = None,
    saved: bool | None = None,
    hidden: bool = False,
    keyword: str | None = None,
    page: int = 1,
    per_page: int = 20,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return paginated jobs and total count."""
    jobs, total = get_jobs(
        db,
        seen=seen,
        saved=saved,
        hidden=hidden,
        keyword=keyword,
        page=page,
        per_page=per_page,
    )
    return {
        "items": [_job_to_dict(job) for job in jobs],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


@router.get("/jobs/{job_id}")
async def get_job(job_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    """
    Return one job.

    If description_html is missing, attempt to fetch and persist it.
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if not job.description_html and job.url:
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                response = await client.get(job.url)
            if response.status_code < 400:
                job.description_html = response.text
                db.commit()
                db.refresh(job)
        except Exception:
            # Best-effort enrichment: keep route functional if remote fetch fails.
            pass

    return _job_to_dict(job)


@router.patch("/jobs/{job_id}")
def patch_job(job_id: int, payload: JobPatchPayload, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Update mutable job flags."""
    job = update_job(
        db,
        job_id,
        seen=payload.seen,
        saved=payload.saved,
        hidden=payload.hidden,
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_to_dict(job)


@router.post("/scrape/trigger")
async def trigger_scrape() -> dict[str, Any]:
    """Kick off an immediate scrape run in background task."""
    db = SessionLocal()
    try:
        scrape_run = create_scrape_run(db, status="running", started_at=datetime.utcnow())
        run_id = scrape_run.id
    finally:
        db.close()

    asyncio.create_task(scrape_scheduler.trigger_scrape(run_id=run_id))
    return {"message": "Scrape started", "run_id": run_id}


@router.get("/scrape/status")
def get_scrape_status(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Return latest scrape run and next scheduled run time."""
    last_run = db.query(ScrapeRun).order_by(ScrapeRun.started_at.desc(), ScrapeRun.id.desc()).first()

    next_run: datetime | None = None
    if scrape_scheduler.scheduler.running:
        job = scrape_scheduler.scheduler.get_job("linkedin_scrape_job")
        if job is not None:
            next_run = job.next_run_time

    return {
        "last_run": _scrape_run_to_dict(last_run) if last_run else None,
        "next_run_time": next_run.isoformat() if next_run else None,
    }


@router.get("/stats")
def stats(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Return top-level dashboard stats."""
    data = get_stats(db)
    last_scraped_at = data.get("last_scraped_at")
    return {
        "total_jobs": data.get("total_jobs", 0),
        "unseen_count": data.get("unseen_count", 0),
        "saved_count": data.get("saved_count", 0),
        "last_scraped_at": last_scraped_at.isoformat() if hasattr(last_scraped_at, "isoformat") else None,
    }
