"""
etl/loader.py
Loads cleaned job data into PostgreSQL using SQLAlchemy.
Handles upserts so re-running the pipeline doesn't duplicate records.
"""

import logging
from datetime import datetime

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from config.settings import DATABASE_URL

logger = logging.getLogger(__name__)


class PostgresLoader:
    def __init__(self):
        self.engine = create_engine(DATABASE_URL, pool_pre_ping=True)

    # ── Main entry point ──────────────────────────────────────────────────────

    def load(self, df: pd.DataFrame, run_id: str = "") -> dict:
        """
        Load a cleaned DataFrame into the database.
        Returns a summary dict with insert/skip counts.
        """
        stats = {"inserted": 0, "skipped": 0, "skills_inserted": 0}
        run_id = run_id or datetime.now().strftime("%Y%m%d_%H%M%S")

        with self.engine.begin() as conn:
            for _, row in df.iterrows():
                inserted = self._upsert_job(conn, row)
                if inserted:
                    stats["inserted"] += 1
                    n_skills = self._upsert_skills(conn, row)
                    stats["skills_inserted"] += n_skills
                else:
                    stats["skipped"] += 1

            self._log_run(conn, run_id, df, stats)

        logger.info(
            f"Load complete — inserted: {stats['inserted']}, "
            f"skipped: {stats['skipped']}, skills: {stats['skills_inserted']}"
        )
        return stats

    # ── Upserts ───────────────────────────────────────────────────────────────

    def _upsert_job(self, conn, row: pd.Series) -> bool:
        """Insert job; skip if job_id already exists. Returns True if inserted."""
        sql = text("""
            INSERT INTO jobs (
                job_id, source, title, title_normalized, company,
                location, city, date_posted, job_url,
                salary_raw, salary_min, salary_max,
                salary_currency, salary_period,
                experience_level, description,
                search_query, search_location, scraped_at
            )
            VALUES (
                :job_id, :source, :title, :title_normalized, :company,
                :location, :city, :date_posted, :job_url,
                :salary_raw, :salary_min, :salary_max,
                :salary_currency, :salary_period,
                :experience_level, :description,
                :search_query, :search_location, :scraped_at
            )
            ON CONFLICT (job_id) DO NOTHING
            RETURNING job_id
        """)

        params = {
            "job_id": row.get("job_id", ""),
            "source": row.get("source", ""),
            "title": row.get("title", ""),
            "title_normalized": row.get("title_normalized", ""),
            "company": row.get("company", ""),
            "location": row.get("location", ""),
            "city": row.get("city", ""),
            "date_posted": self._safe_date(row.get("date_posted")),
            "job_url": row.get("job_url", ""),
            "salary_raw": row.get("salary_raw", ""),
            "salary_min": self._safe_float(row.get("salary_min")),
            "salary_max": self._safe_float(row.get("salary_max")),
            "salary_currency": row.get("salary_currency", ""),
            "salary_period": row.get("salary_period", ""),
            "experience_level": row.get("experience_level", ""),
            "description": row.get("description", "")[:10_000],  # clamp
            "search_query": row.get("search_query", ""),
            "search_location": row.get("search_location", ""),
            "scraped_at": row.get("scraped_at", datetime.now().isoformat()),
        }

        result = conn.execute(sql, params)
        return result.rowcount > 0

    def _upsert_skills(self, conn, row: pd.Series) -> int:
        """Insert skills and create job_skills links. Returns count inserted."""
        skills = row.get("skills", [])
        if not skills:
            return 0

        inserted = 0
        for skill_name in skills:
            # Ensure skill exists in skills table
            conn.execute(
                text("""
                    INSERT INTO skills (skill_name)
                    VALUES (:skill_name)
                    ON CONFLICT (skill_name) DO NOTHING
                """),
                {"skill_name": skill_name},
            )

            # Link job ↔ skill
            result = conn.execute(
                text("""
                    INSERT INTO job_skills (job_id, skill_name)
                    VALUES (:job_id, :skill_name)
                    ON CONFLICT DO NOTHING
                    RETURNING job_id
                """),
                {"job_id": row["job_id"], "skill_name": skill_name},
            )
            inserted += result.rowcount

        return inserted

    def _log_run(self, conn, run_id: str, df: pd.DataFrame, stats: dict):
        conn.execute(
            text("""
                INSERT INTO scrape_runs (run_id, source, query, location,
                    total_scraped, inserted, skipped, ran_at)
                VALUES (:run_id, :source, :query, :location,
                    :total_scraped, :inserted, :skipped, :ran_at)
                ON CONFLICT (run_id) DO NOTHING
            """),
            {
                "run_id": run_id,
                "source": df["source"].iloc[0] if len(df) > 0 else "",
                "query": df["search_query"].iloc[0] if len(df) > 0 else "",
                "location": df["search_location"].iloc[0] if len(df) > 0 else "",
                "total_scraped": len(df),
                "inserted": stats["inserted"],
                "skipped": stats["skipped"],
                "ran_at": datetime.now(),
            },
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _safe_float(val) -> float | None:
        try:
            f = float(val)
            return None if (f != f) else f  # NaN check
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_date(val) -> str | None:
        if not val or str(val).strip() in ("", "nan"):
            return None
        return str(val)[:10]  # keep only YYYY-MM-DD portion

    # ── Convenience: load from CSV ─────────────────────────────────────────────

    def load_from_csv(self, filepath: str) -> dict:
        import ast
        df = pd.read_csv(filepath)
        # skills column stored as string repr of list
        if "skills" in df.columns:
            df["skills"] = df["skills"].apply(
                lambda x: ast.literal_eval(x) if isinstance(x, str) and x.startswith("[") else []
            )
        return self.load(df)
