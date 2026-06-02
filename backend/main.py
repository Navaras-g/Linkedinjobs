"""FastAPI application entrypoint with scheduler lifecycle and CORS setup."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router as api_router
from backend.scraper.scheduler import scrape_scheduler


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Start and stop background scheduler with app lifecycle."""
    scrape_scheduler.start()
    try:
        yield
    finally:
        scrape_scheduler.shutdown()


app = FastAPI(title="linkedin-jobs", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
