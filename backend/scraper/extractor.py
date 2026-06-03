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
    title_raw = await _card_text(card, [".job-card-list__title", ".job-card-container__link", "a[aria-label]"])
    # Deduplicate repeated title lines
    title_lines = [l.strip() for l in title_raw.splitlines() if l.strip()]
    seen_lines: list[str] = []
    for line in title_lines:
        if line not in seen_lines:
            seen_lines.append(line)
    title = seen_lines[0] if seen_lines else ""

    company = await _card_text(
        card,
        [".job-card-container__primary-description", ".artdeco-entity-lockup__subtitle", ".job-card-container__company-name"],
    )
    location = await _card_text(
        card,
        [".job-card-container__metadata-item", ".artdeco-entity-lockup__caption", ".job-card-container__metadata-wrapper li"],
    )

    posted_raw = await _card_text(card, [".job-card-container__footer-item", "time", ".job-card-list__footer-wrapper li"])
    # Take only the first line, skip noise like "Promoted", "Viewed"
    posted_lines = [l.strip() for l in posted_raw.splitlines() if l.strip()]
    skip_values = {"promoted", "viewed", "featured"}
    posted_at = next((l for l in posted_lines if l.lower() not in skip_values), posted_raw.splitlines()[0].strip() if posted_lines else "")

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


async def _scroll_jobs_page(page: Page, *, rounds: int = 20) -> None:
    """Incrementally scroll jobs page to trigger lazy-loaded cards."""
    container_js = """
        (function() {
            const selectors = [
                '.jobs-job-board-list',
                '.discovery-templates-vertical-list',
                '.scaffold-layout__list',
                '.jobs-search-results-list'
            ];
            for (const sel of selectors) {
                const el = document.querySelector(sel);
                if (el) { el.scrollBy(0, 800); return true; }
            }
            window.scrollBy(0, Math.floor(window.innerHeight * 0.9));
            return false;
        })()
    """
    previous_count = 0
    stale_rounds = 0
    for _ in range(rounds):
        await page.evaluate(container_js)
        await _random_delay(page)

        current_count = await page.evaluate(
            "document.querySelectorAll('[data-occludable-job-id], [data-job-id], li.discovery-templates-entity-item').length"
        )
        if current_count == previous_count:
            stale_rounds += 1
            if stale_rounds >= 3:
                break
        else:
            stale_rounds = 0
        previous_count = current_count


JOBS_URL = "https://www.linkedin.com/jobs/collections/recommended/?discover=recommended&discoveryOrigin=JOBS_HOME_JYMBII"

# Ordered fallback selectors for the recommended feed card container
CARD_SELECTORS = [
    "li.discovery-templates-entity-item",
    "li.jobs-job-board-list__item",
    "li[data-occludable-job-id]",
    "div[data-job-id]",
    "li.scaffold-layout__list-item",
]


async def extract_jobs(page: Page) -> list[Job]:
    """Navigate LinkedIn recommended jobs page, scroll, and return visible job cards."""
    await page.goto(JOBS_URL, wait_until="domcontentloaded", timeout=30000)
    await _random_delay(page)

    # Wait for at least one job card to appear before scrolling
    try:
        await page.wait_for_selector(
            ", ".join(CARD_SELECTORS),
            timeout=15000,
        )
    except Exception:
        import logging
        logging.getLogger(__name__).warning(
            "No job cards appeared after 15s — page title: %s", await page.title()
        )
        return []

    await _scroll_jobs_page(page)

    # Try each selector, use first that returns results
    cards = None
    count = 0
    for selector in CARD_SELECTORS:
        candidate = page.locator(selector)
        n = await candidate.count()
        if n > 0:
            cards = candidate
            count = n
            import logging
            logging.getLogger(__name__).info("Using selector '%s' — found %d cards", selector, n)
            break

    if cards is None or count == 0:
        import logging
        logging.getLogger(__name__).warning(
            "All selectors returned 0 cards. Page title: %s", await page.title()
        )
        return []

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
