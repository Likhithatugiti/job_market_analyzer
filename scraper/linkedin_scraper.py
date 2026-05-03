"""
scraper/linkedin_scraper.py
Scrapes LinkedIn Jobs search results using Selenium.
Does NOT require login for basic job card data.
For full job description (skills text), it opens each listing.
"""

import logging
import time
from datetime import datetime
from urllib.parse import quote_plus

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    StaleElementReferenceException,
)

from scraper.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

# LinkedIn public jobs URL (no login required)
BASE_URL = "https://www.linkedin.com/jobs/search"


class LinkedInScraper(BaseScraper):
    """Scrapes LinkedIn public job search results."""

    def scrape_page(self, page: int) -> list[dict]:
        start = (page - 1) * 25  # LinkedIn paginates by 25
        url = (
            f"{BASE_URL}?keywords={quote_plus(self.query)}"
            f"&location={quote_plus(self.location)}"
            f"&start={start}"
            f"&sortBy=DD"  # sort by date
        )
        logger.debug(f"GET {url}")
        self.driver.get(url)
        self.random_sleep(1)

        # Wait for job cards to appear
        try:
            self.wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "ul.jobs-search__results-list")
                )
            )
        except TimeoutException:
            logger.warning("Job list not found — page may be blocked or empty")
            return []

        self.scroll_to_bottom(pause=1.2)

        cards = self.driver.find_elements(
            By.CSS_SELECTOR, "ul.jobs-search__results-list > li"
        )
        logger.debug(f"Found {len(cards)} job cards on page {page}")

        jobs = []
        for card in cards:
            job = self.parse_job_card(card)
            if job:
                jobs.append(job)

        return jobs

    def parse_job_card(self, card) -> dict | None:
        try:
            title = self.safe_find(card, By.CSS_SELECTOR, "h3.base-search-card__title")
            company = self.safe_find(card, By.CSS_SELECTOR, "h4.base-search-card__subtitle")
            location = self.safe_find(card, By.CSS_SELECTOR, "span.job-search-card__location")
            date_posted = self.safe_find_attr(
                card, By.CSS_SELECTOR, "time.job-search-card__listdate", "datetime"
            )
            job_url = self.safe_find_attr(
                card, By.CSS_SELECTOR, "a.base-card__full-link", "href"
            )

            if not title:
                return None

            # Fetch job description by clicking into the listing
            description, salary = "", ""
            if job_url:
                description, salary = self._fetch_job_detail(job_url)
                self.random_sleep(0.5)

            return {
                "source": "linkedin",
                "title": title,
                "company": company,
                "location": location,
                "date_posted": date_posted,
                "job_url": job_url,
                "description": description,
                "salary_raw": salary,
                "search_query": self.query,
                "search_location": self.location,
                "scraped_at": datetime.now().isoformat(),
            }

        except StaleElementReferenceException:
            logger.debug("Stale element — skipping card")
            return None
        except Exception as e:
            logger.warning(f"Card parse error: {e}")
            return None

    def _fetch_job_detail(self, url: str) -> tuple[str, str]:
        """Opens a job detail page and extracts description + salary."""
        # Open in a new tab so we don't lose the results list
        self.driver.execute_script(f"window.open('{url}', '_blank');")
        self.driver.switch_to.window(self.driver.window_handles[-1])

        description, salary = "", ""
        try:
            self.wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "div.show-more-less-html__markup")
                )
            )
            description = self.safe_find(
                self.driver, By.CSS_SELECTOR, "div.show-more-less-html__markup"
            )
            # Salary is sometimes in a separate section
            salary = self.safe_find(
                self.driver,
                By.CSS_SELECTOR,
                "span.compensation__salary, div.salary-main-rail__salary-info",
            )
        except TimeoutException:
            pass
        except Exception as e:
            logger.debug(f"Detail fetch error for {url}: {e}")
        finally:
            self.driver.close()
            self.driver.switch_to.window(self.driver.window_handles[0])

        return description, salary
