"""
analysis/salary_analysis.py
Salary analysis:
  - Salary bands by role (box plots)
  - Salary vs experience level
  - Salary by city heatmap
"""

import logging

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns

from database.queries import salary_by_role, salary_distribution
from config.settings import PROCESSED_DIR

logger = logging.getLogger(__name__)
CHARTS_DIR = PROCESSED_DIR / "charts"
CHARTS_DIR.mkdir(parents=True, exist_ok=True)

PALETTE = {
    "primary": "#2563EB",
    "secondary": "#7C3AED",
    "accent": "#059669",
    "bg": "#F8FAFC",
    "text": "#1E293B",
    "grid": "#E2E8F0",
    "warn": "#F59E0B",
}

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.facecolor": PALETTE["bg"],
    "figure.facecolor": "white",
    "grid.color": PALETTE["grid"],
    "grid.linewidth": 0.8,
    "text.color": PALETTE["text"],
})


def _inr_fmt(val, pos=None):
    if val >= 1_00_000:
        return f"₹{val/1_00_000:.0f}L"
    return f"₹{int(val):,}"


class SalaryAnalyzer:

    def run_all(self):
        logger.info("Running salary analysis...")
        self.plot_salary_by_role()
        self.plot_salary_by_experience()
        self.plot_salary_by_city()

    # ── Chart 1: Salary bands by role ─────────────────────────────────────────

    def plot_salary_by_role(self, top_n: int = 12):
        df = salary_by_role()
        if df.empty:
            logger.warning("No salary data — run the pipeline first")
            return

        # Keep most common roles
        top_roles = (
            df.groupby("role")["job_count"].sum()
            .nlargest(top_n).index.tolist()
        )
        df = df[df["role"].isin(top_roles)].copy()
        df["role_label"] = df["role"].str.title().str[:30]
        df_sorted = df.groupby("role_label")["median_salary"].median().sort_values()

        fig, ax = plt.subplots(figsize=(12, 7))

        # Plot range bars + median marker
        for i, role in enumerate(df_sorted.index):
            role_df = df[df["role_label"] == role]
            sal_min = role_df["avg_salary_min"].mean()
            sal_max = role_df["avg_salary_max"].mean()
            median = role_df["median_salary"].median()

            ax.barh(i, sal_max - sal_min, left=sal_min, height=0.5,
                    color=PALETTE["primary"], alpha=0.4)
            ax.plot(median, i, "D", color=PALETTE["primary"], markersize=7, zorder=5)
            ax.text(
                sal_max + 5000, i, _inr_fmt(median),
                va="center", ha="left", fontsize=8.5, color=PALETTE["text"]
            )

        ax.set_yticks(range(len(df_sorted)))
        ax.set_yticklabels(df_sorted.index, fontsize=10)
        ax.xaxis.set_major_formatter(mticker.FuncFormatter(_inr_fmt))
        ax.set_xlabel("Annual Salary (INR)", fontsize=11)
        ax.set_title("Salary Bands by Role\n(bar = min–max range, diamond = median)",
                     fontsize=13, fontweight="bold", pad=12)
        ax.grid(axis="x", linestyle="--", alpha=0.5)

        fig.tight_layout()
        out = CHARTS_DIR / "salary_by_role.png"
        fig.savefig(out, dpi=150, bbox_inches="tight")
        plt.close(fig)
        logger.info(f"Saved → {out}")
        return out

    # ── Chart 2: Salary by experience ─────────────────────────────────────────

    def plot_salary_by_experience(self):
        df = salary_distribution()
        if df.empty:
            return

        exp_order = [
            "Entry Level", "Junior (1–3 yrs)", "Mid Level (3–6 yrs)",
            "Senior (6+ yrs)", "Management", "Not specified"
        ]
        df = df[df["experience_level"].isin(exp_order)].copy()

        fig, ax = plt.subplots(figsize=(11, 6))
        sns.boxplot(
            data=df,
            x="experience_level",
            y="salary_min",
            order=[e for e in exp_order if e in df["experience_level"].values],
            palette=["#BFDBFE", "#93C5FD", "#60A5FA", "#2563EB", "#1D4ED8", "#CCCCCC"],
            flierprops={"marker": "o", "markersize": 3, "alpha": 0.4},
            ax=ax,
            width=0.55,
        )
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(_inr_fmt))
        ax.set_xlabel("Experience Level", fontsize=11)
        ax.set_ylabel("Annual Salary (INR)", fontsize=11)
        ax.set_title("Salary Distribution by Experience Level",
                     fontsize=13, fontweight="bold", pad=12)
        ax.tick_params(axis="x", rotation=20)
        ax.grid(axis="y", linestyle="--", alpha=0.5)
        fig.tight_layout()

        out = CHARTS_DIR / "salary_by_experience.png"
        fig.savefig(out, dpi=150, bbox_inches="tight")
        plt.close(fig)
        logger.info(f"Saved → {out}")
        return out

    # ── Chart 3: Average salary by city ───────────────────────────────────────

    def plot_salary_by_city(self, top_n: int = 10):
        df = salary_distribution()
        if df.empty or "city" not in df.columns:
            return

        city_df = (
            df[df["city"].notna() & (df["city"] != "")]
            .groupby("city")
            .agg(avg_salary=("salary_min", "mean"), job_count=("salary_min", "count"))
            .query("job_count >= 3")
            .nlargest(top_n, "avg_salary")
            .reset_index()
        )

        if city_df.empty:
            return

        fig, ax = plt.subplots(figsize=(10, 5))
        colors = [PALETTE["primary"] if i < 3 else PALETTE["secondary"]
                  if i < 6 else "#94A3B8" for i in range(len(city_df))]
        bars = ax.bar(city_df["city"], city_df["avg_salary"],
                      color=colors, width=0.6)

        for bar, val in zip(bars, city_df["avg_salary"]):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 5000,
                _inr_fmt(val),
                ha="center", va="bottom", fontsize=9, fontweight="500"
            )

        ax.yaxis.set_major_formatter(mticker.FuncFormatter(_inr_fmt))
        ax.set_xlabel("City", fontsize=11)
        ax.set_ylabel("Average Salary (INR)", fontsize=11)
        ax.set_title(f"Average Salary by City (Top {top_n})",
                     fontsize=13, fontweight="bold", pad=12)
        ax.tick_params(axis="x", rotation=30)
        ax.grid(axis="y", linestyle="--", alpha=0.5)
        fig.tight_layout()

        out = CHARTS_DIR / "salary_by_city.png"
        fig.savefig(out, dpi=150, bbox_inches="tight")
        plt.close(fig)
        logger.info(f"Saved → {out}")
        return out
