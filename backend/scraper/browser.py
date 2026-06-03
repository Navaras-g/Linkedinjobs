"""Async Playwright browser/session helpers for LinkedIn scraping."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from playwright.async_api import BrowserContext, Page, Playwright, async_playwright

from backend.config import settings


class SessionExpiredError(Exception):
    """Raised when LinkedIn cookies are missing/expired and login is required."""


class LinkedInBrowserSession:
    """Manages a persistent Playwright context with cookie load/save support."""

    def __init__(self, cookies_path: str | None = None) -> None:
        project_root = Path(__file__).resolve().parents[2]
        configured_path = cookies_path or settings.cookies_path

        candidate_cookies_path = Path(configured_path).expanduser()
        if not candidate_cookies_path.is_absolute():
            candidate_cookies_path = (project_root / candidate_cookies_path).resolve()
        else:
            candidate_cookies_path = candidate_cookies_path.resolve()

        if candidate_cookies_path.parent != project_root:
            raise ValueError("COOKIES_PATH must resolve to a file in the project root directory.")

        self.cookies_path = candidate_cookies_path
        self.user_data_dir = (project_root / ".playwright-user-data").resolve()

        self._playwright: Playwright | None = None
        self.context: BrowserContext | None = None

    async def start(self) -> BrowserContext:
        """Start Playwright and open a persistent Chromium context."""
        self._playwright = await async_playwright().start()
        self.context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.user_data_dir),
            headless=True,
            viewport={"width": 1366, "height": 768},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
        )
        await self._load_cookies()
        return self.context

    async def close(self) -> None:
        """Persist cookies and close browser context/resources."""
        try:
            await self._save_cookies()
        finally:
            if self.context is not None:
                await self.context.close()
                self.context = None
            if self._playwright is not None:
                await self._playwright.stop()
                self._playwright = None

    async def new_page(self) -> Page:
        """Create a new page from the current context."""
        if self.context is None:
            raise RuntimeError("Browser context is not started. Call start() first.")
        return await self.context.new_page()

    async def ensure_session_valid(self, page: Page | None = None) -> None:
        """Validate authenticated session by checking LinkedIn login redirect."""
        if self.context is None:
            raise RuntimeError("Browser context is not started. Call start() first.")

        own_page = False
        target_page = page
        if target_page is None:
            target_page = await self.context.new_page()
            own_page = True

        try:
            await target_page.goto("https://www.linkedin.com/jobs/", wait_until="domcontentloaded")
            current_url = (target_page.url or "").lower()
            if "/login" in current_url or "linkedin.com/checkpoint" in current_url:
                raise SessionExpiredError(
                    "LinkedIn session is expired. Re-export cookies.json from your browser "
                    "and place it in the project root."
                )
        finally:
            if own_page:
                await target_page.close()

    async def _load_cookies(self) -> None:
        """Load cookies from configured cookies.json into the browser context."""
        if self.context is None or not self.cookies_path.exists():
            return

        raw = self.cookies_path.read_text(encoding="utf-8").strip()
        if not raw:
            return

        cookies: Any = json.loads(raw)
        if isinstance(cookies, dict):
            cookies = cookies.get("cookies", [])
        if not isinstance(cookies, list):
            return

        valid_same_site = {"Strict", "Lax", "None"}
        cleaned = []
        for cookie in cookies:
            if "sameSite" in cookie:
                val = str(cookie["sameSite"]).capitalize()
                cookie["sameSite"] = val if val in valid_same_site else "None"
            cookie.pop("hostOnly", None)
            cookie.pop("session", None)
            cookie.pop("storeId", None)
            cookie.pop("id", None)
            cleaned.append(cookie)

        await self.context.add_cookies(cleaned)

    async def _save_cookies(self) -> None:
        """Save updated browser cookies back to cookies.json."""
        if self.context is None:
            return

        self.cookies_path.parent.mkdir(parents=True, exist_ok=True)
        cookies = await self.context.cookies()
        self.cookies_path.write_text(json.dumps(cookies, indent=2), encoding="utf-8")