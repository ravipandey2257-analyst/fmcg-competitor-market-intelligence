import sqlite3
from pathlib import Path
from datetime import date, timedelta
import pandas as pd
import plotly.express as px
import streamlit as st

DB_PATH = Path(__file__).with_name("fmcg_market.db")

st.set_page_config(page_title="FMCG Market Intelligence", page_icon="📊", layout="wide")

def connect():
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA foreign_keys = ON")
    return con

def init_db():
    with connect() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS brands (
            brand_id INTEGER PRIMARY KEY AUTOINCREMENT,
            brand_name TEXT NOT NULL,
            company_name TEXT,
            is_own_brand INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS products (
            product_id INTEGER PRIMARY KEY AUTOINCREMENT,
            brand_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            category TEXT NOT NULL,
            pack_size REAL NOT NULL,
            pack_unit TEXT NOT NULL,
            FOREIGN KEY (brand_id) REFERENCES brands(brand_id)
        );
        CREATE TABLE IF NOT EXISTS competitors (
            competitor_id INTEGER PRIMARY KEY AUTOINCREMENT,
            competitor_name TEXT NOT NULL,
            headquarters TEXT
        );
        CREATE TABLE IF NOT EXISTS market_observations (
            observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            competitor_id INTEGER,
            observation_date DATE NOT NULL,
            region TEXT NOT NULL,
            channel TEXT NOT NULL,
            selling_price REAL NOT NULL,
            mrp REAL NOT NULL,
            discount_percent REAL NOT NULL DEFAULT 0,
            promotion TEXT,
            estimated_sales_units INTEGER,
            market_share_percent REAL,
            source TEXT,
            FOREIGN KEY (product_id) REFERENCES products(product_id),
            FOREIGN KEY (competitor_id) REFERENCES competitors(competitor_id)
        );
        """)
        count = con.execute("SELECT COUNT(*) FROM market_observations").fetchone()[0]
        if count == 0:
            seed_demo_data(con)

def seed_demo_data(con):
    brands = [
        ("FreshGlow", "Your Company (Demo)", 1),
        ("BrightHome", "BrightHome Consumer Ltd. (Fictional)", 0),
        ("SparkleMax", "SparkleMax Products (Fictional)", 0),
        ("CleanNest", "CleanNest Industries (Fictional)", 0),
        ("PureDrop", "PureDrop Consumer Goods (Fictional)", 0),
    ]
    con.executemany("INSERT INTO brands(brand_name, company_name, is_own_brand) VALUES(?,?,?)", brands)
    brand_ids = {r[1]: r[0] for r in con.execute("SELECT brand_id, brand_name FROM brands")}
    competitors = [
        ("BrightHome Consumer Ltd.", "Mumbai"),
        ("SparkleMax Products", "Ahmedabad"),
        ("CleanNest Industries", "Pune"),
        ("PureDrop Consumer Goods", "Delhi"),
    ]
    con.executemany("INSERT INTO competitors(competitor_name, headquarters) VALUES(?,?)", competitors)
    comp_ids = {r[1]: r[0] for r in con.execute("SELECT competitor_id, competitor_name FROM competitors")}
    product_rows = [
        ("FreshGlow", "FreshGlow Detergent Powder", "Home Care", 1, "kg"),
        ("BrightHome", "BrightHome Detergent Powder", "Home Care", 1, "kg"),
        ("SparkleMax", "SparkleMax Detergent Powder", "Home Care", 1, "kg"),
        ("CleanNest", "CleanNest Detergent Powder", "Home Care", 1, "kg"),
        ("PureDrop", "PureDrop Detergent Powder", "Home Care", 1, "kg"),
        ("FreshGlow", "FreshGlow Dishwash Liquid", "Home Care", 500, "ml"),
        ("BrightHome", "BrightHome Dishwash Liquid", "Home Care", 500, "ml"),
        ("SparkleMax", "SparkleMax Dishwash Liquid", "Home Care", 500, "ml"),
    ]
    for b, name, cat, size, unit in product_rows:
        con.execute("INSERT INTO products(brand_id, product_name, category, pack_size, pack_unit) VALUES(?,?,?,?,?)",
                    (brand_ids[b], name, cat, size, unit))
    product_rows_db = con.execute("""
        SELECT p.product_id, p.product_name, b.brand_name, b.is_own_brand, b.company_name
        FROM products p JOIN brands b ON p.brand_id=b.brand_id
    """).fetchall()
    regions = ["West", "North", "South", "East"]
    channels = ["General Trade", "Modern Trade", "E-commerce"]
    price_base = {
        "FreshGlow": 120, "BrightHome": 126, "SparkleMax": 115,
        "CleanNest": 132, "PureDrop": 118
    }
    dish_base = {
        "FreshGlow": 95, "BrightHome": 99, "SparkleMax": 92
    }
    today = date.today()
    rows = []
    for month_offset in range(6, -1, -1):
        d = today.replace(day=1) - timedelta(days=month_offset * 30)
        for product_id, product_name, brand, own, company in product_rows_db:
            base = dish_base.get(brand, price_base.get(brand, 120)) if "Dishwash" in product_name else price_base[brand]
            for region_idx, region in enumerate(regions):
                for channel_idx, channel in enumerate(channels):
                    variation = 1 + (region_idx - 1.5) * 0.012 + channel_idx * 0.018
                    mrp = round(base * variation, 2)
                    discount = [0, 5, 10, 8, 0, 12, 5][(month_offset + region_idx + channel_idx) % 7]
                    selling = round(mrp * (1 - discount / 100), 2)
                    units = int((900 + (6-month_offset)*45 + region_idx*70 + channel_idx*35) *
                                (1.10 if own else 1.0) * (1 + (0.03 if brand == "BrightHome" else 0)))
                    share = round(100 * units / (units + 4200), 2)
                    comp_id = None if own else comp_ids.get({
                        "BrightHome": "BrightHome Consumer Ltd.",
                        "SparkleMax": "SparkleMax Products",
                        "CleanNest": "CleanNest Industries",
                        "PureDrop": "PureDrop Consumer Goods"
                    }.get(brand))
                    promo = "Festival Combo" if discount >= 10 else ("Price Off" if discount > 0 else "No promotion")
                    rows.append((product_id, comp_id, d.isoformat(), region, channel, selling, mrp,
                                 discount, promo, units, share, "Synthetic demo data"))
    con.executemany("""
        INSERT INTO market_observations
        (product_id, competitor_id, observation_date, region, channel, selling_price, mrp,
         discount_percent, promotion, estimated_sales_units, market_share_percent, source)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
    """, rows)

def load_data():
    with connect() as con:
        return pd.read_sql_query("""
            SELECT mo.*, p.product_name, p.category, p.pack_size, p.pack_unit,
                   b.brand_name, b.company_name, b.is_own_brand,
                   c.competitor_name
            FROM market_observations mo
            JOIN products p ON mo.product_id=p.product_id
            JOIN brands b ON p.brand_id=b.brand_id
            LEFT JOIN competitors c ON mo.competitor_id=c.competitor_id
        """, con, parse_dates=["observation_date"])

init_db()
df = load_data()

st.title("📊 FMCG Competitor & Market Intelligence")
st.caption("A demonstration decision-support app for an FMCG Marketing Team. Demo data is fictional.")

with st.sidebar:
    st.header("Filters")
    regions = ["All"] + sorted(df["region"].dropna().unique().tolist())
    selected_region = st.selectbox("Region", regions)
    categories = ["All"] + sorted(df["category"].dropna().unique().tolist())
    selected_category = st.selectbox("Category", categories)
    brands = ["All"] + sorted(df["brand_name"].dropna().unique().tolist())
    selected_brand = st.selectbox("Brand", brands)
    channels = ["All"] + sorted(df["channel"].dropna().unique().tolist())
    selected_channel = st.selectbox("Sales channel", channels)
    min_date = df["observation_date"].min().date()
    max_date = df["observation_date"].max().date()
    date_range = st.date_input("Observation date range", value=(min_date, max_date),
                               min_value=min_date, max_value=max_date)

filtered = df.copy()
if selected_region != "All":
    filtered = filtered[filtered.region == selected_region]
if selected_category != "All":
    filtered = filtered[filtered.category == selected_category]
if selected_brand != "All":
    filtered = filtered[filtered.brand_name == selected_brand]
if selected_channel != "All":
    filtered = filtered[filtered.channel == selected_channel]
if isinstance(date_range, tuple) and len(date_range) == 2:
    filtered = filtered[
        (filtered.observation_date.dt.date >= date_range[0]) &
        (filtered.observation_date.dt.date <= date_range[1])
    ]

if filtered.empty:
    st.warning("No records match these filters. Please change the selections.")
    st.stop()

own = filtered[filtered.is_own_brand == 1]
competitors_df = filtered[filtered.is_own_brand == 0]
avg_own_price = own.selling_price.mean() if not own.empty else 0
avg_comp_price = competitors_df.selling_price.mean() if not competitors_df.empty else 0
price_gap = avg_own_price - avg_comp_price
avg_discount = competitors_df.discount_percent.mean() if not competitors_df.empty else 0
avg_share = filtered.market_share_percent.mean()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Average own-brand price", f"₹{avg_own_price:,.2f}" if avg_own_price else "N/A")
c2.metric("Average competitor price", f"₹{avg_comp_price:,.2f}" if avg_comp_price else "N/A")
c3.metric("Own vs competitor price gap", f"₹{price_gap:,.2f}" if avg_own_price and avg_comp_price else "N/A")
c4.metric("Average observed discount", f"{avg_discount:.1f}%")

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Overview", "Price Intelligence", "Promotions", "Regional Analysis", "Data Explorer"
])

with tab1:
    st.subheader("Market overview")
    brand_summary = filtered.groupby("brand_name", as_index=False).agg(
        average_price=("selling_price", "mean"),
        estimated_units=("estimated_sales_units", "sum"),
        average_share=("market_share_percent", "mean")
    ).sort_values("estimated_units", ascending=False)
    col1, col2 = st.columns(2)
    with col1:
        fig = px.bar(brand_summary, x="brand_name", y="estimated_units",
                     title="Estimated units by brand", labels={"brand_name":"Brand", "estimated_units":"Estimated units"})
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        fig = px.bar(brand_summary, x="brand_name", y="average_price",
                     title="Average selling price by brand", labels={"brand_name":"Brand", "average_price":"Price (₹)"})
        st.plotly_chart(fig, use_container_width=True)
    st.dataframe(brand_summary.round(2), use_container_width=True, hide_index=True)

with tab2:
    st.subheader("Competitor price comparison")
    price_by_brand = filtered.groupby(["brand_name", "product_name"], as_index=False).selling_price.mean()
    fig = px.bar(price_by_brand, x="brand_name", y="selling_price", color="product_name",
                 barmode="group", title="Average selling price by brand and product",
                 labels={"brand_name":"Brand", "selling_price":"Selling price (₹)"})
    st.plotly_chart(fig, use_container_width=True)
    st.info("Compare products with the same category and pack size. For fair comparison, use price per kg or litre when pack sizes differ.")
    price_by_brand["price_per_pack_unit"] = price_by_brand["selling_price"]
    st.dataframe(price_by_brand.round(2), use_container_width=True, hide_index=True)

with tab3:
    st.subheader("Promotion and discount intelligence")
    promo_summary = competitors_df.groupby(["brand_name", "promotion"], as_index=False).agg(
        avg_discount=("discount_percent", "mean"),
        observations=("observation_id", "count")
    )
    if not promo_summary.empty:
        fig = px.bar(promo_summary, x="brand_name", y="avg_discount", color="promotion",
                     barmode="group", title="Average competitor discount by promotion")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(promo_summary.round(2), use_container_width=True, hide_index=True)
    else:
        st.info("No competitor records available for the selected filters.")

with tab4:
    st.subheader("Regional market intelligence")
    region_summary = filtered.groupby(["region", "brand_name"], as_index=False).agg(
        avg_price=("selling_price", "mean"),
        estimated_units=("estimated_sales_units", "sum"),
        avg_share=("market_share_percent", "mean")
    )
    fig = px.bar(region_summary, x="region", y="estimated_units", color="brand_name",
                 barmode="group", title="Estimated units by region and brand")
    st.plotly_chart(fig, use_container_width=True)
    fig2 = px.line(region_summary, x="region", y="avg_price", color="brand_name",
                   markers=True, title="Average price by region")
    st.plotly_chart(fig2, use_container_width=True)
    st.dataframe(region_summary.round(2), use_container_width=True, hide_index=True)

with tab5:
    st.subheader("Underlying market observations")
    st.dataframe(filtered.sort_values("observation_date", ascending=False),
                 use_container_width=True, hide_index=True)
    st.download_button("Download filtered data as CSV",
                       filtered.to_csv(index=False).encode("utf-8"),
                       file_name="fmcg_market_observations.csv", mime="text/csv")

st.divider()
st.subheader("Automated business observations")
if avg_own_price and avg_comp_price:
    if price_gap > 0:
        st.write(f"• Your brand's average selling price is ₹{price_gap:.2f} higher than the competitor average in the selected view. Validate pack-size equivalence and product positioning before changing price.")
    elif price_gap < 0:
        st.write(f"• Your brand's average selling price is ₹{abs(price_gap):.2f} lower than the competitor average. Assess whether this supports volume growth or unnecessarily reduces margin.")
    else:
        st.write("• Your brand's average selling price is at parity with the competitor average.")
if avg_discount:
    st.write(f"• Competitors are offering an average observed discount of {avg_discount:.1f}%. Review promotion frequency and incremental sales before matching discounts.")
st.caption("Important: Market share and estimated units in this demo are illustrative, not verified market measurements.")
