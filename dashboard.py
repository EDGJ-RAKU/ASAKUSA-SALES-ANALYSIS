from pathlib import Path

import duckdb

import pandas as pd

import plotly.express as px

import plotly.graph_objects as go

from plotly.subplots import make_subplots

import streamlit as st

BASE_DIR = Path(__file__).resolve().parent

DB_FILE = BASE_DIR / "hotel_data.duckdb"

st.set_page_config(page_title="Hotel Dashboard", layout="wide")

st.title("Hotel Performance Dashboard")

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

reservations = con.execute("""

    SELECT *

    FROM reservations

""").fetchdf()

con.close()

monthly_kpis["month_date"] = pd.to_datetime(monthly_kpis["month"], errors="coerce")

ota_sales["month_date"] = pd.to_datetime(ota_sales["month"], errors="coerce")

reservations["month_date"] = pd.to_datetime(reservations["month"], errors="coerce")

monthly_kpis = monthly_kpis.sort_values("month_date")

ota_sales = ota_sales.sort_values(["month_date", "channel"])

reservations = reservations.sort_values(["month_date", "country_region"])

monthly_kpis["month_label"] = monthly_kpis["month_date"].dt.strftime("%b %Y")

ota_sales["month_label"] = ota_sales["month_date"].dt.strftime("%b %Y")

reservations["month_label"] = reservations["month_date"].dt.strftime("%b %Y")

for col in ["sales", "target", "achievement_rate", "occupancy_rate", "adr", "revpar"]:

    monthly_kpis[col] = pd.to_numeric(monthly_kpis[col], errors="coerce")

ota_sales["sales"] = pd.to_numeric(ota_sales["sales"], errors="coerce").fillna(0)

ota_sales["booking_count"] = pd.to_numeric(ota_sales["booking_count"], errors="coerce").fillna(0)

reservations["received_amount"] = pd.to_numeric(

    reservations["received_amount"],

    errors="coerce"

).fillna(0)

reservations["gross_booking_amount"] = pd.to_numeric(

    reservations["gross_booking_amount"],

    errors="coerce"

).fillna(0)

reservations["guest_nights"] = pd.to_numeric(

    reservations["guest_nights"],

    errors="coerce"

).fillna(0)

monthly_kpis["occupancy_pct"] = monthly_kpis["occupancy_rate"] * 100

monthly_kpis["achievement_pct"] = monthly_kpis["achievement_rate"] * 100

# Latest known month = latest month with actual sales

latest_known_month = monthly_kpis.loc[

    monthly_kpis["sales"].fillna(0) > 0,

    "month_date"

].max()

monthly_kpis = monthly_kpis[

    monthly_kpis["month_date"] <= latest_known_month

].copy()

ota_sales = ota_sales[

    ota_sales["month_date"] <= latest_known_month

].copy()

reservations = reservations[

    reservations["month_date"] <= latest_known_month

].copy()

month_order = monthly_kpis["month_label"].dropna().tolist()

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

reservations_filtered = reservations[

    reservations["month_label"].isin(selected_months)

].copy()

if monthly_kpis_filtered.empty:

    st.warning("No data selected.")

    st.stop()

# =====================================================

# 1 KPI

# =====================================================

st.header("1. Monthly KPI Dashboard")

latest = monthly_kpis_filtered.dropna(subset=["sales"]).iloc[-1]

col1, col2, col3, col4, col5 = st.columns(5)

col1.metric("Sales", f"¥{latest['sales']:,.0f}")

col2.metric("Target", f"¥{latest['target']:,.0f}")

col3.metric("Achievement Rate", f"{latest['achievement_pct']:,.1f}%")

col4.metric("Occupancy Rate", f"{latest['occupancy_pct']:,.1f}%")

col5.metric("RevPAR", f"¥{latest['revpar']:,.0f}")

# =====================================================

# 2 SALES VS TARGET

# =====================================================

st.header("2. Sales vs Target Trend")

fig = go.Figure()

fig.add_trace(go.Scatter(

    x=monthly_kpis_filtered["month_label"],

    y=monthly_kpis_filtered["sales"],

    mode="lines+markers",

    name="Actual Sales",

    line=dict(color="blue")

))

fig.add_trace(go.Scatter(

    x=monthly_kpis_filtered["month_label"],

    y=monthly_kpis_filtered["target"],

    mode="lines+markers",

    name="Revenue Target",

    line=dict(color="orange")

))

fig.update_xaxes(

    type="category",

    categoryorder="array",

    categoryarray=month_order

)

fig.update_yaxes(tickprefix="¥")

fig.update_layout(

    title="Actual Sales vs Revenue Target",

    xaxis_title="Month",

    yaxis_title="JPY",

    hovermode="x unified"

)

st.plotly_chart(fig, width="stretch")

# =====================================================

# 3 OCCUPANCY / ADR / REVPAR

# =====================================================

st.header("3. Occupancy / ADR / RevPAR Evolution")

fig = make_subplots(specs=[[{"secondary_y": True}]])

fig.add_trace(go.Scatter(

    x=monthly_kpis_filtered["month_label"],

    y=monthly_kpis_filtered["occupancy_pct"],

    name="Occupancy %",

    mode="lines+markers",

    line=dict(color="blue")

), secondary_y=False)

fig.add_trace(go.Scatter(

    x=monthly_kpis_filtered["month_label"],

    y=monthly_kpis_filtered["adr"],

    name="ADR",

    mode="lines+markers",

    line=dict(color="green")

), secondary_y=True)

fig.add_trace(go.Scatter(

    x=monthly_kpis_filtered["month_label"],

    y=monthly_kpis_filtered["revpar"],

    name="RevPAR",

    mode="lines+markers",

    line=dict(color="red")

), secondary_y=True)

fig.update_xaxes(

    type="category",

    categoryorder="array",

    categoryarray=month_order

)

fig.update_yaxes(

    title_text="Occupancy %",

    range=[0, 100],

    ticksuffix="%",

    secondary_y=False

)

fig.update_yaxes(

    title_text="ADR / RevPAR (JPY)",

    tickprefix="¥",

    secondary_y=True

)

fig.update_layout(

    title="Occupancy vs ADR / RevPAR",

    hovermode="x unified"

)

st.plotly_chart(fig, width="stretch")

# =====================================================

# 4 OTA

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

        "channel": "Booking Channel"

    }

)

fig.update_yaxes(tickprefix="¥")

fig.update_layout(hovermode="x unified", legend_title_text="Booking Channel")

st.plotly_chart(fig, width="stretch")

st.subheader("OTA Revenue Summary")

ota_summary = (

    ota_sales_filtered

    .groupby("channel", as_index=False)

    .agg(

        sales=("sales", "sum"),

        booking_count=("booking_count", "sum")

    )

    .sort_values("sales", ascending=False)

)

ota_summary["share_pct"] = ota_summary["sales"] / ota_summary["sales"].sum() * 100

ota_summary["sales"] = ota_summary["sales"].round(0)

ota_summary["booking_count"] = ota_summary["booking_count"].round(0)

ota_summary["share_pct"] = ota_summary["share_pct"].round(1)

st.dataframe(ota_summary, width="stretch")

# =====================================================
# 5 COUNTRY / REGION
# =====================================================

st.header("5. Revenue by Client Country / Region")

country_summary = (
    reservations_filtered
    .groupby("country_region", as_index=False)
    .agg(
        revenue=("received_amount", "sum"),
        gross_revenue=("gross_booking_amount", "sum"),
        guest_nights=("guest_nights", "sum"),
        bookings=("booking_id", "count")
    )
    .sort_values("revenue", ascending=False)
)

country_summary["share_pct"] = (
    country_summary["revenue"] /
    country_summary["revenue"].sum() * 100
)

country_summary["share_pct"] = country_summary["share_pct"].round(1)

# Top 10 countries
top_countries = (
    country_summary
    .head(10)["country_region"]
    .tolist()
)

country_monthly = (
    reservations_filtered[
        reservations_filtered["country_region"].isin(top_countries)
    ]
    .groupby(
        ["month_label", "country_region"],
        as_index=False
    )
    .agg(
        revenue=("received_amount", "sum")
    )
)

# STACKED BAR CHART
fig = px.bar(
    country_monthly,
    x="month_label",
    y="revenue",
    color="country_region",
    title="Revenue Mix by Client Country / Region",
    category_orders={"month_label": month_order},
    labels={
        "month_label": "Month",
        "revenue": "Revenue (JPY)",
        "country_region": "Country / Region"
    }
)

fig.update_layout(
    barmode="stack",
    hovermode="x unified",
    legend_title_text="Country / Region"
)

fig.update_yaxes(tickprefix="¥")

st.plotly_chart(fig, width="stretch")

# COUNTRY TABLE

st.subheader("Country / Region Revenue Summary")

display_country = country_summary.copy()

display_country["revenue"] = (
    display_country["revenue"]
    .round(0)
)

display_country["gross_revenue"] = (
    display_country["gross_revenue"]
    .round(0)
)

display_country["guest_nights"] = (
    display_country["guest_nights"]
    .round(0)
)

display_country = display_country[
    [
        "country_region",
        "revenue",
        "share_pct",
        "guest_nights",
        "bookings"
    ]
]

display_country.columns = [
    "Country / Region",
    "Revenue",
    "Share %",
    "Guest Nights",
    "Bookings"
]

st.dataframe(
    display_country,
    width="stretch"
)

st.dataframe(display_country, width="stretch")

# =====================================================

# 6 CHANNEL DEPENDENCY

# =====================================================

st.header("6. Channel Dependency Risk")

month_totals = ota_sales_filtered.groupby("month_label")["sales"].transform("sum")

ota_sales_filtered["share"] = ota_sales_filtered["sales"] / month_totals

ota_sales_filtered["share"] = ota_sales_filtered["share"].fillna(0)

fig = px.area(

    ota_sales_filtered,

    x="month_label",

    y="share",

    color="channel",

    title="Revenue Share by Booking Channel",

    category_orders={"month_label": month_order},

    labels={

        "month_label": "Month",

        "share": "Revenue Share",

        "channel": "Booking Channel"

    }

)

fig.update_yaxes(tickformat=".0%")

fig.update_layout(hovermode="x unified", legend_title_text="Booking Channel")

st.plotly_chart(fig, width="stretch")

# =====================================================

# 7 TABLES

# =====================================================

st.header("7. Monthly KPI Table")

st.dataframe(monthly_kpis_filtered, width="stretch")

st.header("8. OTA Revenue Table")

st.dataframe(ota_sales_filtered, width="stretch")

st.header("9. Reservation Table")

st.dataframe(reservations_filtered, width="stretch")