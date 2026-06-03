"""APScheduler orchestration for periodic LinkedIn scrape runs."""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.orm import Session

from backend.config import settings
from backend.db.crud import create_job, create_scrape_run, update_scrape_run
from backend.db.database import SessionLocal
from backend.db.models import Job as JobModel
from backend.scraper.browser import LinkedInBrowserSession, SessionExpiredError
from backend.scraper.extractor import extract_jobs


logger = logging.getLogger(__name__)


async def _run_scraper_in_new_loop() -> list:
    """Run the Playwright scraper in a fresh proactor event loop in a thread."""
    result = []
    exception_holder = []

    def thread_target():
        # Create a brand-new proactor event loop in this thread
        loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop(loop)
        try:
            result.extend(loop.run_until_complete(_do_scrape()))
        except Exception as e:
            exception_holder.append(e)
        finally:
            loop.close()

    async def _do_scrape():
        browser = LinkedInBrowserSession()
        await browser.start()
        try:
            page = await browser.new_page()
            await browser.ensure_session_valid(page)
            return await extract_jobs(page)
        finally:
            await browser.close()

    t = threading.Thread(target=thread_target, daemon=True)
    t.start()
    # Wait for thread without blocking uvicorn's event loop
    await asyncio.get_event_loop().run_in_executor(None, t.join)

    if exception_holder:
        raise exception_holder[0]

    return result


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
            if run_id is None:
                scrape_run = create_scrape_run(
                    session,
                    status="running",
                    started_at=datetime.now(timezone.utc),
                )
                run_id = scrape_run.id

            try:
                logger.info("[Scrape #%s] Starting scrape run in isolated thread", run_id)
                scraped_jobs = await _run_scraper_in_new_loop()
                logger.info("[Scrape #%s] Cards returned: %s", run_id, len(scraped_jobs))

                jobs_found = len(scraped_jobs)
                linkedin_ids = [job.linkedin_id for job in scraped_jobs if job.linkedin_id]
                existing_ids = set()
                if linkedin_ids:
                    rows = (
                        session.query(JobModel.linkedin_id)
                        .filter(JobModel.linkedin_id.in_(linkedin_ids))
                        .all()
                    )
                    existing_ids = {row[0] for row in rows}

                new_job_objects = []
                for job in scraped_jobs:
                    if not job.linkedin_id or job.linkedin_id in existing_ids:
                        continue
                    new_job_objects.append(
                        {
                            "linkedin_id": job.linkedin_id,
                            "title": job.title,
                            "company": job.company,
                            "location": job.location,
                            "url": job.url,
                            "posted_at": job.posted_at,
                            "easy_apply": job.easy_apply,
                        }
                    )
                    existing_ids.add(job.linkedin_id)

                # Batch insert all new jobs in one transaction
                for job_data in new_job_objects:
                    create_job(session, job_data)
                session.commit()
                jobs_new = len(new_job_objects)

                update_scrape_run(
                    session,
                    run_id,
                    status="success",
                    finished_at=datetime.now(timezone.utc),
                    jobs_found=jobs_found,
                    jobs_new=jobs_new,
                )
                logger.info(
                    "[Scrape #%s] Complete — found=%s new=%s",
                    run_id, jobs_found, jobs_new,
                )
                return run_id

            except SessionExpiredError as exc:
                update_scrape_run(
                    session,
                    run_id,
                    status="failed",
                    finished_at=datetime.now(timezone.utc),
                    error=str(exc),
                )
                logger.error("[Scrape #%s] Session expired: %s", run_id, exc)
                return run_id

            except Exception as exc:
                update_scrape_run(
                    session,
                    run_id,
                    status="failed",
                    finished_at=datetime.now(timezone.utc),
                    error=str(exc),
                )
                logger.exception("[Scrape #%s] Failed with error", run_id)
                return run_id

            finally:
                session.close()


scrape_scheduler = ScrapeScheduler()