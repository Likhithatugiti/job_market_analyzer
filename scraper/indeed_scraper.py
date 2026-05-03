"""
scraper/indeed_scraper.py
Scrapes Indeed job search results using Selenium.
"""

import logging
from datetime import datetime
from urllib.parse import quote_plus

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException

from scraper.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

BASE_URL = "https://in.indeed.com/jobs"  # India domain — change for other regions


class IndeedScraper(BaseScraper):
    """Scrapes Indeed public job search results."""

    def scrape_page(self, page: int) -> list[dict]:
        start = (page - 1) * 10  # Indeed paginates by 10
        url = (
            f"{BASE_URL}?q={quote_plus(self.query)}"
            f"&l={quote_plus(self.location)}"
            f"&start={start}"
            f"&sort=date"
        )
        logger.debug(f"GET {url}")
        self.driver.get(url)
        self.random_sleep(1)

        try:
            self.wait.until(
                EC.presence_of_element_located((By.ID, "mosaic-provider-jobcards"))
            )
        except TimeoutException:
            logger.warning("Indeed job cards not found — may be blocked or empty")
            return []

        cards = self.driver.find_elements(
            By.CSS_SELECTOR, "div.job_seen_beacon"
        )
        logger.debug(f"Found {len(cards)} cards on page {page}")

        jobs = []
        for card in cards:
            job = self.parse_job_card(card)
            if job:
                jobs.append(job)

        return jobs

    def parse_job_card(self, card) -> dict | None:
        try:
            title = self.safe_find(card, By.CSS_SELECTOR, "span[title]")
            if not title:
                title = self.safe_find(card, By.CSS_SELECTOR, "h2.jobTitle span")

            company = self.safe_find(card, By.CSS_SELECTOR, "span.companyName")
            location = self.safe_find(card, By.CSS_SELECTOR, "div.companyLocation")
            salary_raw = self.safe_find(
                card, By.CSS_SELECTOR, "div.salary-snippet-container, div.metadata.salary-snippet"
            )
            date_raw = self.safe_find(card, By.CSS_SELECTOR, "span.date")

            # Build job URL from the anchor tag
            try:
                anchor = card.find_element(By.CSS_SELECTOR, "h2.jobTitle a")
                job_id = anchor.get_attribute("id") or ""
                job_url = f"https://in.indeed.com/viewjob?jk={job_id.replace('job_', '')}"
            except Exception:
                job_url = ""

            # Fetch full description
            description = ""
            if job_url:
                description = self._fetch_description(job_url)
                self.random_sleep(0.3)

            if not title:
                return None

            return {
                "source": "indeed",
                "title": title,
                "company": company,
                "location": location,
                "date_posted": date_raw,
                "job_url": job_url,
                "description": description,
                "salary_raw": salary_raw,
                "search_query": self.query,
                "search_location": self.location,
                "scraped_at": datetime.now().isoformat(),
            }

        except StaleElementReferenceException:
            return None
        except Exception as e:
            logger.warning(f"Indeed card parse error: {e}")
            return None

    def _fetch_description(self, url: str) -> str:
        self.driver.execute_script(f"window.open('{url}', '_blank');")
        self.driver.switch_to.window(self.driver.window_handles[-1])
        description = ""
        try:
            self.wait.until(
                EC.presence_of_element_located(
                    (By.ID, "jobDescriptionText")
                )
            )
            description = self.safe_find(
                self.driver, By.ID, "jobDescriptionText"
            )
        except TimeoutException:
            pass
        except Exception as e:
            logger.debug(f"Indeed detail error: {e}")
        finally:
            self.driver.close()
            self.driver.switch_to.window(self.driver.window_handles[0])
        return description
