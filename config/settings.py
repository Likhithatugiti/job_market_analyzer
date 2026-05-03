"""
config/settings.py
Central configuration — reads from .env and exposes typed constants.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
LOGS_DIR = BASE_DIR / "logs"

for d in (RAW_DIR, PROCESSED_DIR, LOGS_DIR):
    d.mkdir(parents=True, exist_ok=True)

load_dotenv(BASE_DIR / ".env")

# ── Database ───────────────────────────────────────────────────────────────────
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", 5432))
DB_NAME = os.getenv("DB_NAME", "job_market")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

DATABASE_URL = (
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# ── Scraper ────────────────────────────────────────────────────────────────────
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"
DELAY_MIN = float(os.getenv("SCRAPER_DELAY_MIN", 2))
DELAY_MAX = float(os.getenv("SCRAPER_DELAY_MAX", 5))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", 3))

LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL", "")
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD", "")

# ── Logging ────────────────────────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = LOGS_DIR / "pipeline.log"

# ── Skills taxonomy ────────────────────────────────────────────────────────────
# Canonical skill names — regex patterns mapped to clean display names
SKILL_PATTERNS = {
    # Languages
    r"\bpython\b": "Python",
    r"\br\b(?:\s+programming)?": "R",
    r"\bsql\b": "SQL",
    r"\bjava\b(?!script)": "Java",
    r"\bscala\b": "Scala",
    r"\bc\+\+": "C++",
    r"\bjavascript\b|\bjs\b": "JavaScript",

    # Data / ML
    r"\bpandas\b": "pandas",
    r"\bnumpy\b": "NumPy",
    r"\bscikit.?learn\b": "scikit-learn",
    r"\btensorflow\b": "TensorFlow",
    r"\bpytorch\b": "PyTorch",
    r"\bkeras\b": "Keras",
    r"\bsparkml\b|spark\s+ml\b": "Spark ML",
    r"\bxgboost\b": "XGBoost",

    # Big Data
    r"\bapache\s+spark\b|\bpyspark\b": "Apache Spark",
    r"\bhadoop\b": "Hadoop",
    r"\bkafka\b": "Kafka",
    r"\bairflow\b": "Airflow",
    r"\bdbt\b": "dbt",

    # Databases
    r"\bpostgresql\b|\bpostgres\b": "PostgreSQL",
    r"\bmysql\b": "MySQL",
    r"\bmongodb\b": "MongoDB",
    r"\bredis\b": "Redis",
    r"\bsnowflake\b": "Snowflake",
    r"\bbigquery\b": "BigQuery",

    # Cloud
    r"\baws\b|amazon\s+web\s+services": "AWS",
    r"\bazure\b": "Azure",
    r"\bgcp\b|google\s+cloud": "GCP",

    # BI / Viz
    r"\bpower\s*bi\b": "Power BI",
    r"\btableau\b": "Tableau",
    r"\blooker\b": "Looker",
    r"\bmatplotlib\b": "matplotlib",
    r"\bseaborn\b": "seaborn",

    # Tools
    r"\bgit\b": "Git",
    r"\bdocker\b": "Docker",
    r"\bkubernetes\b|\bk8s\b": "Kubernetes",
    r"\brest\s*api\b|restful": "REST API",
    r"\bexcel\b|microsoft\s+excel": "Excel",
    r"\bjupyter\b": "Jupyter",

    # Soft skills / domain
    r"\bmachine\s+learning\b|\bml\b": "Machine Learning",
    r"\bdeep\s+learning\b": "Deep Learning",
    r"\bdata\s+visualization\b": "Data Visualization",
    r"\bstatistic": "Statistics",
    r"\bnlp\b|natural\s+language\s+processing": "NLP",
    r"\bcomputer\s+vision\b": "Computer Vision",
    r"\bdata\s+engineering\b": "Data Engineering",
    r"\bdata\s+science\b": "Data Science",
    r"\bmlops\b": "MLOps",
    r"\bci/?cd\b": "CI/CD",
    r"\bagile\b": "Agile",
}

EXPERIENCE_PATTERNS = {
    r"fresher|entry.?level|0.?[–-]?1\s*year": "Entry Level",
    r"[1-3]\s*[–-]\s*[2-4]\s*year|junior": "Junior (1–3 yrs)",
    r"[3-6]\s*[–-]\s*[5-8]\s*year|mid.?level": "Mid Level (3–6 yrs)",
    r"[6-9]\s*[–-]?\+?\s*year|senior|lead": "Senior (6+ yrs)",
    r"manag|director|head\s+of|vp\b": "Management",
}
