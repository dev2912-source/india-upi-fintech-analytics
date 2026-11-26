# Power BI 3-Page Executive Dashboard Blueprint

## Theme & Palette
* **Primary Navy:** `#1E3A8A` | **Accent Blue:** `#0284C7` | **Growth Green:** `#10B981` | **Forecast Amber:** `#F59E0B` | **Alert Coral:** `#EF4444`

---

## Page 1: National UPI Executive Overview
1. **Top KPI Cards:** `Total TPV (Lakh Cr)`, `Total Transactions (Cr)`, `Avg Ticket Size (INR)`, `YoY TPV Growth %`.
2. **Slicers:** `dim_date[year]`, `fact_state_transactions[state]`.
3. **India State Map / Filled Map:** State-level `Total TPV (Cr)`.
4. **Quarterly TPV & Ticket Size Combo Chart:** `dim_date[year_quarter]` vs. `[Total TPV (Cr)]` & `[Avg Ticket Size (INR)]`.
5. **Category Mix Stacked Area Chart:** `fact_national_categories[year_quarter]` split by `category` (*P2P, Retail, Utility*).

## Page 2: District Digital Maturity & Expansion Targets
1. **KPI Cards:** `District Count`, `Hyper-Growth Districts`, `Cluster TPV Share %`.
2. **Donut Chart:** District count by `dim_district_clusters[segment]`.
3. **Scatter Plot:** `tx_per_user` (X) vs. `ttm_tpv_cr` (Y) colored by `segment`, sized by `registered_users`.
4. **Actionable Matrix:** Top Expansion & Hyper-Growth districts with `yoy_tpv_growth_pct` and `avg_ticket_size`.

## Page 3: 4-Quarter TPV Forecast & State Anomaly Alerts
1. **KPI Cards:** Next 4-Quarter Projected TPV, Winning Model Name, Backtest MAPE %.
2. **Line + Shaded CI Chart:** `Historical TPV (Cr)` + `Forecast TPV (Cr)` with `Forecast Lower CI` / `Upper CI`.
3. **Anomaly Alerts Table:** `fact_anomaly_alerts` showing `state`, `year_quarter`, `qoq_tpv_growth_pct`, `peer_z_score`, and `anomaly_type`.
