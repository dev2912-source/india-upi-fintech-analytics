"""District-level Digital Payments Maturity Clustering (K-Means vs. GMM)."""

import logging
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import davies_bouldin_score, silhouette_score
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler

from src.config import DB_PATH, PROCESSED_DIR

logger = logging.getLogger(__name__)


def build_district_features(db_path: Path = DB_PATH) -> pd.DataFrame:
    """Aggregate trailing-4-quarter (TTM) and prior-4-quarter features per district."""
    with sqlite3.connect(db_path) as conn:
        tx = pd.read_sql_query("SELECT * FROM fact_district_transactions", conn)
        usr = pd.read_sql_query("SELECT * FROM fact_district_users", conn)

    periods = (
        tx[["year", "quarter", "year_quarter"]]
        .drop_duplicates()
        .sort_values(["year", "quarter"])
        .reset_index(drop=True)
    )
    if len(periods) < 8:
        raise ValueError("Need at least 8 quarters of data for TTM vs prior-year growth.")

    ttm_quarters = set(periods.tail(4)["year_quarter"])
    prev_quarters = set(periods.iloc[-8:-4]["year_quarter"])
    latest_yq = periods.iloc[-1]["year_quarter"]

    ttm_tx = (
        tx[tx["year_quarter"].isin(ttm_quarters)]
        .groupby(["state", "district"], as_index=False)
        .agg(ttm_tx_count=("tx_count", "sum"), ttm_tx_amount=("tx_amount", "sum"))
    )
    prev_tx = (
        tx[tx["year_quarter"].isin(prev_quarters)]
        .groupby(["state", "district"], as_index=False)
        .agg(prev_tx_amount=("tx_amount", "sum"))
    )
    latest_usr = (
        usr[usr["year_quarter"] == latest_yq][["state", "district", "registered_users"]]
        .drop_duplicates(subset=["state", "district"])
    )

    df = ttm_tx.merge(prev_tx, on=["state", "district"], how="left").merge(
        latest_usr, on=["state", "district"], how="inner"
    )
    df = df[(df["ttm_tx_count"] > 0) & (df["ttm_tx_amount"] > 0) & (df["registered_users"] > 0)].copy()

    df["ttm_tpv_cr"] = (df["ttm_tx_amount"] / 1e7).round(2)
    df["avg_ticket_size"] = (df["ttm_tx_amount"] / df["ttm_tx_count"]).round(2)
    df["tx_per_user"] = (df["ttm_tx_count"] / df["registered_users"]).round(2)
    df["yoy_tpv_growth_pct"] = (
        ((df["ttm_tx_amount"] - df["prev_tx_amount"]) / df["prev_tx_amount"].replace(0, np.nan)) * 100
    ).fillna(0.0).clip(-100, 500).round(2)

    return df.reset_index(drop=True)


def run_clustering(out_dir: Path = PROCESSED_DIR, db_path: Path = DB_PATH) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Benchmark K-Means vs. GMM and export optimal 4-cluster district segments."""
    df = build_district_features(db_path)

    feature_cols = ["ttm_tpv_cr", "tx_per_user", "avg_ticket_size", "registered_users", "yoy_tpv_growth_pct"]
    X_raw = df[feature_cols].copy()
    for col in ["ttm_tpv_cr", "tx_per_user", "avg_ticket_size", "registered_users"]:
        X_raw[col] = np.log1p(X_raw[col])

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_raw)

    bench_rows = []
    for k in range(3, 7):
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        km_labels = km.fit_predict(X_scaled)
        bench_rows.append(
            {
                "model": "K-Means",
                "k": k,
                "silhouette_score": round(float(silhouette_score(X_scaled, km_labels)), 4),
                "davies_bouldin": round(float(davies_bouldin_score(X_scaled, km_labels)), 4),
            }
        )

        gmm = GaussianMixture(n_components=k, random_state=42)
        gmm_labels = gmm.fit_predict(X_scaled)
        bench_rows.append(
            {
                "model": "GMM",
                "k": k,
                "silhouette_score": round(float(silhouette_score(X_scaled, gmm_labels)), 4),
                "davies_bouldin": round(float(davies_bouldin_score(X_scaled, gmm_labels)), 4),
            }
        )

    bench_df = pd.DataFrame(bench_rows)

    optimal_k = 4
    km_final = KMeans(n_clusters=optimal_k, random_state=42, n_init=10)
    df["cluster_id"] = km_final.fit_predict(X_scaled)

    # Rank clusters deterministically by median TPV and growth
    profiles = df.groupby("cluster_id")[["ttm_tpv_cr", "tx_per_user", "yoy_tpv_growth_pct"]].median()
    ranked_by_tpv = profiles.sort_values("ttm_tpv_cr", ascending=False).index.tolist()

    persona_map = {
        ranked_by_tpv[0]: "Metro & Tier-1 Powerhouses",
        ranked_by_tpv[-1]: "Emerging Expansion Targets",
    }
    mid = [ranked_by_tpv[1], ranked_by_tpv[2]]
    if profiles.loc[mid[0], "yoy_tpv_growth_pct"] >= profiles.loc[mid[1], "yoy_tpv_growth_pct"]:
        persona_map[mid[0]] = "Hyper-Growth Tier-2/3 Hubs"
        persona_map[mid[1]] = "Mature Steady Markets"
    else:
        persona_map[mid[1]] = "Hyper-Growth Tier-2/3 Hubs"
        persona_map[mid[0]] = "Mature Steady Markets"

    df["segment"] = df["cluster_id"].map(persona_map)
    df["geo_key"] = df["state"] + " | " + df["district"]

    cols = [
        "geo_key", "state", "district", "ttm_tpv_cr", "ttm_tx_count",
        "registered_users", "tx_per_user", "avg_ticket_size",
        "yoy_tpv_growth_pct", "cluster_id", "segment",
    ]
    df = df[cols].sort_values("ttm_tpv_cr", ascending=False).reset_index(drop=True)

    df.to_csv(out_dir / "district_clusters.csv", index=False)
    bench_df.to_csv(out_dir / "clustering_benchmark.csv", index=False)
    with sqlite3.connect(db_path) as conn:
        df.to_sql("dim_district_clusters", conn, if_exists="replace", index=False)
        bench_df.to_sql("clustering_benchmark", conn, if_exists="replace", index=False)

    logger.info("District clustering complete (%d districts segmented into %d personas).", len(df), optimal_k)
    return df, bench_df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    run_clustering()
