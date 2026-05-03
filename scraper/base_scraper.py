"""
scraper/base_scraper.py
Abstract base class that all scrapers inherit from.
Handles WebDriver setup, retry logic, and safe teardown.
"""

import time
import random
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import HEADLESS, DELAY_MIN, DELAY_MAX, MAX_RETRIES, RAW_DIR

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Abstract base — subclass and implement `scrape_page()` and `parse_job_card()`."""

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ]

    def __init__(self, query: str, location: str, max_pages: int = 3):
        self.query = query
        self.location = location
        self.max_pages = max_pages
        self.driver = None
        self.wait = None
        self.results: list[dict] = []
        self.run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.source_name = self.__class__.__name__.replace("Scraper", "").lower()

    # ── Driver setup ──────────────────────────────────────────────────────────

    def _build_driver(self) -> webdriver.Chrome:
        options = Options()
        if HEADLESS:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_argument(f"user-agent={random.choice(self.USER_AGENTS)}")
        options.add_argument("--window-size=1920,1080")

        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)

        # Mask webdriver fingerprint
        driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        return driver

    def start(self):
        logger.info(f"[{self.source_name}] Starting driver (headless={HEADLESS})")
        self.driver = self._build_driver()
        self.wait = WebDriverWait(self.driver, timeout=15)

    def stop(self):
        if self.driver:
            self.driver.quit()
            logger.info(f"[{self.source_name}] Driver closed")

    # ── Utilities ─────────────────────────────────────────────────────────────

    def random_sleep(self, extra: float = 0):
        delay = random.uniform(DELAY_MIN, DELAY_MAX) + extra
        logger.debug(f"Sleeping {delay:.1f}s")
        time.sleep(delay)

    def scroll_to_bottom(self, pause: float = 1.5):
        last_h = self.driver.execute_script("return document.body.scrollHeight")
        while True:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(pause)
            new_h = self.driver.execute_script("return document.body.scrollHeight")
            if new_h == last_h:
                break
            last_h = new_h

    def safe_find(self, parent, by, selector, default=""):
        try:
            return parent.find_element(by, selector).text.strip()
        except Exception:
            return default

    def safe_find_attr(self, parent, by, selector, attr, default=""):
        try:
            return parent.find_element(by, selector).get_attribute(attr) or default
        except Exception:
            return default

    # ── Public API ────────────────────────────────────────────────────────────

    def run(self) -> list[dict]:
        self.start()
        try:
            for page in range(1, self.max_pages + 1):
                logger.info(
                    f"[{self.source_name}] Scraping page {page}/{self.max_pages} "
                    f"— query='{self.query}' location='{self.location}'"
                )
                page_results = self._scrape_page_safe(page)
                self.results.extend(page_results)
                logger.info(
                    f"[{self.source_name}] Page {page}: {len(page_results)} jobs "
                    f"(total so far: {len(self.results)})"
                )
                if page < self.max_pages:
                    self.random_sleep()
        finally:
            self.stop()

        self._save_raw()
        return self.results

    @retry(stop=stop_after_attempt(MAX_RETRIES), wait=wait_exponential(min=2, max=10))
    def _scrape_page_safe(self, page: int) -> list[dict]:
        return self.scrape_page(page)

    def _save_raw(self):
        import json
        filename = RAW_DIR / f"{self.source_name}_{self.run_id}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "run_id": self.run_id,
                    "source": self.source_name,
                    "query": self.query,
                    "location": self.location,
                    "scraped_at": datetime.now().isoformat(),
                    "total_jobs": len(self.results),
                    "jobs": self.results,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )
        logger.info(f"Raw data saved → {filename}")

    # ── Abstract interface ─────────────────────────────────────────────────────

    @abstractmethod
    def scrape_page(self, page: int) -> list[dict]:
        """Scrape one results page and return a list of raw job dicts."""
        ...

    @abstractmethod
    def parse_job_card(self, card) -> dict | None:
        """Parse a single job card WebElement into a dict."""
        ...
