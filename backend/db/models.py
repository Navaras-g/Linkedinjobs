"""ORM models for scraped jobs and scrape run history."""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from backend.db.database import Base


class Job(Base):
    """LinkedIn job posting record."""

    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    linkedin_id = Column(String, unique=True, nullable=False, index=True)
    title = Column(String, nullable=False)
    company = Column(String, nullable=False)
    location = Column(String, nullable=False)
    url = Column(String, nullable=False)
    posted_at = Column(String, nullable=False)
    easy_apply = Column(Boolean, default=False, nullable=False)
    description_html = Column(Text, nullable=True)
    seen = Column(Boolean, default=False, nullable=False)
    saved = Column(Boolean, default=False, nullable=False)
    hidden = Column(Boolean, default=False, nullable=False)
    scraped_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class ScrapeRun(Base):
    """Execution log for each scraper run."""

    __tablename__ = "scrape_runs"

    id = Column(Integer, primary_key=True, index=True)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at = Column(DateTime, nullable=True)
    jobs_found = Column(Integer, default=0, nullable=False)
    jobs_new = Column(Integer, default=0, nullable=False)
    status = Column(String, nullable=False)
    error = Column(Text, nullable=True)
