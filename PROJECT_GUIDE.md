# Complete Project Guide: India UPI & Digital Payments Intelligence

This guide explains the problem statement, dataset structure, business logic, modeling decisions, code architecture, and interview talking points for `P_3_Fintech`.

---

## 1. Problem Statement

India's Unified Payments Interface (UPI) processes billions of transactions every quarter, but payment adoption, ticket sizes, and growth rates vary sharply across states and districts. Payment aggregators, fintechs, and merchant-acquiring teams (such as PhonePe, Razorpay, Paytm, and CRED) face four operational questions:

1. **Market Growth & Category Mix:** How is national Total Payment Value (TPV) growing, what is happening to average ticket size as UPI shifts from P2P transfers to small-ticket retail payments, and which states drive the majority of volume?
2. **Geographic Expansion Strategy:** Across 783 Indian districts, where should merchant QR deployment, onboarding incentives, and credit/BNPL cross-sell be prioritized?
3. **Capacity & Revenue Forecasting:** What will national and top-state UPI TPV look like over the next 4 quarters, and how accurately can we predict it without data leakage?
4. **Operational & Market Anomaly Monitoring:** Which states experienced abnormal quarter-over-quarter payment surges or drops compared to national peers?

---

## 2. Dataset & Engineering Challenges Solved

* **Source:** Official **PhonePe Pulse** open dataset (`data/raw/pulse/data/`), covering **34 quarters** from `2018-Q1` to `2026-Q2` across **36 States/UTs** and **783 Districts**.
* **Key Data Challenges Handled in `src/etl.py`:**
  * **Deeply Nested JSONs:** Raw data is split across thousands of quarterly JSON files (`aggregated/`, `map/`, `top/`). The ETL pipeline flattens them into a clean Star Schema (`dim_date`, `dim_geography`, `fact_*`) and loads them into a queryable SQLite warehouse (`data/processed/pulse_fintech.db`).
  * **Schema Drift in Newer Quarters:** In 2024+ `aggregated/transaction` files, the `amount` field is omitted at the category level. To maintain 100% INR coverage across all 34 quarters, `fact_national_transactions` is aggregated directly from `fact_state_transactions` (which retains both `count` and `amount` for every quarter).
  * **Inconsistent Naming:** State slugs (e.g., `dadra-&-nagar-haveli-&-daman-&-diu`, `jammu-&-kashmir`) and district names (`"ahilyanagar district"`) are normalized via `STATE_NAME_MAP` and string cleanup so Power BI maps and SQL joins match cleanly.

---

## 3. Core Business Logic & Metrics

| Metric / Rule | Formula / Logic | Business Meaning |
| :--- | :--- | :--- |
| **TPV (₹ Crore)** | `tx_amount / 1e7` | Standardized Indian financial unit for payment volume (1 Lakh Cr = 100,000 Cr). |
| **Average Ticket Size (₹)** | `tx_amount / tx_count` | Indicates whether a market is dominated by small-ticket retail/merchant scans or higher-value transfers. |
| **YoY TPV Growth (%)** | `(TPV_t - TPV_{t-4}) / TPV_{t-4} * 100` | Removes quarterly seasonality by comparing each quarter to the same quarter in the prior year. |
| **QoQ TPV Growth (%)** | `(TPV_t - TPV_{t-1}) / TPV_{t-1} * 100` | Captures immediate quarter-to-quarter momentum and sudden shocks. |
| **Transactions per User (TTM)** | `TTM_tx_count / latest_registered_users` | Measures engagement depth (velocity per registered user over the trailing 12 months). |
| **District Growth Clamping** | `.clip(-100, 500)` on `yoy_tpv_growth_pct` | Prevents newly carved or near-zero-base districts from distorting K-Means centroids. |

---

## 4. How Each Analytical Problem Is Solved

### A. SQL Warehouse Analytics (`src/sql_analytics.py`)
* Queries `pulse_fintech.db` using **CTEs and SQL window functions** (`LAG(..., 4) OVER (ORDER BY year, quarter)` and `SUM(...) OVER ()`).
* Key result: In the latest full year (2025), the top 5 states—**Maharashtra (11.75%)**, **Karnataka (11.55%)**, **Telangana (10.89%)**, **Andhra Pradesh (9.82%)**, and **Uttar Pradesh (8.73%)**—account for over half of national TPV.

### B. District Digital Maturity Clustering (`src/clustering.py`)
* **Feature Engineering:** Aggregates trailing-12-month (TTM) TPV, transaction count, registered users, transactions per user, average ticket size, and YoY TPV growth for **783 districts**.
* **Preprocessing:** Applies `np.log1p` to right-skewed volume/user metrics (`ttm_tpv_cr`, `tx_per_user`, `avg_ticket_size`, `registered_users`) followed by `StandardScaler` so large metros do not dominate Euclidean distances.
* **Model Selection:** Benchmarks **K-Means** vs. **Gaussian Mixture Models (GMM)** for $k \in \{3, 4, 5, 6\}$ using Silhouette Score and Davies-Bouldin Index.
* **Deterministic Persona Mapping ($k=4$):** Rather than hardcoding cluster IDs (which can swap on re-runs), clusters are ranked by median TPV and YoY growth into 4 personas:
  1. **Metro & Tier-1 Powerhouses:** Highest TPV and velocity; focus on retention, UPI Lite, and credit-on-UPI.
  2. **Hyper-Growth Tier-2/3 Hubs:** Strong YoY TPV growth; highest ROI for merchant QR acquisition and working-capital lending.
  3. **Mature Steady Markets:** High ticket size with moderate growth; focus on bill-pay and insurance/wealth cross-sell.
  4. **Emerging Expansion Targets:** Low penetration; focus on user onboarding and cashback incentives.

### C. State Anomaly Detection (`src/anomaly_detection.py`)
* Combines two complementary signals on state-quarter QoQ growth:
  1. **Cross-Sectional Peer Z-Score:** Measures how far a state's QoQ growth diverges from the national peer average in that same quarter (`|peer_z_score| >= 2.5`). This isolates state-specific events from national macro trends (like COVID lockdowns or festive quarters).
  2. **Isolation Forest (`contamination=0.04`):** Multivariate outlier detection across `qoq_tpv_growth_pct`, `qoq_tx_growth_pct`, and `avg_ticket_size`.
* Flags **65 state-quarter alerts**, labeled as **Abnormal Surge** or **Abnormal Drop**.

### D. Multi-Model TPV Forecasting Bake-Off (`src/forecasting.py`)
* **Validation Strategy (No Data Leakage):** Uses **6-quarter expanding-window Walk-Forward Cross-Validation** (1-step-ahead predictions on the last 6 quarters). At each step, models are trained strictly on past quarters before predicting the next quarter.
* **5 Models Benchmarked:**
  1. **Seasonal Naive** (`y_{t-4}`) — Baseline (`16.01%` MAPE)
  2. **Prophet** (multiplicative seasonality) — `14.43%` MAPE
  3. **XGBoost** (lag-1, lag-2, lag-4, 4Q rolling mean, trend, sin/cos quarter encoding) — `5.40%` MAPE
  4. **Holt-Winters Exponential Smoothing** (additive trend + seasonal, period=4) — `2.45%` MAPE
  5. **SARIMA `(1,1,1)(1,0,0,4)`** — **Winner at `2.31%` MAPE** (RMSE `₹97,345.77 Cr`)
* **Production Forecast:** Automatically selects the lowest-MAPE model (`SARIMA`) to project the next **4 quarters** (`2026-Q3` to `2027-Q2`) with 95% confidence intervals, plus Holt-Winters 4-quarter forecasts for the top 10 states.

---

## 5. Repository File Reference

| Path | Purpose |
| :--- | :--- |
| `src/config.py` | Centralized `pathlib` paths and `STATE_NAME_MAP` normalization. |
| `src/etl.py` | Parses PhonePe Pulse JSONs into 8 Star Schema CSVs + SQLite warehouse. |
| `src/sql_analytics.py` | Reusable SQL queries (YoY growth, state rankings, category mix). |
| `src/clustering.py` | K-Means vs. GMM benchmark and 783-district persona segmentation. |
| `src/anomaly_detection.py` | Isolation Forest + Peer Z-Score state anomaly alerting. |
| `src/forecasting.py` | 5-model Walk-Forward CV bake-off and 4-quarter national/state forecasts. |
| `src/generate_charts.py` | Generates 4 high-resolution PNG charts in `assets/`. |
| `run_pipeline.py` | Single-command CLI runner (`etl -> clustering -> anomaly -> forecasting -> charts`). |
| `app.py` | 4-tab interactive Streamlit dashboard reading from `pulse_fintech.db`. |
| `tests/test_pipeline.py` | `pytest` suite validating CSV schemas, SQLite tables, clusters, and CI bounds. |
| `power_bi/` | Star schema docs, DAX library, `fintech_theme.json`, and step-by-step build guide. |
| `notebooks/` | 3 Jupyter notebooks for interactive exploration of SQL EDA, clustering, and forecasting. |

---

## 6. Interview Prep: Key Questions & Answers

1. **Why did SARIMA and Holt-Winters beat XGBoost and Prophet on this dataset?**
   * We have **34 quarterly observations**. Classical state-space/exponential smoothing models (`SARIMA`, `Holt-Winters`) are data-efficient on short, smooth, strongly trending quarterly series. Tree models (`XGBoost`) cannot extrapolate a linear/exponential trend beyond the training range without differencing, and `Prophet`'s default piecewise changepoints over-reacted to early-year hyper-growth rates.
2. **Why did you use log transformation before K-Means?**
   * District TPV ranges from tens of crores in small districts to lakhs of crores in Bengaluru/Mumbai. Without `np.log1p`, Euclidean distance is dominated entirely by metro outliers, collapsing all Tier-2/3 districts into a single cluster.
3. **Why use Peer Z-Score in anomaly detection instead of a global Z-score?**
   * A global Z-score flags every state during a nationwide event (like Q2 2020 COVID or Q4 festive peaks). A cross-sectional Peer Z-Score compares each state against other states *in the same quarter*, isolating true local anomalies.
4. **How does the clustering output drive actual business decisions?**
   * Instead of treating all 783 districts identically, fintech growth teams can allocate merchant-acquisition budgets to **Hyper-Growth Tier-2/3 Hubs**, retention/credit products to **Metro Powerhouses**, and user-activation incentives to **Emerging Expansion Targets**.
