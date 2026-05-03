# 🧑‍💼 Job Market Analyzer

A full end-to-end data engineering project that scrapes job listings from LinkedIn/Indeed using Selenium, cleans and transforms data with pandas, stores it in PostgreSQL, and visualizes insights in Power BI / Tableau.

---

## 📁 Project Structure

```
job_market_analyzer/
├── config/
│   ├── settings.py          # Central config (DB creds, scraper settings)
│   └── logging_config.py    # Logging setup
├── scraper/
│   ├── base_scraper.py      # Abstract base class for all scrapers
│   ├── linkedin_scraper.py  # LinkedIn job scraper (Selenium)
│   ├── indeed_scraper.py    # Indeed job scraper (Selenium)
│   └── utils.py             # Anti-bot helpers, random delays, UA rotation
├── etl/
│   ├── cleaner.py           # Data cleaning (salary parsing, skill extraction)
│   ├── transformer.py       # Feature engineering, normalization
│   └── loader.py            # PostgreSQL bulk loader
├── database/
│   ├── models.py            # SQLAlchemy ORM models
│   ├── schema.sql           # Raw SQL schema (alternative to ORM)
│   └── queries.py           # Reusable analytical queries
├── analysis/
│   ├── skills_analysis.py   # Top skills, co-occurrence matrix
│   ├── salary_analysis.py   # Salary band analysis by role/location
│   └── trend_analysis.py    # Time-based trend tracking
├── dashboard/
│   ├── powerbi_export.py    # Export clean CSVs for Power BI
│   └── job_market.pbix      # Power BI dashboard template (see docs)
├── tests/
│   ├── test_scraper.py
│   ├── test_cleaner.py
│   └── test_loader.py
├── data/
│   ├── raw/                 # Raw scraped JSON files
│   └── processed/           # Cleaned CSVs ready for Power BI
├── docs/
│   └── powerbi_setup.md     # Power BI connection guide
├── main.py                  # Pipeline entry point
├── requirements.txt
├── .env.example
└── README.md
```

---

## ⚙️ Setup

### 1. Clone & install dependencies

```bash
git clone https://github.com/yourusername/job_market_analyzer.git
cd job_market_analyzer
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Set up environment variables

```bash
cp .env.example .env
# Edit .env with your DB credentials and scraper settings
```

### 3. Set up PostgreSQL

```bash
# Create the database
psql -U postgres -c "CREATE DATABASE job_market;"

# Run schema
psql -U postgres -d job_market -f database/schema.sql
```

### 4. Install ChromeDriver

```bash
# ChromeDriver must match your installed Chrome version
# Auto-install via webdriver-manager (already in requirements.txt)
# It's handled automatically in the scraper code
```

---

## 🚀 Running the Pipeline

### Full pipeline (scrape → clean → load → export)

```bash
python main.py --source linkedin --query "Data Analyst" --location "Hyderabad" --pages 5
```

### Individual stages

```bash
# Scrape only
python main.py --stage scrape --source indeed --query "Python Developer"

# ETL only (on existing raw data)
python main.py --stage etl

# Analysis + export for Power BI
python main.py --stage analyze
```

### Options

| Flag | Description | Default |
|------|-------------|---------|
| `--source` | `linkedin` or `indeed` | `linkedin` |
| `--query` | Job title to search | `Data Analyst` |
| `--location` | City or remote | `India` |
| `--pages` | Number of result pages | `3` |
| `--stage` | `all`, `scrape`, `etl`, `analyze` | `all` |
| `--headless` | Run browser headlessly | `True` |

---

## 🗄️ Database Schema

```
jobs              — core job listings
skills            — normalized skill tags
job_skills        — many-to-many join table
companies         — company metadata
salary_bands      — parsed & normalized salary ranges
scrape_runs       — audit log of each scrape run
```

---

## 📊 Power BI Dashboard

After running `python main.py --stage analyze`, connect Power BI Desktop to:

- `data/processed/jobs_clean.csv`
- `data/processed/skills_frequency.csv`
- `data/processed/salary_bands.csv`
- `data/processed/location_heatmap.csv`

Or connect directly to PostgreSQL:
- Host: `localhost`
- Database: `job_market`
- See `docs/powerbi_setup.md` for full instructions.

### Dashboard Pages
1. **Overview** — total jobs, top roles, hiring companies
2. **Skills Demand** — bar chart of top 20 skills, co-occurrence heatmap
3. **Salary Analysis** — salary bands by role, location, experience
4. **Location Map** — jobs by city/region
5. **Trends** — weekly job posting trends by category

---

## 🧪 Running Tests

```bash
pytest tests/ -v
```

---

## ⚠️ Legal & Ethical Notes

- This scraper uses **random delays** and **user-agent rotation** to be respectful.
- Always review a site's `robots.txt` and Terms of Service before scraping.
- LinkedIn officially prohibits scraping — use this for **educational purposes only**.
- For production use, consider official APIs (LinkedIn API, Indeed Publisher API).

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Scraping | Python, Selenium 4, webdriver-manager |
| Data Processing | pandas, NumPy, re (regex) |
| Storage | PostgreSQL 15, SQLAlchemy, psycopg2 |
| Analysis | pandas, matplotlib, seaborn |
| Visualization | Power BI Desktop / Tableau Public |
| Testing | pytest |
| Config | python-dotenv |

---

## 📈 Sample Insights You Can Generate

- "Python is required in 73% of Data Analyst jobs in Bangalore"
- "Median salary for ML Engineer roles: ₹18–24 LPA"
- "SQL + Excel is the most common skill combo for entry-level analysts"
- "Remote Data roles grew 40% between Jan–Mar"
