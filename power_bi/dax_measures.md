# Power BI DAX Measures Library (Indian FinTech)

Organize these measures inside a dedicated **`_Measures`** table in Power BI Desktop.

---

## 1. Core UPI Volume & Value Measures

```dax
Total TPV (Cr) =
SUM ( fact_state_transactions[tx_amount_cr] )
```

```dax
Total TPV (Lakh Cr) =
DIVIDE ( [Total TPV (Cr)], 100000, 0 )
```

```dax
Total Transactions (Cr) =
DIVIDE ( SUM ( fact_state_transactions[tx_count] ), 10000000, 0 )
```

```dax
Avg Ticket Size (INR) =
DIVIDE (
    SUM ( fact_state_transactions[tx_amount] ),
    SUM ( fact_state_transactions[tx_count] ),
    0
)
```

---

## 2. Time-Intelligence (YoY & QoQ Growth)

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

---

## 3. District Clustering & Expansion Measures

```dax
District Count =
DISTINCTCOUNT ( dim_district_clusters[geo_key] )
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

---

## 4. Forecasting Measures

```dax
Historical TPV (Cr) =
SUM ( fact_national_forecast[actual_tpv_cr] )
```

```dax
Forecast TPV (Cr) =
SUM ( fact_national_forecast[forecast_tpv_cr] )
```

```dax
Forecast Lower CI (Cr) =
SUM ( fact_national_forecast[lower_ci_cr] )
```

```dax
Forecast Upper CI (Cr) =
SUM ( fact_national_forecast[upper_ci_cr] )
```
