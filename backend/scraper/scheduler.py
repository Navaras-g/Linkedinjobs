"""APScheduler orchestration for periodic LinkedIn scrape runs."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.orm import Session

from backend.config import settings
from backend.db.crud import create_job, create_scrape_run, update_scrape_run
from backend.db.database import SessionLocal
from backend.db.models import Job as JobModel
from backend.scraper.browser import LinkedInBrowserSession, SessionExpiredError
from backend.scraper.extractor import extract_jobs


logger = logging.getLogger(__name__)


class ScrapeScheduler:
    """Manage scheduled and manual scrape runs."""

    def __init__(self) -> None:
        self.scheduler = AsyncIOScheduler()
        self._job_id = "linkedin_scrape_job"
        self._lock = asyncio.Lock()

    def start(self) -> None:
        """Start scheduler with configurable interval (default 6 hours)."""
        if self.scheduler.running:
            return

        interval_hours = max(1, int(settings.scrape_interval_hours))
        self.scheduler.add_job(
            self.run_scrape_job,
            trigger="interval",
            hours=interval_hours,
            id=self._job_id,
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        self.scheduler.start()
        logger.info("Scraper scheduler started with %s-hour interval", interval_hours)

    def shutdown(self) -> None:
        """Shutdown scheduler cleanly."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("Scraper scheduler shut down")

    async def trigger_scrape(self, run_id: int | None = None) -> int | None:
        """Trigger an immediate scrape and return created ScrapeRun id."""
        return await self.run_scrape_job(run_id=run_id)

    async def run_scrape_job(self, run_id: int | None = None) -> int | None:
        """Run one scrape cycle with deduplication and ScrapeRun logging."""
        async with self._lock:
            session: Session = SessionLocal()
            browser = LinkedInBrowserSession()
            if run_id is None:
                scrape_run = create_scrape_run(session, status="running", started_at=datetime.utcnow())
                run_id = scrape_run.id

            try:
                await browser.start()
                page = await browser.new_page()
                await browser.ensure_session_valid(page)
                scraped_jobs = await extract_jobs(page)

                jobs_found = len(scraped_jobs)
                linkedin_ids = [job.linkedin_id for job in scraped_jobs if job.linkedin_id]
                existing_ids = set()
                if linkedin_ids:
                    rows = session.query(JobModel.linkedin_id).filter(JobModel.linkedin_id.in_(linkedin_ids)).all()
                    existing_ids = {row[0] for row in rows}

                jobs_new = 0
                for job in scraped_jobs:
                    if not job.linkedin_id or job.linkedin_id in existing_ids:
                        continue

                    create_job(
                        session,
                        {
                            "linkedin_id": job.linkedin_id,
                            "title": job.title,
                            "company": job.company,
                            "location": job.location,
                            "url": job.url,
                            "posted_at": job.posted_at,
                            "easy_apply": job.easy_apply,
                        },
                    )
                    existing_ids.add(job.linkedin_id)
                    jobs_new += 1

                update_scrape_run(
                    session,
                    run_id,
                    status="success",
                    finished_at=datetime.utcnow(),
                    jobs_found=jobs_found,
                    jobs_new=jobs_new,
                )
                logger.info("Scrape run %s complete: found=%s new=%s", run_id, jobs_found, jobs_new)
                return run_id

            except SessionExpiredError as exc:
                update_scrape_run(
                    session,
                    run_id,
                    status="failed",
                    finished_at=datetime.utcnow(),
                    error=str(exc),
                )
                logger.error("Scrape run %s failed: session expired. %s", run_id, exc)
                return run_id

            except Exception as exc:  # noqa: BLE001
                update_scrape_run(
                    session,
                    run_id,
                    status="failed",
                    finished_at=datetime.utcnow(),
                    error=str(exc),
                )
                logger.exception("Scrape run %s failed with error", run_id)
                return run_id

            finally:
                try:
                    await browser.close()
                except Exception:  # noqa: BLE001
                    logger.exception("Failed to close browser resources")
                session.close()


scrape_scheduler = ScrapeScheduler()
