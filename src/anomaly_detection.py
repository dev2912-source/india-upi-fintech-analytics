"""State-level payment surge and anomaly detection using QoQ Z-scores & Isolation Forest."""

import logging
import sqlite3
from pathlib import Path

import pandas as pd
from sklearn.ensemble import IsolationForest

from src.config import DB_PATH, PROCESSED_DIR

logger = logging.getLogger(__name__)


def run_anomaly_detection(out_dir: Path = PROCESSED_DIR, db_path: Path = DB_PATH) -> pd.DataFrame:
    """Detect abnormal quarterly payment surges/drops across Indian states."""
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query("SELECT * FROM fact_state_transactions", conn)

    df = df.sort_values(["state", "year", "quarter"]).reset_index(drop=True)
    df["qoq_tpv_growth_pct"] = (
        df.groupby("state")["tx_amount_cr"].pct_change() * 100
    ).round(2)
    df["qoq_tx_growth_pct"] = (
        df.groupby("state")["tx_count"].pct_change() * 100
    ).round(2)

    valid = df.dropna(subset=["qoq_tpv_growth_pct", "qoq_tx_growth_pct"]).copy()

    # Cross-sectional Z-score per quarter (flags states diverging sharply from national peer quarter)
    q_stats = valid.groupby("year_quarter")["qoq_tpv_growth_pct"].transform("mean")
    q_std = valid.groupby("year_quarter")["qoq_tpv_growth_pct"].transform("std").replace(0, 1)
    valid["peer_z_score"] = ((valid["qoq_tpv_growth_pct"] - q_stats) / q_std).round(2)

    iso = IsolationForest(contamination=0.04, random_state=42)
    features = valid[["qoq_tpv_growth_pct", "qoq_tx_growth_pct", "avg_ticket_size"]].fillna(0)
    valid["iso_flag"] = iso.fit_predict(features) == -1
    valid["is_anomaly"] = valid["iso_flag"] | (valid["peer_z_score"].abs() >= 2.5)
    valid["anomaly_type"] = valid.apply(
        lambda r: (
            "Abnormal Surge" if r["is_anomaly"] and r["peer_z_score"] > 0
            else ("Abnormal Drop" if r["is_anomaly"] else "Normal")
        ),
        axis=1,
    )

    alerts = (
        valid[valid["is_anomaly"]]
        .sort_values(["year", "quarter", "peer_z_score"], ascending=[False, False, False])
        .reset_index(drop=True)
    )

    alerts.to_csv(out_dir / "anomaly_alerts.csv", index=False)
    with sqlite3.connect(db_path) as conn:
        alerts.to_sql("fact_anomaly_alerts", conn, if_exists="replace", index=False)

    logger.info("Anomaly detection complete: %d state-quarter alerts flagged.", len(alerts))
    return alerts


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    run_anomaly_detection()
