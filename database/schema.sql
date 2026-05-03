-- database/schema.sql
-- Job Market Analyzer — PostgreSQL schema
-- Run: psql -U postgres -d job_market -f database/schema.sql

-- ─────────────────────────────────────────────────────────────
-- Extension
-- ─────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- for fuzzy text search

-- ─────────────────────────────────────────────────────────────
-- Core jobs table
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS jobs (
    id                  SERIAL PRIMARY KEY,
    job_id              VARCHAR(20)  NOT NULL UNIQUE,  -- MD5 hash key
    source              VARCHAR(20)  NOT NULL,          -- linkedin / indeed
    title               VARCHAR(300) NOT NULL,
    title_normalized    VARCHAR(300),
    company             VARCHAR(200),
    location            VARCHAR(200),
    city                VARCHAR(100),
    date_posted         DATE,
    job_url             TEXT,
    salary_raw          VARCHAR(200),
    salary_min          NUMERIC(15, 2),
    salary_max          NUMERIC(15, 2),
    salary_currency     VARCHAR(10),
    salary_period       VARCHAR(20),                   -- annual / monthly / hourly
    experience_level    VARCHAR(50),
    description         TEXT,
    search_query        VARCHAR(200),
    search_location     VARCHAR(200),
    scraped_at          TIMESTAMPTZ DEFAULT NOW(),
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────
-- Skills (normalized taxonomy)
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS skills (
    id          SERIAL PRIMARY KEY,
    skill_name  VARCHAR(100) NOT NULL UNIQUE,
    category    VARCHAR(50),   -- language / framework / tool / cloud / soft
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────
-- Job ↔ Skill (many-to-many)
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS job_skills (
    job_id      VARCHAR(20)  NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    skill_name  VARCHAR(100) NOT NULL REFERENCES skills(skill_name) ON DELETE CASCADE,
    PRIMARY KEY (job_id, skill_name)
);

-- ─────────────────────────────────────────────────────────────
-- Scrape run audit log
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS scrape_runs (
    id              SERIAL PRIMARY KEY,
    run_id          VARCHAR(30) NOT NULL UNIQUE,
    source          VARCHAR(20),
    query           VARCHAR(200),
    location        VARCHAR(200),
    total_scraped   INT DEFAULT 0,
    inserted        INT DEFAULT 0,
    skipped         INT DEFAULT 0,
    ran_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────
-- Indexes
-- ─────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_jobs_source         ON jobs(source);
CREATE INDEX IF NOT EXISTS idx_jobs_city           ON jobs(city);
CREATE INDEX IF NOT EXISTS idx_jobs_title_norm     ON jobs(title_normalized);
CREATE INDEX IF NOT EXISTS idx_jobs_experience     ON jobs(experience_level);
CREATE INDEX IF NOT EXISTS idx_jobs_scraped_at     ON jobs(scraped_at);
CREATE INDEX IF NOT EXISTS idx_jobs_salary_min     ON jobs(salary_min);
CREATE INDEX IF NOT EXISTS idx_job_skills_skill    ON job_skills(skill_name);
CREATE INDEX IF NOT EXISTS idx_jobs_title_trgm     ON jobs USING gin(title gin_trgm_ops);

-- ─────────────────────────────────────────────────────────────
-- Useful views (used by analysis & Power BI)
-- ─────────────────────────────────────────────────────────────

CREATE OR REPLACE VIEW v_skill_demand AS
SELECT
    js.skill_name,
    COUNT(DISTINCT js.job_id)                          AS job_count,
    ROUND(COUNT(DISTINCT js.job_id) * 100.0 /
        NULLIF((SELECT COUNT(*) FROM jobs), 0), 2)    AS pct_of_jobs
FROM job_skills js
GROUP BY js.skill_name
ORDER BY job_count DESC;


CREATE OR REPLACE VIEW v_salary_by_role AS
SELECT
    title_normalized                            AS role,
    experience_level,
    city,
    COUNT(*)                                    AS job_count,
    ROUND(AVG(salary_min), 0)                  AS avg_salary_min,
    ROUND(AVG(salary_max), 0)                  AS avg_salary_max,
    ROUND(PERCENTILE_CONT(0.5)
        WITHIN GROUP (ORDER BY salary_min), 0) AS median_salary,
    salary_currency
FROM jobs
WHERE salary_min IS NOT NULL
GROUP BY title_normalized, experience_level, city, salary_currency
ORDER BY median_salary DESC NULLS LAST;


CREATE OR REPLACE VIEW v_jobs_over_time AS
SELECT
    DATE_TRUNC('week', scraped_at)::DATE        AS week,
    source,
    search_query                                AS role,
    COUNT(*)                                    AS jobs_posted
FROM jobs
GROUP BY 1, 2, 3
ORDER BY 1;


CREATE OR REPLACE VIEW v_location_heatmap AS
SELECT
    city,
    COUNT(*)                            AS job_count,
    ROUND(AVG(salary_min), 0)          AS avg_salary
FROM jobs
WHERE city IS NOT NULL AND city != ''
GROUP BY city
ORDER BY job_count DESC;


CREATE OR REPLACE VIEW v_top_companies AS
SELECT
    company,
    COUNT(*)                            AS open_roles,
    ARRAY_AGG(DISTINCT city)           AS cities,
    ROUND(AVG(salary_min), 0)          AS avg_min_salary
FROM jobs
WHERE company IS NOT NULL AND company != ''
GROUP BY company
ORDER BY open_roles DESC;
