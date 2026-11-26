# Power BI Desktop — Complete Step-by-Step Build Guide

Follow this guide from top to bottom to build a **3-page executive Power BI dashboard** (`India_UPI_Fintech_Dashboard.pbix`) from the processed data in `data/processed/`.

---

## Step 0: Apply the FinTech Theme (2 Clicks)
1. Open **Power BI Desktop** (blank report).
2. Go to **View** tab > **Themes** dropdown > **Browse for themes**.
3. Select [`power_bi/fintech_theme.json`](fintech_theme.json).
   * This automatically sets your canvas background (`#F8FAFC`), white rounded cards, subtle drop shadows, and corporate FinTech palette (`#1E3A8A` Navy, `#0284C7` Blue, `#10B981` Green, `#F59E0B` Amber, `#EF4444` Coral).

---

## Step 1: Load the Processed CSVs
Go to **Home** > **Get Data** > **Text/CSV** and load these **8 files** from `data/processed/` (click **Transform Data** after loading):

1. `dim_date.csv`
2. `fact_state_transactions.csv`
3. `fact_district_transactions.csv`
4. `fact_national_categories.csv`
5. `district_clusters.csv`
6. `national_forecast.csv`
7. `forecast_benchmark.csv`
8. `anomaly_alerts.csv`

---

## Step 2: Power Query Transformations (In Power Query Editor)

1. **Rename 3 tables** for clean Star Schema naming:
   * `district_clusters` → **`dim_district_clusters`**
   * `national_forecast` → **`fact_national_forecast`**
   * `anomaly_alerts` → **`fact_anomaly_alerts`**
2. **Add `geo_key` to `fact_district_transactions`:**
   * Select `fact_district_transactions` > **Add Column** > **Custom Column**.
   * New column name: `geo_key`
   * Formula: `= [state] & " | " & [district]`
   * Set data type to **Text**.
3. **Verify Date & Numeric Types:**
   * In `dim_date`: ensure `quarter_start_date` and `quarter_end_date` are **Date** type.
   * In `fact_national_forecast`: ensure `quarter_start_date` is **Date** type, and `actual_tpv_cr`, `forecast_tpv_cr`, `lower_ci_cr`, `upper_ci_cr` are **Decimal Number**.
   * In `fact_state_transactions` and `fact_district_transactions`: ensure `tx_count` is **Whole Number**, and `tx_amount`, `tx_amount_cr`, `avg_ticket_size` are **Decimal Number**.
4. Click **Home** > **Close & Apply**.

---

## Step 3: Set Sorting, Geography Categories & Relationships

### A. Column Sorting & Map Categories (Data View)
1. Select `dim_date` > click `year_quarter` > **Column tools** > **Sort by column** > `quarter_start_date`.
2. In `dim_date`, click **Table tools** > **Mark as date table** > select `quarter_start_date`.
3. Select `fact_state_transactions` > click `state` > **Column tools** > **Data category** > **State or Province**.
4. Select `dim_district_clusters` > click `state` > **Data category** > **State or Province**; click `district` > **Data category** > **County**.

### B. Model Relationships (Model View)
Create/verify these **3 relationships** (all **Many-to-One `*:1`**, **Single** cross-filter direction):

| From Table | From Column | To Table | To Column |
| :--- | :--- | :--- | :--- |
| `fact_state_transactions` | `year_quarter` | `dim_date` | `year_quarter` |
| `fact_district_transactions` | `year_quarter` | `dim_date` | `year_quarter` |
| `fact_national_categories` | `year_quarter` | `dim_date` | `year_quarter` |
| `fact_district_transactions` | `geo_key` | `dim_district_clusters` | `geo_key` |

> [!TIP]
> Keep `fact_national_forecast` **unlinked** from `dim_date` (because `fact_national_forecast` contains 4 future quarters `2026-Q3` to `2027-Q2` beyond `dim_date`). On Page 3, use `fact_national_forecast[year_quarter]` directly on the X-axis (sorted by `fact_national_forecast[quarter_start_date]`).

In Data View, select `fact_national_forecast` > click `year_quarter` > **Sort by column** > `quarter_start_date`.

---

## Step 4: Create the `_Measures` Table & Paste DAX

1. Click **Home** > **Enter Data** > name the table **`_Measures`** > click **Load**.
2. Right-click `_Measures` > **New measure** and paste each measure below (all column names match your CSVs):

### Core KPI Measures
```dax
Total TPV (Cr) = SUM ( fact_state_transactions[tx_amount_cr] )
```
```dax
Total TPV (Lakh Cr) = DIVIDE ( [Total TPV (Cr)], 100000, 0 )
```
```dax
Total Transactions (Bn) = DIVIDE ( SUM ( fact_state_transactions[tx_count] ), 1000000000, 0 )
```
```dax
Avg Ticket Size (INR) =
DIVIDE (
    SUM ( fact_state_transactions[tx_amount] ),
    SUM ( fact_state_transactions[tx_count] ),
    0
)
```

### Time-Intelligence Measures (YoY & QoQ)
```dax
TPV Prev Year (Cr) =
CALCULATE (
    [Total TPV (Cr)],
    DATEADD ( dim_date[quarter_start_date], -1, YEAR )
)
```
```dax
YoY TPV Growth % =
DIVIDE ( [Total TPV (Cr)] - [TPV Prev Year (Cr)], [TPV Prev Year (Cr)], 0 )
```
```dax
TPV Prev Quarter (Cr) =
CALCULATE (
    [Total TPV (Cr)],
    DATEADD ( dim_date[quarter_start_date], -1, QUARTER )
)
```
```dax
QoQ TPV Growth % =
DIVIDE ( [Total TPV (Cr)] - [TPV Prev Quarter (Cr)], [TPV Prev Quarter (Cr)], 0 )
```

### District Clustering Measures
```dax
District Count = DISTINCTCOUNT ( dim_district_clusters[geo_key] )
```
```dax
Hyper-Growth Districts =
CALCULATE (
    [District Count],
    dim_district_clusters[segment] = "Hyper-Growth Tier-2/3 Hubs"
)
```
```dax
Cluster TPV Share % =
VAR AllTPV = CALCULATE ( SUM ( dim_district_clusters[ttm_tpv_cr] ), ALL ( dim_district_clusters ) )
RETURN
DIVIDE ( SUM ( dim_district_clusters[ttm_tpv_cr] ), AllTPV, 0 )
```

### Forecasting Measures (Page 3)
```dax
Historical TPV (Cr) = SUM ( fact_national_forecast[actual_tpv_cr] )
```
```dax
Forecast TPV (Cr) = SUM ( fact_national_forecast[forecast_tpv_cr] )
```
```dax
Forecast Lower CI (Cr) = SUM ( fact_national_forecast[lower_ci_cr] )
```
```dax
Forecast Upper CI (Cr) = SUM ( fact_national_forecast[upper_ci_cr] )
```
```dax
Next 4Q Projected TPV (Lakh Cr) =
DIVIDE (
    CALCULATE (
        [Forecast TPV (Cr)],
        fact_national_forecast[record_type] = "Forecast"
    ),
    100000,
    0
)
```
```dax
Best Model MAPE % =
DIVIDE ( MIN ( forecast_benchmark[mape_pct] ), 100, 0 )
```

> [!NOTE]
> Format `YoY TPV Growth %`, `QoQ TPV Growth %`, `Cluster TPV Share %`, and `Best Model MAPE %` as **Percentage (1 decimal)**. Format `Avg Ticket Size (INR)` as **₹ Whole Number**.

---

## Step 5: Build the 3 Report Pages

### Page 1: `National UPI Executive Overview`
* **Header:** Title text box `"India UPI & Digital Payments Intelligence (2018–2026)"` + 2 Slicers (`dim_date[year]` dropdown, `fact_state_transactions[state]` dropdown).
* **Top KPI Row (4 New Card visuals):**
  1. `[Total TPV (Lakh Cr)]` (Label: *"Total Payment Value (₹ Lakh Cr)"*)
  2. `[Total Transactions (Bn)]` (Label: *"Total Transactions (Billions)"*)
  3. `[Avg Ticket Size (INR)]` (Label: *"Avg Ticket Size (₹)"*)
  4. `[YoY TPV Growth %]` (Label: *"YoY TPV Growth"*)
* **Middle Left (Line & Clustered Column Chart — 60% width):**
  * **X-axis:** `dim_date[year_quarter]`
  * **Column y-axis:** `[Total TPV (Cr)]`
  * **Line y-axis:** `[Avg Ticket Size (INR)]`
* **Middle Right (Filled Map or Bar Chart — 40% width):**
  * **Location / Y-axis:** `fact_state_transactions[state]` (Top 10 filter by `[Total TPV (Cr)]`)
  * **Color / X-axis:** `[Total TPV (Cr)]`
* **Bottom Full Width (100% Stacked Column Chart):**
  * **X-axis:** `dim_date[year_quarter]`
  * **Y-axis:** `SUM(fact_national_categories[tx_count])`
  * **Legend:** `fact_national_categories[category]` (*P2P, Retail, Utility*)

---

### Page 2: `District Digital Maturity & Expansion`
* **Header:** Slicer on `dim_district_clusters[state]` + Slicer on `dim_district_clusters[segment]`.
* **Top KPI Row (3 Cards):**
  1. `[District Count]` (783)
  2. `[Hyper-Growth Districts]`
  3. `[Cluster TPV Share %]`
* **Left (Donut Chart — 35% width):**
  * **Legend:** `dim_district_clusters[segment]`
  * **Values:** `[District Count]`
* **Right (Scatter Chart — 65% width):**
  * **Values:** `dim_district_clusters[district]`
  * **X-axis:** `dim_district_clusters[tx_per_user]`
  * **Y-axis:** `dim_district_clusters[ttm_tpv_cr]` (Turn **Logarithmic scale** ON in Y-axis formatting!)
  * **Legend:** `dim_district_clusters[segment]`
  * **Size:** `dim_district_clusters[registered_users]`
  * **Tooltips:** `state`, `avg_ticket_size`, `yoy_tpv_growth_pct`
* **Bottom (Matrix / Table Visual):**
  * **Columns:** `state`, `district`, `segment`, `ttm_tpv_cr`, `tx_per_user`, `avg_ticket_size`, `yoy_tpv_growth_pct`
  * Add **Conditional Formatting > Data bars** on `ttm_tpv_cr` and **Font color** (green/red) on `yoy_tpv_growth_pct`.

---

### Page 3: `TPV Forecasting & Anomaly Alerts`
* **Top KPI Row (3 Cards):**
  1. `[Next 4Q Projected TPV (Lakh Cr)]`
  2. `[Best Model MAPE %]` (`2.3%` — SARIMA)
  3. `COUNTROWS(fact_anomaly_alerts)` (65 flagged state-quarters)
* **Middle Left (Line Chart — 65% width):**
  * **X-axis:** `fact_national_forecast[year_quarter]`
  * **Y-axis:** `[Historical TPV (Cr)]`, `[Forecast TPV (Cr)]`, `[Forecast Lower CI (Cr)]`, `[Forecast Upper CI (Cr)]`
  * Format `Forecast TPV (Cr)` as dashed Amber `#F59E0B`, and Lower/Upper CI as light dotted lines.
* **Middle Right (Clustered Bar Chart — 35% width):**
  * **Title:** *"5-Model Walk-Forward CV Benchmark (Lower MAPE = Better)"*
  * **Y-axis:** `forecast_benchmark[model]`
  * **X-axis:** `forecast_benchmark[mape_pct]` (Turn Data Labels ON)
* **Bottom (Table Visual — Anomaly Alerts):**
  * **Columns:** `fact_anomaly_alerts[year_quarter]`, `state`, `tx_amount_cr`, `qoq_tpv_growth_pct`, `peer_z_score`, `anomaly_type`
  * Add **Conditional Formatting > Background color** on `anomaly_type` (*Abnormal Surge* = soft green/amber, *Abnormal Drop* = soft red).

---

## Step 6: Save & Publish for Your Portfolio
1. Save as `c:\Users\DEV PARMAR\Desktop\P_3_Fintech\India_UPI_Fintech_Dashboard.pbix`.
2. Take **3 clean screenshots** (one per page) using **Windows + Shift + S** and save them as:
   * `assets/pbi_page1_overview.png`
   * `assets/pbi_page2_clusters.png`
   * `assets/pbi_page3_forecast_anomalies.png`
3. Add those 3 screenshots to `README.md` so recruiters see your Power BI dashboard immediately on GitHub!
