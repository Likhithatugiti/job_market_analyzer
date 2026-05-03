"""
analysis/skills_analysis.py
Skills demand analysis:
  - Top N skills bar chart
  - Skill co-occurrence heatmap
  - Skills by role comparison
  - Saves PNGs to data/processed/charts/
"""

import logging
from pathlib import Path

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns

from database.queries import top_skills, skill_cooccurrence, skills_by_role
from config.settings import PROCESSED_DIR

logger = logging.getLogger(__name__)
CHARTS_DIR = PROCESSED_DIR / "charts"
CHARTS_DIR.mkdir(parents=True, exist_ok=True)

# ── Style ──────────────────────────────────────────────────────────────────────
PALETTE = {
    "primary": "#2563EB",
    "secondary": "#7C3AED",
    "accent": "#059669",
    "bg": "#F8FAFC",
    "text": "#1E293B",
    "grid": "#E2E8F0",
}

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.facecolor": PALETTE["bg"],
    "figure.facecolor": "white",
    "axes.edgecolor": PALETTE["grid"],
    "axes.labelcolor": PALETTE["text"],
    "xtick.color": PALETTE["text"],
    "ytick.color": PALETTE["text"],
    "text.color": PALETTE["text"],
    "grid.color": PALETTE["grid"],
    "grid.linewidth": 0.8,
})


class SkillsAnalyzer:

    def run_all(self):
        logger.info("Running skills analysis...")
        self.plot_top_skills()
        self.plot_skill_cooccurrence()
        logger.info(f"Charts saved to {CHARTS_DIR}")

    # ── Chart 1: Top N skills horizontal bar ──────────────────────────────────

    def plot_top_skills(self, top_n: int = 25, role: str = ""):
        if role:
            df = skills_by_role(role).head(top_n)
            df = df.rename(columns={"freq": "job_count"})
            title = f"Top {top_n} Skills — {role.title()} Roles"
            filename = f"top_skills_{role.replace(' ', '_')}.png"
        else:
            df = top_skills(top_n)
            title = f"Top {top_n} Most In-Demand Skills"
            filename = "top_skills_overall.png"

        if df.empty:
            logger.warning("No skill data available")
            return

        # Color gradient from high to low
        colors = [
            PALETTE["primary"] if i < 5
            else PALETTE["secondary"] if i < 15
            else "#94A3B8"
            for i in range(len(df))
        ]

        fig, ax = plt.subplots(figsize=(11, 8))
        df_sorted = df.sort_values("job_count", ascending=True)
        bars = ax.barh(df_sorted["skill_name"], df_sorted["job_count"],
                       color=colors[::-1], height=0.65)

        # Value labels
        for bar, val in zip(bars, df_sorted["job_count"]):
            ax.text(
                bar.get_width() + 0.3, bar.get_y() + bar.get_height() / 2,
                str(int(val)), va="center", ha="left", fontsize=9, color=PALETTE["text"]
            )

        # Percentage column if available
        if "pct_of_jobs" in df.columns:
            for bar, pct in zip(bars, df_sorted.get("pct_of_jobs", [0]*len(df))):
                ax.text(
                    bar.get_width() * 0.5, bar.get_y() + bar.get_height() / 2,
                    f"{pct:.0f}%", va="center", ha="center",
                    fontsize=8, color="white", fontweight="bold"
                )

        ax.set_xlabel("Number of Job Listings", fontsize=11)
        ax.set_title(title, fontsize=14, fontweight="bold", pad=15)
        ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))
        ax.grid(axis="x", linestyle="--", alpha=0.5)

        fig.tight_layout()
        out = CHARTS_DIR / filename
        fig.savefig(out, dpi=150, bbox_inches="tight")
        plt.close(fig)
        logger.info(f"Saved → {out}")
        return out

    # ── Chart 2: Co-occurrence heatmap ────────────────────────────────────────

    def plot_skill_cooccurrence(self, top_n: int = 15):
        df = skill_cooccurrence(top_n)
        if df.empty:
            logger.warning("No co-occurrence data")
            return

        # Pivot to matrix
        skills = sorted(set(df["skill_a"]) | set(df["skill_b"]))
        matrix = pd.DataFrame(0, index=skills, columns=skills)
        for _, row in df.iterrows():
            matrix.loc[row["skill_a"], row["skill_b"]] = row["co_count"]
            matrix.loc[row["skill_b"], row["skill_a"]] = row["co_count"]

        fig, ax = plt.subplots(figsize=(12, 10))
        mask = np.triu(np.ones_like(matrix, dtype=bool))

        sns.heatmap(
            matrix,
            mask=mask,
            ax=ax,
            cmap=sns.color_palette("Blues", as_cmap=True),
            linewidths=0.5,
            linecolor=PALETTE["grid"],
            annot=True,
            fmt="d",
            annot_kws={"size": 8},
            cbar_kws={"label": "Co-occurrence count", "shrink": 0.7},
        )
        ax.set_title(
            f"Skill Co-occurrence Matrix (Top {top_n} skills)",
            fontsize=14, fontweight="bold", pad=15
        )
        ax.tick_params(axis="x", rotation=45, labelsize=9)
        ax.tick_params(axis="y", rotation=0, labelsize=9)

        fig.tight_layout()
        out = CHARTS_DIR / "skill_cooccurrence.png"
        fig.savefig(out, dpi=150, bbox_inches="tight")
        plt.close(fig)
        logger.info(f"Saved → {out}")
        return out

    # ── Chart 3: Skills by role (grouped bar) ─────────────────────────────────

    def plot_skills_by_roles(self, roles: list[str] = None):
        roles = roles or [
            "data analyst", "data engineer", "machine learning",
            "data scientist", "business analyst"
        ]
        dfs = []
        for role in roles:
            df = skills_by_role(role).head(10)
            df["role"] = role.title()
            dfs.append(df)

        if not dfs:
            return

        combined = pd.concat(dfs, ignore_index=True)

        # Pivot: skills as rows, roles as columns
        pivot = combined.pivot_table(
            index="skill_name", columns="role", values="freq", fill_value=0
        )
        # Keep only skills that appear in at least 2 roles
        pivot = pivot[(pivot > 0).sum(axis=1) >= 2].nlargest(15, pivot.columns[0])

        fig, ax = plt.subplots(figsize=(14, 8))
        pivot.plot(kind="bar", ax=ax, width=0.75,
                   color=[PALETTE["primary"], PALETTE["secondary"],
                          PALETTE["accent"], "#F59E0B", "#EF4444"])
        ax.set_title("Top Skills by Role", fontsize=14, fontweight="bold", pad=15)
        ax.set_xlabel("Skill", fontsize=11)
        ax.set_ylabel("Number of Listings", fontsize=11)
        ax.legend(title="Role", bbox_to_anchor=(1.01, 1), loc="upper left", fontsize=9)
        ax.tick_params(axis="x", rotation=45)
        ax.grid(axis="y", linestyle="--", alpha=0.5)
        fig.tight_layout()

        out = CHARTS_DIR / "skills_by_role.png"
        fig.savefig(out, dpi=150, bbox_inches="tight")
        plt.close(fig)
        logger.info(f"Saved → {out}")
        return out
