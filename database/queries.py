"""
database/queries.py
Reusable analytical queries — returns pandas DataFrames.
Used by both analysis scripts and the Power BI export.
"""

import logging
import pandas as pd
from sqlalchemy import create_engine, text

from config.settings import DATABASE_URL

logger = logging.getLogger(__name__)
_engine = create_engine(DATABASE_URL, pool_pre_ping=True)


def run_query(sql: str, params: dict = None) -> pd.DataFrame:
    with _engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params=params or {})


# ─── Skills ───────────────────────────────────────────────────────────────────

def top_skills(limit: int = 30) -> pd.DataFrame:
    return run_query("""
        SELECT skill_name, job_count, pct_of_jobs
        FROM v_skill_demand
        LIMIT :limit
    """, {"limit": limit})


def skills_by_role(role_keyword: str) -> pd.DataFrame:
    return run_query("""
        SELECT js.skill_name, COUNT(*) AS freq
        FROM job_skills js
        JOIN jobs j ON js.job_id = j.job_id
        WHERE j.title_normalized ILIKE :kw
        GROUP BY js.skill_name
        ORDER BY freq DESC
        LIMIT 25
    """, {"kw": f"%{role_keyword}%"})


def skill_cooccurrence(top_n: int = 15) -> pd.DataFrame:
    """Returns a co-occurrence matrix for the top N skills."""
    top = top_skills(top_n)["skill_name"].tolist()
    if not top:
        return pd.DataFrame()

    placeholders = ", ".join(f"'{s}'" for s in top)
    sql = f"""
        SELECT a.skill_name AS skill_a,
               b.skill_name AS skill_b,
               COUNT(*)     AS co_count
        FROM job_skills a
        JOIN job_skills b ON a.job_id = b.job_id
            AND a.skill_name < b.skill_name
        WHERE a.skill_name IN ({placeholders})
          AND b.skill_name IN ({placeholders})
        GROUP BY a.skill_name, b.skill_name
        ORDER BY co_count DESC
    """
    return run_query(sql)


# ─── Salary ───────────────────────────────────────────────────────────────────

def salary_by_role(min_jobs: int = 5) -> pd.DataFrame:
    return run_query("""
        SELECT role, experience_level, city, job_count,
               avg_salary_min, avg_salary_max, median_salary, salary_currency
        FROM v_salary_by_role
        WHERE job_count >= :min_jobs
    """, {"min_jobs": min_jobs})


def salary_distribution(role_keyword: str = "") -> pd.DataFrame:
    filter_clause = "AND title_normalized ILIKE :kw" if role_keyword else ""
    return run_query(f"""
        SELECT salary_min, salary_max, salary_currency,
               experience_level, city, title_normalized
        FROM jobs
        WHERE salary_min IS NOT NULL
          {filter_clause}
    """, {"kw": f"%{role_keyword}%"} if role_keyword else {})


# ─── Location ─────────────────────────────────────────────────────────────────

def location_heatmap() -> pd.DataFrame:
    return run_query("SELECT * FROM v_location_heatmap")


# ─── Trends ───────────────────────────────────────────────────────────────────

def jobs_over_time() -> pd.DataFrame:
    return run_query("SELECT * FROM v_jobs_over_time ORDER BY week")


# ─── Companies ────────────────────────────────────────────────────────────────

def top_hiring_companies(limit: int = 20) -> pd.DataFrame:
    return run_query("""
        SELECT company, open_roles, avg_min_salary
        FROM v_top_companies
        LIMIT :limit
    """, {"limit": limit})


# ─── Overview stats (for Power BI KPIs) ──────────────────────────────────────

def overview_stats() -> dict:
    df = run_query("""
        SELECT
            COUNT(*)                                   AS total_jobs,
            COUNT(DISTINCT company)                    AS companies,
            COUNT(DISTINCT city)                       AS cities,
            COUNT(DISTINCT source)                     AS sources,
            ROUND(AVG(salary_min), 0)                 AS avg_salary,
            MIN(scraped_at)::DATE                      AS first_scraped,
            MAX(scraped_at)::DATE                      AS last_scraped
        FROM jobs
    """)
    return df.iloc[0].to_dict() if len(df) > 0 else {}
