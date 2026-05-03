"""
main.py
Pipeline entry point — orchestrates scrape → ETL → analyze → export.

Usage:
    python main.py --source linkedin --query "Data Analyst" --location "Hyderabad" --pages 5
    python main.py --stage etl
    python main.py --stage analyze
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from datetime import datetime

import pandas as pd

# ── Logging setup ─────────────────────────────────────────────────────────────
from config.settings import LOG_LEVEL, LOG_FILE

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)-8s] %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
logger = logging.getLogger("pipeline")


# ── Stage functions ────────────────────────────────────────────────────────────

def stage_scrape(args) -> list[dict]:
    if args.source == "linkedin":
        from scraper.linkedin_scraper import LinkedInScraper
        scraper = LinkedInScraper(
            query=args.query, location=args.location, max_pages=args.pages
        )
    elif args.source == "indeed":
        from scraper.indeed_scraper import IndeedScraper
        scraper = IndeedScraper(
            query=args.query, location=args.location, max_pages=args.pages
        )
    else:
        raise ValueError(f"Unknown source: {args.source}")

    logger.info(f"Scraping '{args.query}' in '{args.location}' from {args.source} ({args.pages} pages)")
    results = scraper.run()
    logger.info(f"Scraped {len(results)} raw job listings")
    return results


def stage_etl(raw_data: list[dict] = None, raw_file: str = None) -> pd.DataFrame:
    from etl.cleaner import JobCleaner
    from etl.loader import PostgresLoader

    if raw_data:
        df = pd.DataFrame(raw_data)
    elif raw_file:
        with open(raw_file) as f:
            payload = json.load(f)
        df = pd.DataFrame(payload.get("jobs", []))
    else:
        # Load all JSON files from data/raw/
        from config.settings import RAW_DIR
        files = sorted(RAW_DIR.glob("*.json"))
        if not files:
            logger.error("No raw data found. Run --stage scrape first.")
            sys.exit(1)
        dfs = []
        for f in files:
            with open(f) as fh:
                payload = json.load(fh)
            dfs.append(pd.DataFrame(payload.get("jobs", [])))
        df = pd.concat(dfs, ignore_index=True)

    logger.info(f"Running ETL on {len(df)} records")
    cleaned = JobCleaner(df).run()

    # Save cleaned CSV
    from config.settings import PROCESSED_DIR
    csv_path = PROCESSED_DIR / f"jobs_cleaned_{datetime.now().strftime('%Y%m%d')}.csv"
    cleaned.to_csv(csv_path, index=False, encoding="utf-8-sig")
    logger.info(f"Cleaned data saved → {csv_path}")

    # Load into PostgreSQL
    loader = PostgresLoader()
    stats = loader.load(cleaned)
    logger.info(f"DB load: {stats}")

    return cleaned


def stage_analyze():
    from analysis.skills_analysis import SkillsAnalyzer
    from analysis.salary_analysis import SalaryAnalyzer
    from dashboard.powerbi_export import PowerBIExporter

    SkillsAnalyzer().run_all()
    SalaryAnalyzer().run_all()
    PowerBIExporter().export_all()
    logger.info("Analysis complete. Open data/processed/ for CSVs and charts.")


# ── CLI ────────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Job Market Analyzer — full data pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--source",   default="linkedin", choices=["linkedin", "indeed"])
    parser.add_argument("--query",    default="Data Analyst",  help="Job title to search")
    parser.add_argument("--location", default="India",          help="City / region")
    parser.add_argument("--pages",    default=3, type=int,      help="Result pages to scrape")
    parser.add_argument(
        "--stage",
        default="all",
        choices=["all", "scrape", "etl", "analyze"],
        help="Pipeline stage to run",
    )
    parser.add_argument("--raw-file", default="",               help="Path to a raw JSON file (ETL stage only)")
    return parser.parse_args()


def main():
    args = parse_args()
    logger.info(f"=== Job Market Analyzer | stage={args.stage} ===")

    if args.stage == "scrape":
        stage_scrape(args)

    elif args.stage == "etl":
        stage_etl(raw_file=args.raw_file or None)

    elif args.stage == "analyze":
        stage_analyze()

    elif args.stage == "all":
        raw = stage_scrape(args)
        cleaned = stage_etl(raw_data=raw)
        stage_analyze()

    logger.info("=== Pipeline finished ===")


if __name__ == "__main__":
    main()
