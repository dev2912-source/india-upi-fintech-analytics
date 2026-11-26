"""Generate publication-quality PNG charts in assets/ for README and executive presentation."""

import logging
import sqlite3
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
import seaborn as sns

from src.config import ASSETS_DIR, DB_PATH, PROCESSED_DIR

logger = logging.getLogger(__name__)
sns.set_theme(style="whitegrid", context="talk")


def generate_all_charts(
    out_dir: Path = PROCESSED_DIR,
    assets_dir: Path = ASSETS_DIR,
    db_path: Path = DB_PATH,
) -> None:
    """Create 4 high-resolution analytical charts saved to assets/."""
    assets_dir.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        nat = pd.read_sql_query("SELECT * FROM fact_national_transactions ORDER BY year, quarter", conn)
        top_states = pd.read_sql_query(
            """
            SELECT state, ROUND(SUM(tx_amount_cr), 2) AS tpv_cr
            FROM fact_state_transactions
            WHERE year = (SELECT MAX(year) FROM fact_state_transactions WHERE quarter = 4)
            GROUP BY state
            ORDER BY tpv_cr DESC
            LIMIT 10
            """,
            conn,
        )
        clusters = pd.read_sql_query("SELECT * FROM dim_district_clusters", conn)
        fc = pd.read_sql_query("SELECT * FROM fact_national_forecast", conn)

    # 1. National UPI TPV & Ticket Size Trend
    fig, ax1 = plt.subplots(figsize=(12, 5.5))
    x = range(len(nat))
    ax1.fill_between(x, nat["tx_amount_cr"] / 1e5, color="#1E3A8A", alpha=0.15)
    ax1.plot(x, nat["tx_amount_cr"] / 1e5, color="#1E3A8A", linewidth=2.8, marker="o", markersize=4, label="TPV (₹ Lakh Cr)")
    ax1.set_ylabel("Total Payment Value (₹ Lakh Crore)", color="#1E3A8A", fontweight="bold")
    ax1.set_xticks(x[::3])
    ax1.set_xticklabels(nat["year_quarter"].iloc[::3], rotation=45, ha="right", fontsize=10)
    ax1.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.1f"))

    ax2 = ax1.twinx()
    ax2.plot(x, nat["avg_ticket_size"], color="#F59E0B", linewidth=2.2, linestyle="--", label="Avg Ticket Size (₹)")
    ax2.set_ylabel("Avg Ticket Size (₹)", color="#D97706", fontweight="bold")
    ax2.grid(False)

    plt.title("India UPI Growth: Quarterly TPV vs. Average Ticket Size (2018–2026)", fontweight="bold", pad=15)
    fig.tight_layout()
    fig.savefig(assets_dir / "01_national_upi_growth.png", dpi=180)
    plt.close(fig)

    # 2. Top 10 States by TPV (Latest Full Year)
    fig, ax = plt.subplots(figsize=(11, 5.5))
    top_sorted = top_states.sort_values("tpv_cr", ascending=True)
    bars = ax.barh(top_sorted["state"], top_sorted["tpv_cr"] / 1e5, color="#0284C7")
    ax.set_xlabel("Total Payment Value (₹ Lakh Crore)", fontweight="bold")
    ax.set_title("Top 10 Indian States by UPI Payment Value (Latest Full Year)", fontweight="bold", pad=12)
    for bar in bars:
        w = bar.get_width()
        ax.text(w + 0.3, bar.get_y() + bar.get_height() / 2, f"₹{w:.2f}L Cr", va="center", fontsize=10)
    ax.set_xlim(0, top_sorted["tpv_cr"].max() / 1e5 * 1.18)
    fig.tight_layout()
    fig.savefig(assets_dir / "02_top_states_tpv.png", dpi=180)
    plt.close(fig)

    # 3. District Digital Maturity Clusters
    fig, ax = plt.subplots(figsize=(11, 6))
    palette = {
        "Metro & Tier-1 Powerhouses": "#1E3A8A",
        "Hyper-Growth Tier-2/3 Hubs": "#10B981",
        "Mature Steady Markets": "#0284C7",
        "Emerging Expansion Targets": "#F59E0B",
    }
    sns.scatterplot(
        data=clusters,
        x="tx_per_user",
        y="ttm_tpv_cr",
        hue="segment",
        palette=palette,
        alpha=0.75,
        s=55,
        ax=ax,
    )
    ax.set_yscale("log")
    ax.set_xlabel("Transactions per Registered User (TTM)", fontweight="bold")
    ax.set_ylabel("Trailing 12M Payment Value (₹ Crore, Log Scale)", fontweight="bold")
    ax.set_title("Indian District Digital Maturity Segments (K-Means, k=4)", fontweight="bold", pad=12)
    ax.legend(title="District Persona", frameon=True)
    fig.tight_layout()
    fig.savefig(assets_dir / "03_district_clusters.png", dpi=180)
    plt.close(fig)

    # 4. National TPV 4-Quarter Forecast
    fig, ax = plt.subplots(figsize=(12, 5.5))
    hist = fc[fc["record_type"] == "Historical"]
    pred = fc[fc["record_type"] == "Forecast"]
    x_all = range(len(fc))
    x_hist = range(len(hist))
    x_pred = range(len(hist) - 1, len(fc))

    ax.plot(x_hist, hist["actual_tpv_cr"] / 1e5, color="#1E3A8A", linewidth=2.5, label="Historical TPV")
    pred_y = pd.concat([hist["actual_tpv_cr"].iloc[-1:], pred["forecast_tpv_cr"]]) / 1e5
    ax.plot(x_pred, pred_y, color="#F59E0B", linewidth=2.8, linestyle="--", marker="o", label=f"Forecast ({pred['model_used'].iloc[0]})")
    ax.fill_between(
        range(len(hist), len(fc)),
        pred["lower_ci_cr"] / 1e5,
        pred["upper_ci_cr"] / 1e5,
        color="#FDE68A",
        alpha=0.5,
        label="95% Confidence Interval",
    )
    ax.set_xticks(list(x_all)[::3])
    ax.set_xticklabels(fc["year_quarter"].iloc[::3], rotation=45, ha="right", fontsize=10)
    ax.set_ylabel("Total Payment Value (₹ Lakh Crore)", fontweight="bold")
    ax.set_title("India UPI TPV: Historical & 4-Quarter Forecast", fontweight="bold", pad=12)
    ax.legend(frameon=True)
    fig.tight_layout()
    fig.savefig(assets_dir / "04_tpv_forecast.png", dpi=180)
    plt.close(fig)

    logger.info("Generated 4 high-resolution charts in %s", assets_dir)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    generate_all_charts()
