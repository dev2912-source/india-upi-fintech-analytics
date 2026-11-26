"""Automated data-contract and model-output validation tests."""

import sqlite3
import pandas as pd

from src.config import DB_PATH, PROCESSED_DIR
from src.sql_analytics import get_national_yoy_growth, get_top_states_latest_year


def test_processed_files_exist():
    expected = [
        "dim_date.csv",
        "dim_geography.csv",
        "fact_national_transactions.csv",
        "fact_state_transactions.csv",
        "fact_district_transactions.csv",
        "district_clusters.csv",
        "forecast_benchmark.csv",
        "national_forecast.csv",
        "anomaly_alerts.csv",
    ]
    for fname in expected:
        assert (PROCESSED_DIR / fname).exists(), f"Missing processed file: {fname}"


def test_sqlite_warehouse_tables():
    assert DB_PATH.exists(), "SQLite warehouse missing"
    with sqlite3.connect(DB_PATH) as conn:
        tables = {
            r[0]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
    assert {"dim_date", "fact_national_transactions", "dim_district_clusters", "fact_national_forecast"} <= tables


def test_national_transactions_integrity():
    df = pd.read_csv(PROCESSED_DIR / "fact_national_transactions.csv")
    assert len(df) >= 30
    assert (df["tx_count"] > 0).all()
    assert (df["tx_amount_cr"] > 0).all()
    assert df["avg_ticket_size"].between(100, 10000).all()


def test_district_clusters_valid():
    df = pd.read_csv(PROCESSED_DIR / "district_clusters.csv")
    assert len(df) > 700
    assert df["segment"].nunique() == 4
    assert df["geo_key"].is_unique


def test_forecast_horizon_and_ci_bounds():
    fc = pd.read_csv(PROCESSED_DIR / "national_forecast.csv")
    future = fc[fc["record_type"] == "Forecast"]
    assert len(future) == 4
    assert (future["lower_ci_cr"] <= future["forecast_tpv_cr"]).all()
    assert (future["forecast_tpv_cr"] <= future["upper_ci_cr"]).all()

    bench = pd.read_csv(PROCESSED_DIR / "forecast_benchmark.csv")
    assert len(bench) == 5
    assert bench.iloc[0]["mape_pct"] < bench.iloc[-1]["mape_pct"]


def test_sql_analytics_queries():
    yoy = get_national_yoy_growth()
    assert len(yoy) >= 30
    assert "yoy_tpv_growth_pct" in yoy.columns
    top_states = get_top_states_latest_year(top_n=5)
    assert len(top_states) == 5
    assert top_states["national_tpv_share_pct"].sum() > 40
