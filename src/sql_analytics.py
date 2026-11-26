"""SQL analytics layer querying the SQLite FinTech warehouse."""

import sqlite3
from pathlib import Path

import pandas as pd

from src.config import DB_PATH


def query_sql(sql: str, db_path: Path = DB_PATH) -> pd.DataFrame:
    """Execute a read-only SQL query against the SQLite warehouse."""
    with sqlite3.connect(db_path) as conn:
        return pd.read_sql_query(sql, conn)


def get_national_yoy_growth(db_path: Path = DB_PATH) -> pd.DataFrame:
    """Compute quarterly national TPV, transaction count, and YoY growth using SQL window functions."""
    sql = """
    WITH base AS (
        SELECT
            n.year,
            n.quarter,
            n.year_quarter,
            d.quarter_start_date,
            n.tx_count,
            n.tx_amount_cr,
            n.avg_ticket_size,
            LAG(n.tx_amount_cr, 4) OVER (ORDER BY n.year, n.quarter) AS prev_year_tpv_cr,
            LAG(n.tx_count, 4) OVER (ORDER BY n.year, n.quarter) AS prev_year_tx_count
        FROM fact_national_transactions n
        JOIN dim_date d ON n.year_quarter = d.year_quarter
    )
    SELECT
        year,
        quarter,
        year_quarter,
        quarter_start_date,
        tx_count,
        tx_amount_cr,
        avg_ticket_size,
        ROUND((tx_amount_cr - prev_year_tpv_cr) * 100.0 / NULLIF(prev_year_tpv_cr, 0), 2) AS yoy_tpv_growth_pct,
        ROUND((tx_count - prev_year_tx_count) * 100.0 / NULLIF(prev_year_tx_count, 0), 2) AS yoy_tx_growth_pct
    FROM base
    ORDER BY year, quarter;
    """
    return query_sql(sql, db_path)


def get_top_states_latest_year(db_path: Path = DB_PATH, top_n: int = 10) -> pd.DataFrame:
    """Rank top states by Total Payment Value in the most recent complete year."""
    sql = f"""
    WITH latest_full_year AS (
        SELECT MAX(year) AS max_year
        FROM (
            SELECT year, COUNT(DISTINCT quarter) AS q_cnt
            FROM fact_state_transactions
            GROUP BY year
            HAVING q_cnt = 4
        )
    )
    SELECT
        s.state,
        s.year,
        ROUND(SUM(s.tx_amount_cr), 2) AS total_tpv_cr,
        SUM(s.tx_count) AS total_tx_count,
        ROUND(SUM(s.tx_amount) * 1.0 / SUM(s.tx_count), 2) AS avg_ticket_size,
        ROUND(SUM(s.tx_amount_cr) * 100.0 / SUM(SUM(s.tx_amount_cr)) OVER (), 2) AS national_tpv_share_pct
    FROM fact_state_transactions s
    JOIN latest_full_year l ON s.year = l.max_year
    GROUP BY s.state, s.year
    ORDER BY total_tpv_cr DESC
    LIMIT {int(top_n)};
    """
    return query_sql(sql, db_path)


def get_category_mix_shift(db_path: Path = DB_PATH) -> pd.DataFrame:
    """Analyze transaction share shift across categories (P2P, Retail/Merchant, Utility) by year."""
    sql = """
    SELECT
        year,
        category,
        SUM(tx_count) AS total_tx_count,
        ROUND(SUM(tx_count) * 100.0 / SUM(SUM(tx_count)) OVER (PARTITION BY year), 2) AS category_share_pct
    FROM fact_national_categories
    GROUP BY year, category
    ORDER BY year, total_tx_count DESC;
    """
    return query_sql(sql, db_path)
