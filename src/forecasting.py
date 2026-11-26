"""Multi-model UPI TPV forecasting bake-off with Walk-Forward CV & 4-quarter projections."""

import logging
import sqlite3
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from prophet import Prophet
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error, root_mean_squared_error
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.statespace.sarimax import SARIMAX
from xgboost import XGBRegressor

from src.config import DB_PATH, PROCESSED_DIR

warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)


def _smape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    denom = (np.abs(y_true) + np.abs(y_pred)) / 2.0
    return float(np.mean(np.where(denom == 0, 0, np.abs(y_true - y_pred) / denom)) * 100)


def _predict_seasonal_naive(train: pd.Series, steps: int = 1) -> np.ndarray:
    vals = train.values
    return np.array([vals[-4 + (i % 4)] for i in range(steps)], dtype=float)


def _predict_holt_winters(train: pd.Series, steps: int = 1) -> np.ndarray:
    model = ExponentialSmoothing(
        train.values, trend="add", seasonal="add", seasonal_periods=4, initialization_method="estimated"
    ).fit(optimized=True)
    return np.asarray(model.forecast(steps), dtype=float)


def _predict_sarima(train: pd.Series, steps: int = 1) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    model = SARIMAX(
        train.values,
        order=(1, 1, 1),
        seasonal_order=(1, 0, 0, 4),
        enforce_stationarity=False,
        enforce_invertibility=False,
    ).fit(disp=False)
    fc = model.get_forecast(steps=steps)
    ci = fc.conf_int()
    return np.asarray(fc.predicted_mean, dtype=float), np.asarray(ci[:, 0], dtype=float), np.asarray(ci[:, 1], dtype=float)


def _predict_prophet(dates: pd.Series, values: pd.Series, steps: int = 1) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    df_p = pd.DataFrame({"ds": pd.to_datetime(dates), "y": values.values})
    m = Prophet(yearly_seasonality=True, weekly_seasonality=False, daily_seasonality=False, seasonality_mode="multiplicative")
    m.fit(df_p)
    future = m.make_future_dataframe(periods=steps, freq="QS")
    fc = m.predict(future).tail(steps)
    return fc["yhat"].values, fc["yhat_lower"].values, fc["yhat_upper"].values


def _make_xgb_features(series: pd.Series) -> pd.DataFrame:
    df = pd.DataFrame({"y": series.values})
    df["lag_1"] = df["y"].shift(1)
    df["lag_2"] = df["y"].shift(2)
    df["lag_4"] = df["y"].shift(4)
    df["roll_4"] = df["y"].shift(1).rolling(4).mean()
    df["t"] = np.arange(len(df))
    df["q_sin"] = np.sin(2 * np.pi * (df["t"] % 4) / 4)
    df["q_cos"] = np.cos(2 * np.pi * (df["t"] % 4) / 4)
    return df


def _predict_xgboost(train: pd.Series, steps: int = 1) -> np.ndarray:
    feat_cols = ["lag_1", "lag_2", "lag_4", "roll_4", "t", "q_sin", "q_cos"]
    df = _make_xgb_features(train).dropna().reset_index(drop=True)
    model = XGBRegressor(n_estimators=120, max_depth=3, learning_rate=0.08, random_state=42)
    model.fit(df[feat_cols], df["y"])

    history = list(train.values)
    preds = []
    for _ in range(steps):
        t = len(history)
        row = pd.DataFrame(
            [
                {
                    "lag_1": history[-1],
                    "lag_2": history[-2],
                    "lag_4": history[-4],
                    "roll_4": np.mean(history[-4:]),
                    "t": t,
                    "q_sin": np.sin(2 * np.pi * (t % 4) / 4),
                    "q_cos": np.cos(2 * np.pi * (t % 4) / 4),
                }
            ]
        )
        pred = float(model.predict(row[feat_cols])[0])
        preds.append(pred)
        history.append(pred)
    return np.array(preds, dtype=float)


def run_forecasting(out_dir: Path = PROCESSED_DIR, db_path: Path = DB_PATH) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run expanding-window CV benchmark across 5 models and generate 4-quarter national & state forecasts."""
    with sqlite3.connect(db_path) as conn:
        nat = pd.read_sql_query(
            """
            SELECT n.*, d.quarter_start_date
            FROM fact_national_transactions n
            JOIN dim_date d ON n.year_quarter = d.year_quarter
            ORDER BY n.year, n.quarter
            """,
            conn,
        )
        state_df = pd.read_sql_query(
            """
            SELECT s.*, d.quarter_start_date
            FROM fact_state_transactions s
            JOIN dim_date d ON s.year_quarter = d.year_quarter
            ORDER BY s.state, s.year, s.quarter
            """,
            conn,
        )

    y = nat["tx_amount_cr"].reset_index(drop=True)
    dates = pd.to_datetime(nat["quarter_start_date"]).reset_index(drop=True)

    # Expanding-window walk-forward CV over the last 6 quarters (1-step ahead per fold)
    n_folds = 6
    start_idx = len(y) - n_folds
    records = {m: {"actual": [], "pred": []} for m in ["Seasonal Naive", "Holt-Winters", "SARIMA", "Prophet", "XGBoost"]}

    for split in range(start_idx, len(y)):
        train_y = y.iloc[:split]
        train_d = dates.iloc[:split]
        actual = float(y.iloc[split])

        records["Seasonal Naive"]["actual"].append(actual)
        records["Seasonal Naive"]["pred"].append(float(_predict_seasonal_naive(train_y, 1)[0]))

        records["Holt-Winters"]["actual"].append(actual)
        records["Holt-Winters"]["pred"].append(float(_predict_holt_winters(train_y, 1)[0]))

        sar_pred, _, _ = _predict_sarima(train_y, 1)
        records["SARIMA"]["actual"].append(actual)
        records["SARIMA"]["pred"].append(float(sar_pred[0]))

        prop_pred, _, _ = _predict_prophet(train_d, train_y, 1)
        records["Prophet"]["actual"].append(actual)
        records["Prophet"]["pred"].append(float(prop_pred[0]))

        records["XGBoost"]["actual"].append(actual)
        records["XGBoost"]["pred"].append(float(_predict_xgboost(train_y, 1)[0]))

    bench_rows = []
    for model_name, vals in records.items():
        yt = np.array(vals["actual"])
        yp = np.array(vals["pred"])
        bench_rows.append(
            {
                "model": model_name,
                "rmse_cr": round(float(root_mean_squared_error(yt, yp)), 2),
                "mae_cr": round(float(mean_absolute_error(yt, yp)), 2),
                "mape_pct": round(float(mean_absolute_percentage_error(yt, yp) * 100), 2),
                "smape_pct": round(_smape(yt, yp), 2),
            }
        )
    bench_df = pd.DataFrame(bench_rows).sort_values("mape_pct").reset_index(drop=True)
    best_model = bench_df.iloc[0]["model"]
    logger.info("Forecasting Bake-Off Winner: %s (MAPE: %.2f%%)", best_model, bench_df.iloc[0]["mape_pct"])

    # Fit on full history for next 4 quarters
    horizon = 4
    last_year = int(nat.iloc[-1]["year"])
    last_q = int(nat.iloc[-1]["quarter"])
    future_yqs, future_dates = [], []
    cy, cq = last_year, last_q
    for _ in range(horizon):
        cq += 1
        if cq > 4:
            cq = 1
            cy += 1
        future_yqs.append(f"{cy}-Q{cq}")
        future_dates.append(pd.Timestamp(year=cy, month=(cq - 1) * 3 + 1, day=1).strftime("%Y-%m-%d"))

    # Use winner for point forecast; use SARIMA/Prophet empirical CI if model doesn't emit native CI
    best_mae = float(bench_df.iloc[0]["mae_cr"])
    if best_model == "Prophet":
        fc_mean, fc_low, fc_high = _predict_prophet(dates, y, horizon)
    elif best_model == "SARIMA":
        fc_mean, fc_low, fc_high = _predict_sarima(y, horizon)
    elif best_model == "Holt-Winters":
        fc_mean = _predict_holt_winters(y, horizon)
        z = np.array([1.96 * best_mae * np.sqrt(i + 1) for i in range(horizon)])
        fc_low, fc_high = fc_mean - z, fc_mean + z
    elif best_model == "XGBoost":
        fc_mean = _predict_xgboost(y, horizon)
        z = np.array([1.96 * best_mae * np.sqrt(i + 1) for i in range(horizon)])
        fc_low, fc_high = fc_mean - z, fc_mean + z
    else:
        fc_mean = _predict_seasonal_naive(y, horizon)
        z = np.array([1.96 * best_mae * np.sqrt(i + 1) for i in range(horizon)])
        fc_low, fc_high = fc_mean - z, fc_mean + z

    hist_df = pd.DataFrame(
        {
            "year_quarter": nat["year_quarter"],
            "quarter_start_date": nat["quarter_start_date"],
            "record_type": "Historical",
            "actual_tpv_cr": nat["tx_amount_cr"].round(2),
            "forecast_tpv_cr": np.nan,
            "lower_ci_cr": np.nan,
            "upper_ci_cr": np.nan,
            "model_used": best_model,
        }
    )
    fc_df = pd.DataFrame(
        {
            "year_quarter": future_yqs,
            "quarter_start_date": future_dates,
            "record_type": "Forecast",
            "actual_tpv_cr": np.nan,
            "forecast_tpv_cr": np.round(fc_mean, 2),
            "lower_ci_cr": np.round(np.maximum(fc_low, 0), 2),
            "upper_ci_cr": np.round(fc_high, 2),
            "model_used": best_model,
        }
    )
    combined_fc = pd.concat([hist_df, fc_df], ignore_index=True)

    # Top 10 states 4-quarter forecast via Holt-Winters
    top_states = (
        state_df.groupby("state")["tx_amount_cr"].sum().sort_values(ascending=False).head(10).index.tolist()
    )
    state_fc_rows = []
    for st in top_states:
        st_sub = state_df[state_df["state"] == st].sort_values(["year", "quarter"])
        st_preds = _predict_holt_winters(st_sub["tx_amount_cr"], horizon)
        for yq, dt, pred in zip(future_yqs, future_dates, st_preds):
            state_fc_rows.append(
                {
                    "state": st,
                    "year_quarter": yq,
                    "quarter_start_date": dt,
                    "forecast_tpv_cr": round(float(max(pred, 0)), 2),
                }
            )
    state_fc_df = pd.DataFrame(state_fc_rows)

    bench_df.to_csv(out_dir / "forecast_benchmark.csv", index=False)
    combined_fc.to_csv(out_dir / "national_forecast.csv", index=False)
    state_fc_df.to_csv(out_dir / "state_forecasts.csv", index=False)

    with sqlite3.connect(db_path) as conn:
        bench_df.to_sql("forecast_benchmark", conn, if_exists="replace", index=False)
        combined_fc.to_sql("fact_national_forecast", conn, if_exists="replace", index=False)
        state_fc_df.to_sql("fact_state_forecasts", conn, if_exists="replace", index=False)

    return bench_df, combined_fc


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    run_forecasting()
