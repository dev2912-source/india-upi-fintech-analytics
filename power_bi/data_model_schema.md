# Power BI Data Model Schema (Star Schema)

This document defines the Star Schema for **India UPI & Digital Payments Intelligence** in Power BI Desktop using `data/processed/`.

---

## 1. Star Schema Architecture

```text
                  +-----------------------------+
                  |          dim_date           |
                  |  (year_quarter, year, Q)    |
                  +-----------------------------+
                     | 1                  | 1
                     |                    |
                     | *                  | *
+-------------------------------+    +-----------------------------+
|  fact_district_transactions   |    |   fact_national_forecast    |
|  (tx_count, tx_amount_cr)     |    | (actual_tpv_cr, forecast)   |
+-------------------------------+    +-----------------------------+
            | *
            |
            | 1
+-------------------------------+
|    dim_district_clusters      |
| (geo_key, state, district,    |
|  segment, ttm_tpv_cr, growth) |
+-------------------------------+
```

*(Optionally load `fact_state_transactions`, `fact_national_categories`, and `fact_anomaly_alerts` for executive summary and anomaly drill-downs.)*

---

## 2. Relationships & Cardinality

| From Table | From Column | To Table | To Column | Cardinality | Cross-Filter | Active |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `fact_district_transactions` | `year_quarter` | `dim_date` | `year_quarter` | Many-to-One (`*:1`) | Single | Yes |
| `fact_national_forecast` | `year_quarter` | `dim_date` | `year_quarter` | Many-to-One (`*:1`) | Single | Yes |
| `fact_district_transactions` | `geo_key` *(calculated: `state & " | " & district`)* | `dim_district_clusters` | `geo_key` | Many-to-One (`*:1`) | Single | Yes |
| `fact_state_transactions` | `year_quarter` | `dim_date` | `year_quarter` | Many-to-One (`*:1`) | Single | Yes |
