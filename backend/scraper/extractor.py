"""LinkedIn jobs page extractor that returns normalized job dataclass objects."""

from __future__ import annotations

import random
import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

from playwright.async_api import Locator, Page


@dataclass(slots=True)
class Job:
    """Structured job card data extracted from LinkedIn."""

    title: str
    company: str
    location: str
    url: str
    linkedin_id: str
    easy_apply: bool
    posted_at: str


async def _random_delay(page: Page) -> None:
    """Sleep between interactions to reduce automation fingerprinting."""
    await page.wait_for_timeout(random.uniform(1.5, 4.0) * 1000)


def _extract_linkedin_id(job_url: str) -> str:
    """Extract LinkedIn job id from URL path or query params."""
    if not job_url:
        return ""

    view_match = re.search(r"/jobs/view/(\d+)", job_url)
    if view_match:
        return view_match.group(1)

    parsed = urlparse(job_url)
    params = parse_qs(parsed.query)
    if "currentJobId" in params and params["currentJobId"]:
        return params["currentJobId"][0]
    return ""


async def _card_text(card: Locator, selectors: list[str]) -> str:
    """Return first non-empty trimmed text found for selector candidates."""
    for selector in selectors:
        locator = card.locator(selector).first
        if await locator.count():
            text = (await locator.inner_text()).strip()
            if text:
                return text
    return ""


async def _card_url(card: Locator) -> str:
    """Return canonical job URL from a card."""
    link = card.locator("a.job-card-container__link, a.job-card-list__title, a[href*='/jobs/view/']").first
    if not await link.count():
        return ""

    href = (await link.get_attribute("href") or "").strip()
    if href.startswith("http://") or href.startswith("https://"):
        return href
    if href.startswith("/"):
        return f"https://www.linkedin.com{href}"
    return href


async def _extract_job_from_card(card: Locator) -> Job | None:
    """Parse a single LinkedIn job card into a Job dataclass."""
    title = await _card_text(card, [".job-card-list__title", ".job-card-container__link", "a[aria-label]"])
    company = await _card_text(
        card,
        [".job-card-container__primary-description", ".artdeco-entity-lockup__subtitle", ".job-card-container__company-name"],
    )
    location = await _card_text(
        card,
        [".job-card-container__metadata-item", ".artdeco-entity-lockup__caption", ".job-card-container__metadata-wrapper li"],
    )
    posted_at = await _card_text(card, [".job-card-container__footer-item", "time", ".job-card-list__footer-wrapper li"])
    url = await _card_url(card)
    linkedin_id = _extract_linkedin_id(url)

    card_text = ((await card.inner_text()) or "").lower()
    easy_apply = "easy apply" in card_text

    if not title or not company or not url or not linkedin_id:
        return None

    return Job(
        title=title,
        company=company,
        location=location,
        url=url,
        linkedin_id=linkedin_id,
        easy_apply=easy_apply,
        posted_at=posted_at,
    )


async def _scroll_jobs_page(page: Page, *, rounds: int = 12) -> None:
    """Incrementally scroll jobs page to trigger lazy-loaded cards."""
    previous_height = 0
    for _ in range(rounds):
        await page.evaluate("window.scrollBy(0, Math.floor(window.innerHeight * 0.9))")
        await _random_delay(page)

        current_height = await page.evaluate("document.body.scrollHeight")
        if current_height == previous_height:
            break
        previous_height = current_height


async def extract_jobs(page: Page) -> list[Job]:
    """Navigate LinkedIn jobs page, scroll, and return visible job cards."""
    await page.goto("https://www.linkedin.com/jobs/", wait_until="domcontentloaded")
    await _random_delay(page)
    await _scroll_jobs_page(page)

    cards = page.locator("li.jobs-search-results__list-item, .jobs-search-results-list__list-item")
    count = await cards.count()

    seen_ids: set[str] = set()
    jobs: list[Job] = []

    for idx in range(count):
        card = cards.nth(idx)
        parsed = await _extract_job_from_card(card)
        if not parsed:
            continue
        if parsed.linkedin_id in seen_ids:
            continue
        seen_ids.add(parsed.linkedin_id)
        jobs.append(parsed)

    return jobs
