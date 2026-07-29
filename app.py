import streamlit as st
import pandas as pd
import yfinance as yf
# Import specific needed functions from psx to avoid namespace clutter
from psx import tickers as psx_tickers

# -----------------------------------------------------------------------------
# 1. PAGE CONFIGURATION & SETUP
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Multi-Market Dividend Screener",
    page_icon="📊",
    layout="wide"
)

# Custom CSS to improve table visibility
st.markdown("""
<style>
    [data-testid="stDataFrame"] {font-size: 0.9rem;}
</style>
""", unsafe_allow_html=True)

st.title("📊 Multi-Market Dividend Screener")
st.markdown("Filter active companies by dividend yield and analyze historical payout data across different markets.")

# -----------------------------------------------------------------------------
# 2. SIDEBAR & CONTROLS
# -----------------------------------------------------------------------------
st.sidebar.header("Screener Settings")

market_choice = st.sidebar.radio(
    "Select Market Context:",
    ["Pakistan Stock Exchange (PSX)", "Global Exchanges (US/Major)"]
)

st.sidebar.subheader("Filters")
min_yield = st.sidebar.slider(
    "Minimum Annual Dividend Yield (%)",
    min_value=0.0,
    max_value=30.0,
    value=8.0,
    step=0.5,
    help="Filter stocks that have a trailing annual dividend yield above this percentage."
)

st.sidebar.markdown("---")
st.sidebar.info(
    "**Note on Data:** PSX data is retrieved via Yahoo Finance using '.KA' suffix, "
    "based on ticker lists from the PSX data reader library."
)

# -----------------------------------------------------------------------------
# 3. DATA ACQUISITION FUNCTIONS
# -----------------------------------------------------------------------------
@st.cache_data(ttl=86400, show_spinner=False) # Cache ticker list for 24 hours
def get_psx_tickers_map():
    """
    Fetches live tickers from PSX via psx-data-reader and formats them 
    for yfinance compatibility (appending .KA).
    Returns a dictionary: {'TICKER.KA': 'Company Name'}
    """
    psx_dict = {}
    try:
        # psx.tickers() returns a pandas DataFrame
        tickers_df = psx_tickers()
        
        # Iterate through dataframe to build map
        for symbol, row in tickers_df.iterrows():
            # yfinance requires .KA suffix for PSX data
            yf_symbol = f"{symbol}.KA"
            # Use Name column if available, else use symbol as fallback name
            company_name = row.get('Name', symbol)
            psx_dict[yf_symbol] = company_name
            
        return psx_dict
        
    except Exception as e:
        st.error(f"Could not fetch latest PSX tickers: {e}")
        # Fallback list to ensure app functionality if PSX source is down
        return {
             "ENGRO.KA": "Engro Corporation",
             "FFC.KA": "Fauji Fertilizer Company",
             "HUBC.KA": "Hub Power Company",
             "MCB.KA": "MCB Bank Limited",
             "OGDC.KA": "Oil & Gas Development Company",
             "LUCK.KA": "Lucky Cement Limited"
        }

# Hardcoded list of major global dividend payers for the "Global" option
GLOBAL_TICKERS = {
    "T": "AT&T Inc.", "VZ": "Verizon Communications",
    "KO": "The Coca-Cola Company", "JNJ": "Johnson & Johnson",
    "PG": "Procter & Gamble", "XOM": "Exxon Mobil Corp",
    "CVX": "Chevron Corp", "PFE": "Pfizer Inc.",
    "ABBV": "AbbVie Inc.", "PEP": "PepsiCo, Inc."
}

# Determine which ticker set to use based on sidebar selection
if "Pakistan" in market_choice:
    ticker_map = get_psx_tickers_map()
    currency_symbol = "PKR"
    # LIMIT FOR PERFORMANCE: Scanning 500+ stocks takes time. 
    # Limiting to first 150 for reasonable load times in this blueprint.
    # Comment out next line for full market scan (will take several minutes).
    ticker_map = dict(list(ticker_map.items())[:150])
    st.toast(f"Loaded {len(ticker_map)} PSX tickers for screening.", icon="🇵🇰")
else:
    ticker_map = GLOBAL_TICKERS
    currency_symbol = "USD"
    st.toast(f"Loaded global major tickers for screening.", icon="🌎")

# -----------------------------------------------------------------------------
# 4. CORE SCREENER LOGIC
# -----------------------------------------------------------------------------
@st.cache_data(ttl=3600) # Cache screener results for 1 hour
def run_screener(symbol_dict):
    """Iterates through symbols, fetches real-time info, checks activity status."""
    results = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    total = len(symbol_dict)
    
    for i, (full_ticker, company_name) in enumerate(symbol_dict.items()):
        # Update progress UI
        progress_val = (i + 1) / total
        progress_bar.progress(progress_val)
        clean_symbol = full_ticker.replace(".KA", "")
        status_text.text(f"Scanning {i+1}/{total}: {clean_symbol}...")
        
        try:
            stock = yf.Ticker(full_ticker)
            
            # 1. Check Activity: Try to fetch 5 days of price history. 
            # If empty, Yahoo likely considers it inactive/delisted.
            history = stock.history(period="5d")
            
            if not history.empty:
                is_active = True
                status_icon = "🟢 Active"
                current_price = history["Close"].iloc[-1]
                
                # 2. Fetch Yield Data
                info = stock.info
                # trailingAnnualDividendYield can be None or 0
                raw_yield = info.get("trailingAnnualDividendYield")
                yield_pct = (raw_yield * 100) if raw_yield else 0.0
                
            else:
                is_active = False
                status_icon = "🔴 Inactive/No Data"
                current_price = 0.0
                yield_pct = 0.0

            results.append({
                "Symbol": clean_symbol,
                "yf_ticker": full_ticker, # Hidden column for subsequent queries
                "Company Name": company_name,
                "Status": status_icon,
                "Price": current_price,
                "Yield (%)": yield_pct,
                "is_active_bool": is_active # Hidden boolean for filtering
            })
            
        except Exception as e:
            # Handle individual ticker failures gracefully
            results.append({
                "Symbol": clean_symbol,
                "yf_ticker": full_ticker,
                "Company Name": company_name,
                "Status": "⚠️ Error",
                "Price": 0.0,
                "Yield (%)": 0.0,
                "is_active_bool": False
            })
            print(f"Error scanning {full_ticker}: {e}")

    # Cleanup UI elements
    progress_bar.empty()
    status_text.empty()
    
    return pd.DataFrame(results)

# Run the screener
with st.spinner("Fetching market data... This may take a minute depending on the number of stocks."):
    screener_df = run_screener(ticker_map)

# -----------------------------------------------------------------------------
# 5. UI: SCREENER RESULTS TABLE
# -----------------------------------------------------------------------------
# Filter results based on slider and activity status
filtered_df = screener_df[
    (screener_df["Yield (%)"] >= min_yield) & 
    (screener_df["is_active_bool"] == True)
].copy()

# Format columns for display
filtered_df["Price"] = filtered_df["Price"].map("{:,.2f}".format)
filtered_df["Yield (%)"] = filtered_df["Yield (%)"].map("{:.2f}%".format)

st.subheader(f"📋 Screening Results: Yield ≥ {min_yield}%")

if filtered_df.empty:
    st.warning(f"No active companies found matching a minimum yield of {min_yield}%. Try lowering the filter.")
else:
    # Define columns to display (hiding internal utility columns)
    display_cols = ["Symbol", "Company Name", "Status", "Price", "Yield (%)"]
    st.dataframe(
        filtered_df[display_cols],
        use_container_width=True,
        hide_index=True,
        height=400
    )

st.markdown("---")

# -----------------------------------------------------------------------------
# 6. UI: HISTORIC DIVIDEND LOG
# -----------------------------------------------------------------------------
st.subheader("📜 Historical Payout Analysis")

# Dropdown list populated only by the filtered results
stock_options = dict(zip(filtered_df["yf_ticker"], filtered_df["Symbol"] + " - " + filtered_df["Company Name"]))

if not stock_options:
     st.info("Adjust filters above to see stocks available for detailed analysis.")
else:
    selected_yf_ticker = st.selectbox(
        "Select a company from results above to view full history:",
        options=stock_options.keys(),
        format_func=lambda x: stock_options[x]
    )

    if selected_yf_ticker:
        st.markdown(f"#### Payout History for: **{stock_options[selected_yf_ticker]}**")
        
        stock_obj = yf.Ticker(selected_yf_ticker)
        
        # Fetch dividends series
        div_series = stock_obj.dividends
        
        if not div_series.empty:
            # Process into a clean dataframe
            div_df = pd.DataFrame(div_series).reset_index()
            div_df.columns = ["Date", f"Amount ({currency_symbol})"]
            
            # Remove timezone info for cleaner display dates
            div_df["Date"] = div_df["Date"].dt.date
            
            # Sort newest first
            div_df = div_df.sort_values(by="Date", ascending=False).reset_index(drop=True)
            
            # Layout: Chart on left, Data table on right
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.write("**Last 50 Payouts Trend**")
                # Use date as index for better chart labeling
                chart_data = div_df.head(50).set_index("Date").sort_index()
                st.bar_chart(chart_data, color="#00C805")
                
            with col2:
                st.write(f"**Complete Log ({len(div_df)} records)**")
                st.dataframe(
                    div_df, 
                    use_container_width=True, 
                    hide_index=True,
                    height=400
                )
        else:
            st.warning("No dividend history records found for this stock in the database.")