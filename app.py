"""Interactive Streamlit dashboard for India UPI & Digital Payments analysis."""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.config import PROCESSED_DIR

st.set_page_config(
    page_title="India UPI & Digital Payments Analysis",
    layout="wide",
)

st.title("India UPI & Digital Payments Analysis (PhonePe Pulse)")
st.caption("Quarterly UPI trends, district segmentation, anomaly detection, and TPV forecasting (2018-2027)")


@st.cache_data
def load_tables():
    nat = pd.read_csv(PROCESSED_DIR / "fact_national_transactions.csv").sort_values(["year", "quarter"])
    cat = pd.read_csv(PROCESSED_DIR / "fact_national_categories.csv").sort_values(["year", "quarter"])
    states = pd.read_csv(PROCESSED_DIR / "fact_state_transactions.csv").sort_values(["year", "quarter"])
    clusters = pd.read_csv(PROCESSED_DIR / "district_clusters.csv")
    fc = pd.read_csv(PROCESSED_DIR / "national_forecast.csv")
    bench = pd.read_csv(PROCESSED_DIR / "forecast_benchmark.csv")
    state_fc = pd.read_csv(PROCESSED_DIR / "state_forecasts.csv")
    alerts = pd.read_csv(PROCESSED_DIR / "anomaly_alerts.csv")
    return nat, cat, states, clusters, fc, bench, state_fc, alerts


nat, cat, states, clusters, fc, bench, state_fc, alerts = load_tables()

tab1, tab2, tab3, tab4 = st.tabs([
    "National & State Overview",
    "District Segments",
    "TPV Forecasting",
    "Anomaly Alerts",
])

with tab1:
    latest = nat.iloc[-1]
    prev_yr = nat.iloc[-5] if len(nat) >= 5 else nat.iloc[0]
    yoy_tpv = ((latest["tx_amount_cr"] - prev_yr["tx_amount_cr"]) / prev_yr["tx_amount_cr"]) * 100

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"Latest Quarter TPV ({latest['year_quarter']})", f"₹{latest['tx_amount_cr']/1e5:.2f} Lakh Cr", f"{yoy_tpv:+.1f}% YoY")
    c2.metric("Latest Quarter Transactions", f"{latest['tx_count']/1e9:.2f} Bn")
    c3.metric("Avg Ticket Size", f"₹{latest['avg_ticket_size']:,.0f}")
    c4.metric("Districts Tracked", f"{len(clusters):,}")

    col_a, col_b = st.columns([3, 2])
    with col_a:
        fig_trend = px.area(
            nat, x="year_quarter", y="tx_amount_cr",
            title="National Quarterly Total Payment Value (₹ Crore)",
            labels={"year_quarter": "Quarter", "tx_amount_cr": "TPV (₹ Cr)"},
        )
        st.plotly_chart(fig_trend, use_container_width=True)
    with col_b:
        yr_sel = st.selectbox("Select Year for State Leaderboard", sorted(states["year"].unique(), reverse=True))
        top_st = (
            states[states["year"] == yr_sel]
            .groupby("state", as_index=False)["tx_amount_cr"]
            .sum()
            .sort_values("tx_amount_cr", ascending=False)
            .head(10)
        )
        fig_st = px.bar(
            top_st.sort_values("tx_amount_cr"),
            x="tx_amount_cr", y="state", orientation="h",
            title=f"Top 10 States by TPV ({yr_sel})",
            labels={"tx_amount_cr": "TPV (₹ Cr)", "state": "State"},
        )
        st.plotly_chart(fig_st, use_container_width=True)

    fig_cat = px.bar(
        cat, x="year_quarter", y="tx_count", color="category",
        title="Transaction Volume Mix by Category (P2P, Retail/Merchant, Utility)",
        labels={"year_quarter": "Quarter", "tx_count": "Transactions"},
    )
    st.plotly_chart(fig_cat, use_container_width=True)

with tab2:
    seg_filter = st.multiselect(
        "Filter District Segments",
        options=clusters["segment"].unique().tolist(),
        default=clusters["segment"].unique().tolist(),
    )
    filtered_c = clusters[clusters["segment"].isin(seg_filter)]

    fig_sc = px.scatter(
        filtered_c,
        x="tx_per_user",
        y="ttm_tpv_cr",
        color="segment",
        size="registered_users",
        log_y=True,
        hover_data=["state", "district", "avg_ticket_size", "yoy_tpv_growth_pct"],
        title="District Digital Maturity (Transactions/User vs. TTM TPV)",
        labels={"tx_per_user": "Transactions per User (TTM)", "ttm_tpv_cr": "TTM TPV (₹ Cr, Log)"},
    )
    st.plotly_chart(fig_sc, use_container_width=True)

    summary = (
        filtered_c.groupby("segment", as_index=False)
        .agg(
            districts=("district", "count"),
            avg_tpv_cr=("ttm_tpv_cr", "mean"),
            avg_tx_per_user=("tx_per_user", "mean"),
            avg_ticket_inr=("avg_ticket_size", "mean"),
            median_yoy_growth_pct=("yoy_tpv_growth_pct", "median"),
        )
        .round(2)
    )
    st.subheader("Segment Summary")
    st.dataframe(summary, use_container_width=True)
    st.subheader("District Explorer")
    st.dataframe(filtered_c.head(100), use_container_width=True)

with tab3:
    winner = bench.iloc[0]
    st.info(f"Best model on Walk-Forward CV: {winner['model']} (MAPE: {winner['mape_pct']:.2f}%, RMSE: ₹{winner['rmse_cr']:,.0f} Cr)")

    hist = fc[fc["record_type"] == "Historical"]
    pred = fc[fc["record_type"] == "Forecast"]

    fig_fc = go.Figure()
    fig_fc.add_trace(go.Scatter(x=hist["year_quarter"], y=hist["actual_tpv_cr"], name="Historical TPV", line=dict(color="#1E3A8A", width=3)))
    fig_fc.add_trace(go.Scatter(x=pred["year_quarter"], y=pred["forecast_tpv_cr"], name=f"Forecast ({winner['model']})", line=dict(color="#F59E0B", width=3, dash="dash")))
    fig_fc.add_trace(go.Scatter(
        x=pd.concat([pred["year_quarter"], pred["year_quarter"][::-1]]),
        y=pd.concat([pred["upper_ci_cr"], pred["lower_ci_cr"][::-1]]),
        fill="toself",
        fillcolor="rgba(253, 230, 138, 0.4)",
        line=dict(color="rgba(255,255,255,0)"),
        name="95% CI",
    ))
    fig_fc.update_layout(title="National UPI TPV: Historical & 4-Quarter Forecast (₹ Cr)", xaxis_title="Quarter", yaxis_title="TPV (₹ Cr)")
    st.plotly_chart(fig_fc, use_container_width=True)

    col_l, col_r = st.columns(2)
    with col_l:
        st.subheader("5-Model Walk-Forward CV Benchmark")
        st.dataframe(bench, use_container_width=True)
    with col_r:
        st.subheader("Top-10 State 4-Quarter Forecast (₹ Cr)")
        st.dataframe(state_fc, use_container_width=True)

with tab4:
    st.subheader("Flagged State-Quarter Payment Surges & Drops (Isolation Forest + Peer Z-Score)")
    st.dataframe(alerts[["year_quarter", "state", "tx_amount_cr", "qoq_tpv_growth_pct", "peer_z_score", "anomaly_type"]], use_container_width=True)
