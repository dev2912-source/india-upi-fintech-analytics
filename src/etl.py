"""ETL pipeline for PhonePe Pulse JSON files -> Star Schema CSVs & SQLite warehouse."""

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd

from src.config import DB_PATH, PROCESSED_DIR, RAW_PULSE_DIR, format_state_name

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


def _quarter_dates(year: int, quarter: int) -> tuple[str, str]:
    start_month = (quarter - 1) * 3 + 1
    start = pd.Timestamp(year=year, month=start_month, day=1)
    end = start + pd.offsets.QuarterEnd(1)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f).get("data") or {}


def extract_national_categories(raw_dir: Path) -> pd.DataFrame:
    """Extract national quarterly transaction counts (and amounts where available) by category."""
    base = raw_dir / "aggregated" / "transaction" / "country" / "india"
    rows = []
    for year_dir in sorted(p for p in base.iterdir() if p.is_dir() and p.name.isdigit()):
        year = int(year_dir.name)
        for q_file in sorted(year_dir.glob("*.json")):
            quarter = int(q_file.stem)
            data = _load_json(q_file)
            for item in data.get("transactionData") or []:
                instruments = item.get("paymentInstruments") or []
                total = next((pi for pi in instruments if pi.get("type") == "TOTAL"), None)
                if not total:
                    continue
                count = total.get("count", 0)
                amount = total.get("amount")
                rows.append(
                    {
                        "year": year,
                        "quarter": quarter,
                        "year_quarter": f"{year}-Q{quarter}",
                        "category": item.get("name"),
                        "tx_count": int(count) if count is not None else 0,
                        "tx_amount": float(amount) if amount is not None else None,
                    }
                )
    return pd.DataFrame(rows)


def extract_state_transactions(raw_dir: Path) -> pd.DataFrame:
    """Extract state-level quarterly transaction counts and INR amounts."""
    base = raw_dir / "map" / "transaction" / "hover" / "country" / "india"
    rows = []
    for year_dir in sorted(p for p in base.iterdir() if p.is_dir() and p.name.isdigit()):
        year = int(year_dir.name)
        for q_file in sorted(year_dir.glob("*.json")):
            quarter = int(q_file.stem)
            data = _load_json(q_file)
            for item in data.get("hoverDataList") or []:
                metrics = item.get("metric") or []
                total = next((m for m in metrics if m.get("type") == "TOTAL"), None)
                if not total:
                    continue
                count = int(total.get("count", 0))
                amount = float(total.get("amount", 0.0))
                rows.append(
                    {
                        "year": year,
                        "quarter": quarter,
                        "year_quarter": f"{year}-Q{quarter}",
                        "state": format_state_name(item.get("name", "")),
                        "tx_count": count,
                        "tx_amount": amount,
                        "tx_amount_cr": round(amount / 1e7, 4),
                        "avg_ticket_size": round(amount / count, 2) if count > 0 else 0.0,
                    }
                )
    return pd.DataFrame(rows)


def extract_district_transactions(raw_dir: Path) -> pd.DataFrame:
    """Extract district-level quarterly transaction counts and INR amounts."""
    base = raw_dir / "map" / "transaction" / "hover" / "country" / "india" / "state"
    rows = []
    for state_dir in sorted(p for p in base.iterdir() if p.is_dir()):
        state_name = format_state_name(state_dir.name)
        for year_dir in sorted(p for p in state_dir.iterdir() if p.is_dir() and p.name.isdigit()):
            year = int(year_dir.name)
            for q_file in sorted(year_dir.glob("*.json")):
                quarter = int(q_file.stem)
                data = _load_json(q_file)
                for item in data.get("hoverDataList") or []:
                    metrics = item.get("metric") or []
                    total = next((m for m in metrics if m.get("type") == "TOTAL"), None)
                    if not total:
                        continue
                    count = int(total.get("count", 0))
                    amount = float(total.get("amount", 0.0))
                    district = item.get("name", "").replace(" district", "").strip().title()
                    rows.append(
                        {
                            "year": year,
                            "quarter": quarter,
                            "year_quarter": f"{year}-Q{quarter}",
                            "state": state_name,
                            "district": district,
                            "tx_count": count,
                            "tx_amount": amount,
                            "tx_amount_cr": round(amount / 1e7, 4),
                            "avg_ticket_size": round(amount / count, 2) if count > 0 else 0.0,
                        }
                    )
    return pd.DataFrame(rows)


def extract_state_users(raw_dir: Path) -> pd.DataFrame:
    """Extract state-level quarterly registered users and app opens."""
    base = raw_dir / "aggregated" / "user" / "country" / "india" / "state"
    rows = []
    for state_dir in sorted(p for p in base.iterdir() if p.is_dir()):
        state_name = format_state_name(state_dir.name)
        for year_dir in sorted(p for p in state_dir.iterdir() if p.is_dir() and p.name.isdigit()):
            year = int(year_dir.name)
            for q_file in sorted(year_dir.glob("*.json")):
                quarter = int(q_file.stem)
                data = _load_json(q_file)
                agg = data.get("aggregated") or {}
                reg = agg.get("registeredUsers") or agg.get("registeredCount") or 0
                opens = agg.get("appOpens")
                rows.append(
                    {
                        "year": year,
                        "quarter": quarter,
                        "year_quarter": f"{year}-Q{quarter}",
                        "state": state_name,
                        "registered_users": int(reg),
                        "app_opens": int(opens) if opens is not None else None,
                    }
                )
    return pd.DataFrame(rows)


def extract_district_users(raw_dir: Path) -> pd.DataFrame:
    """Extract district-level quarterly registered users."""
    base = raw_dir / "map" / "user" / "hover" / "country" / "india" / "state"
    rows = []
    for state_dir in sorted(p for p in base.iterdir() if p.is_dir()):
        state_name = format_state_name(state_dir.name)
        for year_dir in sorted(p for p in state_dir.iterdir() if p.is_dir() and p.name.isdigit()):
            year = int(year_dir.name)
            for q_file in sorted(year_dir.glob("*.json")):
                quarter = int(q_file.stem)
                data = _load_json(q_file)
                hover = data.get("hoverData") or {}
                for dist_raw, metrics in hover.items():
                    district = dist_raw.replace(" district", "").strip().title()
                    reg = metrics.get("registeredUsers") or metrics.get("registeredCount") or 0
                    opens = metrics.get("appOpens")
                    rows.append(
                        {
                            "year": year,
                            "quarter": quarter,
                            "year_quarter": f"{year}-Q{quarter}",
                            "state": state_name,
                            "district": district,
                            "registered_users": int(reg),
                            "app_opens": int(opens) if opens is not None else None,
                        }
                    )
    return pd.DataFrame(rows)


def build_dim_date(state_tx: pd.DataFrame) -> pd.DataFrame:
    """Build quarterly date dimension table."""
    pairs = state_tx[["year", "quarter", "year_quarter"]].drop_duplicates().sort_values(["year", "quarter"])
    records = []
    for _, row in pairs.iterrows():
        y, q = int(row["year"]), int(row["quarter"])
        start_dt, end_dt = _quarter_dates(y, q)
        records.append(
            {
                "year_quarter": row["year_quarter"],
                "year": y,
                "quarter": q,
                "quarter_label": f"Q{q}",
                "quarter_start_date": start_dt,
                "quarter_end_date": end_dt,
            }
        )
    return pd.DataFrame(records)


def build_dim_geography(district_tx: pd.DataFrame) -> pd.DataFrame:
    """Build geography dimension table."""
    geo = (
        district_tx[["state", "district"]]
        .drop_duplicates()
        .sort_values(["state", "district"])
        .reset_index(drop=True)
    )
    geo["geo_key"] = geo["state"] + " | " + geo["district"]
    return geo[["geo_key", "state", "district"]]


def run_etl(raw_dir: Path = RAW_PULSE_DIR, out_dir: Path = PROCESSED_DIR, db_path: Path = DB_PATH) -> None:
    """Execute full ETL pipeline and persist Star Schema CSVs + SQLite warehouse."""
    if not raw_dir.exists():
        raise FileNotFoundError(f"Raw PhonePe Pulse directory not found at {raw_dir}")

    out_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Extracting PhonePe Pulse JSON datasets...")

    nat_cat = extract_national_categories(raw_dir)
    state_tx = extract_state_transactions(raw_dir)
    dist_tx = extract_district_transactions(raw_dir)
    state_usr = extract_state_users(raw_dir)
    dist_usr = extract_district_users(raw_dir)

    dim_date = build_dim_date(state_tx)
    dim_geo = build_dim_geography(dist_tx)

    # National quarterly rollup from state transactions (ensures 100% INR amount coverage across all quarters)
    nat_tx = (
        state_tx.groupby(["year", "quarter", "year_quarter"], as_index=False)
        .agg(tx_count=("tx_count", "sum"), tx_amount=("tx_amount", "sum"))
        .sort_values(["year", "quarter"])
    )
    nat_tx["tx_amount_cr"] = (nat_tx["tx_amount"] / 1e7).round(2)
    nat_tx["avg_ticket_size"] = (nat_tx["tx_amount"] / nat_tx["tx_count"]).round(2)

    tables = {
        "dim_date": dim_date,
        "dim_geography": dim_geo,
        "fact_national_transactions": nat_tx,
        "fact_national_categories": nat_cat,
        "fact_state_transactions": state_tx,
        "fact_district_transactions": dist_tx,
        "fact_state_users": state_usr,
        "fact_district_users": dist_usr,
    }

    with sqlite3.connect(db_path) as conn:
        for name, df in tables.items():
            csv_path = out_dir / f"{name}.csv"
            df.to_csv(csv_path, index=False)
            df.to_sql(name, conn, if_exists="replace", index=False)
            logger.info("Saved %-28s | %7d rows -> %s", name, len(df), csv_path.name)

        conn.execute("CREATE INDEX IF NOT EXISTS idx_state_tx_yq ON fact_state_transactions(year_quarter, state)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_dist_tx_yq ON fact_district_transactions(year_quarter, state, district)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_state_usr_yq ON fact_state_users(year_quarter, state)")

    logger.info("ETL complete. SQLite warehouse ready at %s", db_path)


if __name__ == "__main__":
    run_etl()
