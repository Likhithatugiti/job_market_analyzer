# Power BI Dashboard Setup Guide

## Option A — Connect via CSV files (easiest)

After running `python main.py --stage analyze`, all datasets are exported to `data/processed/`.

1. Open **Power BI Desktop**
2. Click **Get Data → Text/CSV**
3. Import each of these files:

| File | Used for |
|------|----------|
| `jobs_clean.csv` | Main jobs table (all visuals) |
| `skills_frequency.csv` | Skills demand bar chart |
| `skill_cooccurrence.csv` | Co-occurrence matrix |
| `salary_bands.csv` | Salary by role chart |
| `location_heatmap.csv` | Location map visual |
| `jobs_over_time.csv` | Trend line chart |
| `top_companies.csv` | Top hiring companies |
| `overview_kpis.csv` | KPI cards at the top |

---

## Option B — Live PostgreSQL Connection

1. Open Power BI Desktop
2. **Get Data → PostgreSQL database**
3. Enter:
   - Server: `localhost`
   - Database: `job_market`
4. Select these tables/views:
   - `jobs`
   - `job_skills`
   - `skills`
   - `v_skill_demand`
   - `v_salary_by_role`
   - `v_location_heatmap`
   - `v_jobs_over_time`
   - `v_top_companies`

> **Note**: Install the **Npgsql** PostgreSQL driver if prompted:
> https://www.npgsql.org/doc/installation.html

---

## Recommended Dashboard Layout

### Page 1 — Overview
- **KPI Cards** (top row): Total Jobs | Companies | Cities | Avg Salary
  - Source: `overview_kpis.csv`
- **Bar chart**: Jobs by Source (LinkedIn vs Indeed)
- **Donut chart**: Experience Level breakdown
- **Slicer**: Date range filter

### Page 2 — Skills Demand
- **Horizontal bar chart**: Top 25 skills by frequency
  - X-axis: `job_count`, Y-axis: `skill_name`
  - Source: `skills_frequency.csv`
- **Matrix/Table**: Skill co-occurrence heat table
  - Source: `skill_cooccurrence.csv`
- **Slicer**: Filter by role / city

### Page 3 — Salary Analysis
- **Bar chart with error bars**: Salary range by role
  - Min: `avg_salary_min`, Max: `avg_salary_max`, Tooltip: `median_salary`
  - Source: `salary_bands.csv`
- **Box plot (or grouped bar)**: Salary by experience level
- **Scatter plot**: salary_min vs skills_count

### Page 4 — Location Map
- **Map visual**: Bubble map of job count by city
  - Location: `city`, Size: `job_count`, Color: `avg_salary`
  - Source: `location_heatmap.csv`
- **Table**: Top cities with avg salary

### Page 5 — Trends
- **Line chart**: Jobs posted per week by role
  - X-axis: `week`, Y-axis: `jobs_posted`, Legend: `role`
  - Source: `jobs_over_time.csv`
- **Bar chart**: Top 10 hiring companies

---

## Useful DAX Measures

```dax
-- Total Jobs
Total Jobs = COUNTROWS(jobs_clean)

-- Avg Salary (where available)
Avg Salary = AVERAGE(jobs_clean[salary_min])

-- Salary Coverage %
Salary Coverage = 
    DIVIDE(
        COUNTROWS(FILTER(jobs_clean, NOT ISBLANK(jobs_clean[salary_min]))),
        COUNTROWS(jobs_clean)
    )

-- Top Skill
Top Skill = 
    FIRSTNONBLANK(
        TOPN(1, skills_frequency, skills_frequency[job_count], DESC),
        skills_frequency[skill_name]
    )

-- Jobs This Week
Jobs This Week = 
    CALCULATE(
        COUNTROWS(jobs_clean),
        DATESINPERIOD(jobs_clean[scraped_date], TODAY(), -7, DAY)
    )
```

---

## Scheduled Refresh

To keep the dashboard fresh, set up a Windows Task Scheduler job:

```bat
@echo off
cd /d C:\path\to\job_market_analyzer
call venv\Scripts\activate
python main.py --stage all --query "Data Analyst" --location "India" --pages 5
python main.py --stage all --query "Data Engineer" --location "India" --pages 5
python main.py --stage all --query "Machine Learning Engineer" --location "India" --pages 5
```

Schedule this to run daily/weekly, then enable **Scheduled Refresh** in Power BI Service.
