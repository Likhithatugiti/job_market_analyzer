"""
tests/test_cleaner.py
Unit tests for the ETL cleaning layer.
Run with: pytest tests/ -v
"""

import pytest
import pandas as pd
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from etl.cleaner import JobCleaner


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_df():
    return pd.DataFrame([
        {
            "source": "linkedin",
            "title": "  data analyst  ",
            "company": "Acme Corp",
            "location": "Bangalore, Karnataka, India",
            "date_posted": "2024-03-15",
            "job_url": "https://linkedin.com/jobs/1",
            "description": (
                "We're looking for a Data Analyst with strong Python, SQL, "
                "pandas, Power BI, and Excel skills. Experience with PostgreSQL "
                "and Tableau a plus. 2-4 years experience required."
            ),
            "salary_raw": "8 - 14 LPA",
            "search_query": "Data Analyst",
            "search_location": "Bangalore",
            "scraped_at": "2024-03-15T10:00:00",
        },
        {
            "source": "indeed",
            "title": "Machine Learning Engineer",
            "company": "TechStart",
            "location": "Hyderabad, Telangana",
            "date_posted": "2024-03-14",
            "job_url": "https://indeed.com/jobs/2",
            "description": (
                "Senior ML Engineer needed. TensorFlow, PyTorch, Python, "
                "Kubernetes, Docker, AWS required. 6+ years experience."
            ),
            "salary_raw": "₹25,00,000 - ₹40,00,000",
            "search_query": "ML Engineer",
            "search_location": "Hyderabad",
            "scraped_at": "2024-03-14T11:30:00",
        },
        {
            "source": "linkedin",
            "title": "",  # should be dropped
            "company": "Ghost Inc",
            "location": "Remote",
            "date_posted": None,
            "job_url": "",
            "description": "",
            "salary_raw": "",
            "search_query": "Data Analyst",
            "search_location": "India",
            "scraped_at": "2024-03-13T09:00:00",
        },
    ])


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestJobCleaner:

    def test_drops_empty_titles(self, sample_df):
        cleaned = JobCleaner(sample_df).run()
        assert len(cleaned) == 2, "Row with empty title should be dropped"
        assert all(cleaned["title"].str.strip() != "")

    def test_title_normalized(self, sample_df):
        cleaned = JobCleaner(sample_df).run()
        assert "title_normalized" in cleaned.columns
        assert cleaned["title_normalized"].str.lower().equals(cleaned["title_normalized"])

    def test_salary_parsing_lpa(self, sample_df):
        cleaned = JobCleaner(sample_df).run()
        row = cleaned[cleaned["source"] == "linkedin"].iloc[0]
        assert row["salary_min"] == pytest.approx(800_000)
        assert row["salary_max"] == pytest.approx(1_400_000)
        assert row["salary_currency"] == "INR"
        assert row["salary_period"] == "annual"

    def test_salary_parsing_rupee_range(self, sample_df):
        cleaned = JobCleaner(sample_df).run()
        row = cleaned[cleaned["source"] == "indeed"].iloc[0]
        assert row["salary_min"] == pytest.approx(2_500_000)
        assert row["salary_max"] == pytest.approx(4_000_000)

    def test_skill_extraction(self, sample_df):
        cleaned = JobCleaner(sample_df).run()
        analyst_row = cleaned[cleaned["title"].str.lower().str.contains("analyst")].iloc[0]
        skills = analyst_row["skills"]
        assert "Python" in skills
        assert "SQL" in skills
        assert "Power BI" in skills
        assert "pandas" in skills

    def test_skills_ml_engineer(self, sample_df):
        cleaned = JobCleaner(sample_df).run()
        ml_row = cleaned[cleaned["title"].str.lower().str.contains("machine")].iloc[0]
        skills = ml_row["skills"]
        assert "TensorFlow" in skills
        assert "PyTorch" in skills
        assert "Docker" in skills
        assert "AWS" in skills

    def test_experience_level_detection(self, sample_df):
        cleaned = JobCleaner(sample_df).run()
        analyst_row = cleaned[cleaned["title"].str.lower().str.contains("analyst")].iloc[0]
        assert analyst_row["experience_level"] in (
            "Junior (1–3 yrs)", "Mid Level (3–6 yrs)", "Not specified"
        )

    def test_location_normalization(self, sample_df):
        cleaned = JobCleaner(sample_df).run()
        bangalore_row = cleaned[cleaned["location"].str.contains("Bangalore", na=False)].iloc[0]
        assert bangalore_row["city"] == "Bengaluru"

    def test_job_id_generated(self, sample_df):
        cleaned = JobCleaner(sample_df).run()
        assert "job_id" in cleaned.columns
        assert cleaned["job_id"].notna().all()
        assert cleaned["job_id"].str.len().eq(12).all()

    def test_no_duplicate_job_ids(self, sample_df):
        # Add a duplicate
        dup = sample_df.iloc[[0]].copy()
        df_with_dup = pd.concat([sample_df, dup], ignore_index=True)
        cleaned = JobCleaner(df_with_dup).run()
        assert cleaned["job_id"].nunique() == len(cleaned)

    def test_skills_count_column(self, sample_df):
        cleaned = JobCleaner(sample_df).run()
        assert "skills_count" in cleaned.columns
        assert (cleaned["skills_count"] >= 0).all()


# ── Salary parser unit tests ──────────────────────────────────────────────────

class TestSalaryParser:
    parse = staticmethod(JobCleaner._parse_salary_string)

    def test_lpa_range(self):
        r = self.parse("8 - 14 LPA")
        assert r["min"] == 800_000
        assert r["max"] == 1_400_000
        assert r["currency"] == "INR"

    def test_single_lpa(self):
        r = self.parse("12 LPA")
        assert r["min"] == r["max"] == 1_200_000

    def test_usd_range(self):
        r = self.parse("$80,000 – $120,000")
        assert r["min"] == 80_000
        assert r["max"] == 120_000
        assert r["currency"] == "USD"

    def test_monthly_period(self):
        r = self.parse("₹60,000 per month")
        assert r["period"] == "monthly"

    def test_empty_string(self):
        r = self.parse("")
        assert r["min"] is np.nan or r["min"] != r["min"]  # NaN

    def test_no_salary(self):
        r = self.parse("Competitive salary")
        assert r["currency"] == ""
