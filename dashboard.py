from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st


# =====================================================
# CONFIG
# =====================================================

BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "hotel_data.duckdb"

st.set_page_config(
    page_title="Hotel Dashboard",
    layout="wide"
)

st.title("Hotel Performance Dashboard")


# =====================================================
# LOAD DATA
# =====================================================

con = duckdb.connect(str(DB_FILE))

monthly_kpis = con.execute("""
    SELECT *
    FROM monthly_kpis
    ORDER BY month
""").fetchdf()

ota_sales = con.execute("""
    SELECT *
    FROM monthly_ota_sales
    ORDER BY month, channel
""").fetchdf()

con.close()


# =====================================================
# CLEAN DATA
# =====================================================

monthly_kpis["month_date"] = pd.to_datetime(
    monthly_kpis["month"],
    errors="coerce"
)

ota_sales["month_date"] = pd.to_datetime(
    ota_sales["month"],
    errors="coerce"
)

monthly_kpis = monthly_kpis.sort_values("month_date")
ota_sales = ota_sales.sort_values(["month_date", "channel"])

monthly_kpis["month_label"] = (
    monthly_kpis["month_date"]
    .dt.strftime("%b %Y")
)

ota_sales["month_label"] = (
    ota_sales["month_date"]
    .dt.strftime("%b %Y")
)

month_order = (
    monthly_kpis["month_label"]
    .dropna()
    .tolist()
)

numeric_kpi_cols = [
    "sales",
    "target",
    "achievement_rate",
    "occupancy_rate",
    "adr",
    "revpar",
]

for col in numeric_kpi_cols:

    if col in monthly_kpis.columns:

        monthly_kpis[col] = pd.to_numeric(
            monthly_kpis[col],
            errors="coerce"
        )

ota_sales["sales"] = pd.to_numeric(
    ota_sales["sales"],
    errors="coerce"
)

monthly_kpis["occupancy_pct"] = (
    monthly_kpis["occupancy_rate"] * 100
)

monthly_kpis["achievement_pct"] = (
    monthly_kpis["achievement_rate"] * 100
)

ota_sales["share"] = (
    ota_sales["sales"]
    / ota_sales.groupby("month_label")["sales"].transform("sum")
)

# =====================================================
# DEFINE HISTORICAL VS FUTURE
# =====================================================

today_cutoff = pd.Timestamp("2026-04-30")

monthly_kpis["period_type"] = monthly_kpis["month_date"].apply(
    lambda x: "Historical"
    if x <= today_cutoff
    else "Future / Forecast"
)

# =====================================================
# SIDEBAR FILTERS
# =====================================================

st.sidebar.header("Filters")

selected_months = st.sidebar.multiselect(
    "Months",
    month_order,
    default=month_order
)

monthly_kpis_filtered = monthly_kpis[
    monthly_kpis["month_label"].isin(selected_months)
].copy()

ota_sales_filtered = ota_sales[
    ota_sales["month_label"].isin(selected_months)
].copy()

if monthly_kpis_filtered.empty:
    st.warning("No data selected.")
    st.stop()


# =====================================================
# KPI DASHBOARD
# =====================================================

st.header("1. Monthly KPI Dashboard")

latest_hist = monthly_kpis_filtered[
    monthly_kpis_filtered["period_type"] == "Historical"
]

latest = latest_hist.dropna(subset=["sales"]).iloc[-1]

col1, col2, col3, col4, col5 = st.columns(5)

col1.metric(
    "Sales",
    f"¥{latest['sales']:,.0f}"
)

col2.metric(
    "Target",
    f"¥{latest['target']:,.0f}"
)

col3.metric(
    "Achievement Rate",
    f"{latest['achievement_pct']:,.1f}%"
)

col4.metric(
    "Occupancy Rate",
    f"{latest['occupancy_pct']:,.1f}%"
)

col5.metric(
    "RevPAR",
    f"¥{latest['revpar']:,.0f}"
)

st.caption(
    """
Solid lines = historical actual data.
Dashed lines = future / forecast values from the source Excel.
"""
)

# =====================================================
# SALES VS TARGET
# =====================================================

st.header("2. Sales vs Target Trend")

hist = monthly_kpis_filtered[
    monthly_kpis_filtered["period_type"] == "Historical"
]

future = monthly_kpis_filtered[
    monthly_kpis_filtered["period_type"] == "Future / Forecast"
]

fig = go.Figure()

# Historical Sales
fig.add_trace(
    go.Scatter(
        x=hist["month_label"],
        y=hist["sales"],
        mode="lines+markers",
        name="Historical Sales",
        line=dict(color="blue"),
    )
)

# Future Sales
fig.add_trace(
    go.Scatter(
        x=future["month_label"],
        y=future["sales"],
        mode="lines+markers",
        name="Future / Forecast Sales",
        line=dict(color="lightblue", dash="dash"),
    )
)

# Historical Target
fig.add_trace(
    go.Scatter(
        x=hist["month_label"],
        y=hist["target"],
        mode="lines+markers",
        name="Historical Target",
        line=dict(color="darkorange"),
    )
)

# Future Target
fig.add_trace(
    go.Scatter(
        x=future["month_label"],
        y=future["target"],
        mode="lines+markers",
        name="Future / Forecast Target",
        line=dict(color="orange", dash="dash"),
    )
)

fig.update_layout(
    title="Actual Sales vs Revenue Target",
    xaxis_title="Month",
    yaxis_title="JPY",
    hovermode="x unified",
)

fig.update_xaxes(
    type="category",
    categoryorder="array",
    categoryarray=month_order
)

fig.update_yaxes(
    tickprefix="¥"
)

st.plotly_chart(fig, use_container_width=True)

# =====================================================
# OCCUPANCY / ADR / REVPAR
# =====================================================

st.header("3. Occupancy / ADR / RevPAR Evolution")

fig = make_subplots(
    specs=[[{"secondary_y": True}]]
)

# Historical occupancy
fig.add_trace(
    go.Scatter(
        x=hist["month_label"],
        y=hist["occupancy_pct"],
        name="Historical Occupancy %",
        mode="lines+markers",
        line=dict(color="blue"),
    ),
    secondary_y=False,
)

# Future occupancy
fig.add_trace(
    go.Scatter(
        x=future["month_label"],
        y=future["occupancy_pct"],
        name="Future Occupancy %",
        mode="lines+markers",
        line=dict(color="lightblue", dash="dash"),
    ),
    secondary_y=False,
)

# Historical ADR
fig.add_trace(
    go.Scatter(
        x=hist["month_label"],
        y=hist["adr"],
        name="Historical ADR",
        mode="lines+markers",
        line=dict(color="green"),
    ),
    secondary_y=True,
)

# Future ADR
fig.add_trace(
    go.Scatter(
        x=future["month_label"],
        y=future["adr"],
        name="Future ADR",
        mode="lines+markers",
        line=dict(color="lightgreen", dash="dash"),
    ),
    secondary_y=True,
)

# Historical RevPAR
fig.add_trace(
    go.Scatter(
        x=hist["month_label"],
        y=hist["revpar"],
        name="Historical RevPAR",
        mode="lines+markers",
        line=dict(color="red"),
    ),
    secondary_y=True,
)

# Future RevPAR
fig.add_trace(
    go.Scatter(
        x=future["month_label"],
        y=future["revpar"],
        name="Future RevPAR",
        mode="lines+markers",
        line=dict(color="pink", dash="dash"),
    ),
    secondary_y=True,
)

fig.update_xaxes(
    type="category",
    categoryorder="array",
    categoryarray=month_order
)

fig.update_yaxes(
    title_text="Occupancy %",
    range=[0, 100],
    ticksuffix="%",
    secondary_y=False,
)

fig.update_yaxes(
    title_text="ADR / RevPAR (JPY)",
    tickprefix="¥",
    secondary_y=True,
)

fig.update_layout(
    title="Occupancy vs ADR / RevPAR",
    hovermode="x unified",
)

st.plotly_chart(fig, use_container_width=True)

# =====================================================
# OTA MIX
# =====================================================

st.header("4. OTA Channel Mix")

fig = px.bar(
    ota_sales_filtered,
    x="month_label",
    y="sales",
    color="channel",
    barmode="group",
    title="Revenue by Booking Channel",
    category_orders={"month_label": month_order},
    labels={
        "month_label": "Month",
        "sales": "Revenue (JPY)",
        "channel": "Booking Channel",
    },
)

fig.update_xaxes(
    type="category",
    categoryorder="array",
    categoryarray=month_order
)

fig.update_yaxes(
    tickprefix="¥"
)

fig.update_layout(
    hovermode="x unified",
    legend_title_text="Booking Channel"
)

st.plotly_chart(fig, use_container_width=True)

st.caption(
    """
Grouped bars make smaller channels easier to compare visually.
"""
)

# =====================================================
# OTA SUMMARY TABLE
# =====================================================

st.subheader("OTA Revenue Summary")

ota_summary = (
    ota_sales_filtered
    .groupby("channel", as_index=False)
    .agg({
        "sales": "sum",
    })
    .sort_values("sales", ascending=False)
)

ota_summary["share_pct"] = (
    ota_summary["sales"]
    / ota_summary["sales"].sum()
    * 100
)

ota_summary["sales"] = ota_summary["sales"].round(0)
ota_summary["share_pct"] = ota_summary["share_pct"].round(1)

st.dataframe(
    ota_summary,
    use_container_width=True
)

# =====================================================
# CHANNEL DEPENDENCY
# =====================================================

st.header("5. Channel Dependency Risk")

fig = px.area(
    ota_sales_filtered,
    x="month_label",
    y="share",
    color="channel",
    title="Revenue Share by Booking Channel",
    category_orders={"month_label": month_order},
)

fig.update_xaxes(
    type="category",
    categoryorder="array",
    categoryarray=month_order
)

fig.update_yaxes(
    tickformat=".0%"
)

st.plotly_chart(fig, use_container_width=True)

# =====================================================
# TABLES
# =====================================================

st.header("6. Monthly KPI Table")

st.dataframe(
    monthly_kpis_filtered,
    use_container_width=True
)

st.header("7. OTA Revenue Table")

st.dataframe(
    ota_sales_filtered,
    use_container_width=True
)