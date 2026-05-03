"""
etl/cleaner.py
Cleans raw scraped job data:
  - Normalizes titles, companies, and locations
  - Parses salary strings into structured min/max/currency
  - Extracts skills from description text using regex patterns
  - Detects experience level
  - Deduplicates records
"""

import re
import logging
import hashlib
from typing import Optional

import pandas as pd
import numpy as np

from config.settings import SKILL_PATTERNS, EXPERIENCE_PATTERNS

logger = logging.getLogger(__name__)


class JobCleaner:
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()

    def run(self) -> pd.DataFrame:
        logger.info(f"Cleaning {len(self.df)} raw records")
        self.df = (
            self.df
            .pipe(self._drop_empty_titles)
            .pipe(self._normalize_text_fields)
            .pipe(self._parse_salary)
            .pipe(self._extract_skills)
            .pipe(self._detect_experience_level)
            .pipe(self._normalize_location)
            .pipe(self._add_job_id)
            .pipe(self._deduplicate)
        )
        logger.info(f"Cleaning done — {len(self.df)} records remain")
        return self.df

    # ── Step 1: Drop rows with no title ───────────────────────────────────────

    def _drop_empty_titles(self, df: pd.DataFrame) -> pd.DataFrame:
        before = len(df)
        df = df[df["title"].notna() & (df["title"].str.strip() != "")]
        logger.debug(f"drop_empty_titles: {before} → {len(df)}")
        return df.reset_index(drop=True)

    # ── Step 2: Normalize text ─────────────────────────────────────────────────

    def _normalize_text_fields(self, df: pd.DataFrame) -> pd.DataFrame:
        for col in ("title", "company", "location"):
            if col in df.columns:
                df[col] = (
                    df[col]
                    .fillna("")
                    .str.strip()
                    .str.replace(r"\s+", " ", regex=True)
                )
        # Normalize title: title-case and remove noise
        df["title"] = df["title"].str.title()
        df["title_normalized"] = (
            df["title"]
            .str.lower()
            .str.replace(r"[^a-z0-9\s/]", "", regex=True)
            .str.strip()
        )
        return df

    # ── Step 3: Parse salary ───────────────────────────────────────────────────

    def _parse_salary(self, df: pd.DataFrame) -> pd.DataFrame:
        df["salary_min"] = np.nan
        df["salary_max"] = np.nan
        df["salary_currency"] = ""
        df["salary_period"] = ""  # annual / monthly / hourly

        if "salary_raw" not in df.columns:
            return df

        df["salary_raw"] = df["salary_raw"].fillna("")
        parsed = df["salary_raw"].apply(self._parse_salary_string)
        df["salary_min"] = parsed.apply(lambda x: x["min"])
        df["salary_max"] = parsed.apply(lambda x: x["max"])
        df["salary_currency"] = parsed.apply(lambda x: x["currency"])
        df["salary_period"] = parsed.apply(lambda x: x["period"])

        # Annualize monthly/hourly figures
        df = self._annualize_salary(df)
        return df

    @staticmethod
    def _parse_salary_string(raw: str) -> dict:
        result = {"min": np.nan, "max": np.nan, "currency": "", "period": ""}
        if not raw:
            return result

        raw_lower = raw.lower()

        # Detect currency
        if "₹" in raw or "inr" in raw_lower or "lpa" in raw_lower:
            result["currency"] = "INR"
        elif "$" in raw or "usd" in raw_lower:
            result["currency"] = "USD"
        elif "£" in raw or "gbp" in raw_lower:
            result["currency"] = "GBP"

        # Detect period
        if re.search(r"\bper\s+hour\b|/hr\b|hourly", raw_lower):
            result["period"] = "hourly"
        elif re.search(r"\bper\s+month\b|/mo\b|monthly|p\.m\.", raw_lower):
            result["period"] = "monthly"
        else:
            result["period"] = "annual"

        # Handle "X LPA" format (Indian: Lakhs Per Annum)
        lpa_match = re.search(
            r"([\d.]+)\s*[-–to]+\s*([\d.]+)\s*lpa", raw_lower
        )
        if lpa_match:
            result["min"] = float(lpa_match.group(1)) * 100_000
            result["max"] = float(lpa_match.group(2)) * 100_000
            result["currency"] = "INR"
            result["period"] = "annual"
            return result

        single_lpa = re.search(r"([\d.]+)\s*lpa", raw_lower)
        if single_lpa:
            val = float(single_lpa.group(1)) * 100_000
            result["min"] = result["max"] = val
            result["currency"] = "INR"
            result["period"] = "annual"
            return result

        # Handle "X,000 – Y,000" or "X - Y" or "X to Y"
        range_match = re.search(
            r"([\d,]+(?:\.\d+)?)\s*[-–to]+\s*([\d,]+(?:\.\d+)?)", raw
        )
        if range_match:
            result["min"] = float(range_match.group(1).replace(",", ""))
            result["max"] = float(range_match.group(2).replace(",", ""))
            return result

        # Single number
        single = re.search(r"([\d,]+(?:\.\d+)?)", raw)
        if single:
            val = float(single.group(1).replace(",", ""))
            result["min"] = result["max"] = val

        return result

    @staticmethod
    def _annualize_salary(df: pd.DataFrame) -> pd.DataFrame:
        monthly_mask = df["salary_period"] == "monthly"
        hourly_mask = df["salary_period"] == "hourly"
        for col in ("salary_min", "salary_max"):
            df.loc[monthly_mask, col] = df.loc[monthly_mask, col] * 12
            df.loc[hourly_mask, col] = df.loc[hourly_mask, col] * 2080  # 40hr/wk
        return df

    # ── Step 4: Extract skills ─────────────────────────────────────────────────

    def _extract_skills(self, df: pd.DataFrame) -> pd.DataFrame:
        text_col = "description" if "description" in df.columns else "title"
        df["skills"] = df[text_col].fillna("").apply(self._extract_skills_from_text)
        df["skills_count"] = df["skills"].apply(len)
        return df

    @staticmethod
    def _extract_skills_from_text(text: str) -> list[str]:
        if not text:
            return []
        text_lower = text.lower()
        found = set()
        for pattern, canonical_name in SKILL_PATTERNS.items():
            if re.search(pattern, text_lower, re.IGNORECASE):
                found.add(canonical_name)
        return sorted(found)

    # ── Step 5: Experience level ───────────────────────────────────────────────

    def _detect_experience_level(self, df: pd.DataFrame) -> pd.DataFrame:
        def detect(row):
            text = f"{row.get('title', '')} {row.get('description', '')}".lower()
            for pattern, level in EXPERIENCE_PATTERNS.items():
                if re.search(pattern, text, re.IGNORECASE):
                    return level
            return "Not specified"

        df["experience_level"] = df.apply(detect, axis=1)
        return df

    # ── Step 6: Normalize location ─────────────────────────────────────────────

    def _normalize_location(self, df: pd.DataFrame) -> pd.DataFrame:
        CITY_MAP = {
            r"bengaluru|bangalore": "Bengaluru",
            r"mumbai|bombay": "Mumbai",
            r"delhi|new delhi|ncr": "Delhi NCR",
            r"hyderabad|hyd\b": "Hyderabad",
            r"chennai|madras": "Chennai",
            r"pune": "Pune",
            r"kolkata|calcutta": "Kolkata",
            r"remote|work from home|wfh": "Remote",
            r"hybrid": "Hybrid",
        }
        df["city"] = ""
        for pattern, city in CITY_MAP.items():
            mask = df["location"].str.contains(pattern, case=False, na=False, regex=True)
            df.loc[mask & (df["city"] == ""), "city"] = city
        df.loc[df["city"] == "", "city"] = df.loc[df["city"] == "", "location"].str.split(",").str[0].str.strip()
        return df

    # ── Step 7: Stable job ID (hash for dedup) ─────────────────────────────────

    def _add_job_id(self, df: pd.DataFrame) -> pd.DataFrame:
        def make_id(row):
            key = f"{row.get('source','')}{row.get('title','')}{row.get('company','')}{row.get('location','')}"
            return hashlib.md5(key.encode()).hexdigest()[:12]

        df["job_id"] = df.apply(make_id, axis=1)
        return df

    # ── Step 8: Deduplicate ────────────────────────────────────────────────────

    def _deduplicate(self, df: pd.DataFrame) -> pd.DataFrame:
        before = len(df)
        df = df.drop_duplicates(subset=["job_id"], keep="first")
        logger.debug(f"deduplicate: {before} → {len(df)}")
        return df.reset_index(drop=True)
