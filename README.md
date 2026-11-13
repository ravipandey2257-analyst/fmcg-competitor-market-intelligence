# FMCG Competitor & Market Intelligence App

## Run
1. Extract the ZIP.
2. Open a terminal in this folder.
3. Run `pip install -r requirements.txt`
4. Run `streamlit run app.py`

The app uses the included `fmcg_market.db`. If the database is absent or empty, the app initializes the schema and inserts demo records.

## Database tables
- `brands`
- `products`
- `competitors`
- `market_observations`

All preloaded brands, company names, prices, discounts, sales estimates and market-share values are fictional illustrative data. Replace them with verified company data before making business decisions.
