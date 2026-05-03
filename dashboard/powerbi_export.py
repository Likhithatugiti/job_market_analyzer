"""
dashboard/powerbi_export.py
Exports clean, Power BI-ready CSVs to data/processed/.
Run after ETL to refresh the dashboard data source.
"""

import logging
import pandas as pd
from pathlib import Path

from database.queries import (
    top_skills,
    skill_cooccurrence,
    salary_by_role,
    salary_distribution,
    location_heatmap,
    jobs_over_time,
    top_hiring_companies,
    overview_stats,
    run_query,
)
from config.settings import PROCESSED_DIR

logger = logging.getLogger(__name__)


class PowerBIExporter:

    def export_all(self):
        logger.info("Exporting Power BI datasets...")
        exports = [
            ("jobs_clean.csv",          self._jobs_clean),
            ("skills_frequency.csv",    self._skills_frequency),
            ("skill_cooccurrence.csv",  self._skill_cooccurrence),
            ("salary_bands.csv",        self._salary_bands),
            ("location_heatmap.csv",    self._location_heatmap),
            ("jobs_over_time.csv",      self._jobs_over_time),
            ("top_companies.csv",       self._top_companies),
            ("overview_kpis.csv",       self._overview_kpis),
        ]
        for filename, fn in exports:
            try:
                df = fn()
                out = PROCESSED_DIR / filename
                df.to_csv(out, index=False, encoding="utf-8-sig")
                logger.info(f"  ✓ {filename} ({len(df)} rows)")
            except Exception as e:
                logger.error(f"  ✗ {filename}: {e}")

        logger.info(f"All exports saved to {PROCESSED_DIR}")

    # ── Individual exports ────────────────────────────────────────────────────

    def _jobs_clean(self) -> pd.DataFrame:
        return run_query("""
            SELECT
                j.job_id,
                j.source,
                j.title,
                j.title_normalized,
                j.company,
                j.location,
                j.city,
                j.date_posted,
                j.experience_level,
                j.salary_min,
                j.salary_max,
                j.salary_currency,
                j.salary_period,
                j.search_query,
                j.scraped_at::DATE AS scraped_date,
                STRING_AGG(js.skill_name, ', ' ORDER BY js.skill_name) AS skills
            FROM jobs j
            LEFT JOIN job_skills js ON j.job_id = js.job_id
            GROUP BY j.job_id, j.source, j.title, j.title_normalized,
                     j.company, j.location, j.city, j.date_posted,
                     j.experience_level, j.salary_min, j.salary_max,
                     j.salary_currency, j.salary_period, j.search_query, j.scraped_at
            ORDER BY j.scraped_at DESC
        """)

    def _skills_frequency(self) -> pd.DataFrame:
        return top_skills(50)

    def _skill_cooccurrence(self) -> pd.DataFrame:
        return skill_cooccurrence(20)

    def _salary_bands(self) -> pd.DataFrame:
        return salary_by_role(min_jobs=3)

    def _location_heatmap(self) -> pd.DataFrame:
        return location_heatmap()

    def _jobs_over_time(self) -> pd.DataFrame:
        return jobs_over_time()

    def _top_companies(self) -> pd.DataFrame:
        return top_hiring_companies(30)

    def _overview_kpis(self) -> pd.DataFrame:
        stats = overview_stats()
        return pd.DataFrame([stats])
