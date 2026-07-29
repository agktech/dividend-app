import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from psx import tickers as psx_tickers

# -----------------------------------------------------------------------------
# 1. PAGE CONFIGURATION & STYLING
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Dividend Scout",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for a cleaner, more minimal look
st.markdown("""
<style>
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    h1 {
        font-family: 'Helvetica Neue', sans-serif;
        font-weight: 700;
        color: #0E1117;
    }
    h2, h3 {
        font-family: 'Helvetica Neue', sans-serif;
        font-weight: 600;
        color: #262730;
    }
    .stDataFrame { font-size: 0.95rem; }
    /* Subtle border for metric containers */
    [data-testid="stMetric"] {
        background-color: #f8f9fa;
        border-radius: 0.5rem;
        padding: 1rem;
        border: 1px solid #e9ecef;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. HEADER & INSTRUCTIONS
# -----------------------------------------------------------------------------
st.title("📈 Dividend Scout")
st.caption("A professional screener for high-yield, actively trading dividend stocks across global markets.")

with st.expander("ℹ️ Quick Guide: How to use this tool", expanded=False):
    st.markdown("""
    1.  **Select Market:** Choose between the Pakistan Stock Exchange (PSX) or Major US indices via the sidebar.
    2.  **Set Minimum Yield:** Adjust the slider in the sidebar to filter out stocks below your desired annual dividend percentage.
    3.  **View Results:** The main table shows active companies matching your criteria.
    4.  **Deep Dive:** Select a specific company from the dropdown below the results table to visualize its complete payout history.
    """)

# -----------------------------------------------------------------------------
# 3. SIDEBAR CONTROLS
# -----------------------------------------------------------------------------
with st.sidebar:
    st.header("🔍 Screener Settings")
    
    market_choice = st.radio(
        "Select Market Context:",
        ["🇵🇰 Pakistan (PSX)", "🌎 Global (US Major)"],
        index=0
    )

    st.divider()
    
    st.subheader("Filters")
    min_yield = st.slider(
        "Minimum Annual Yield (%)",
        min_value=0.0,
        max_value=25.0,
        value=8.0,
        step=0.5,
        format="%d%%",
        help="Filter stocks with a trailing annual dividend yield below this value."
    )

    st.divider()
    
    if "Pakistan" in market_choice:
        st.info("💡 **PSX Data Note:** Tickers are fetched live via `psx-data-reader` and appended with `.KA` for Yahoo Finance retrieval.")
    else:
        st.info("💡 **Global Data Note:** Scanning major US large-cap dividend payers.")

# -----------------------------------------------------------------------------
# 4. DATA ACQUISITION (Cached)
# -----------------------------------------------------------------------------
@st.cache_data(ttl=86400, show_spinner=False)
def get_psx_tickers_map():
    psx_dict = {}
    try:
        tickers_df = psx_tickers()
        for symbol, row in tickers_df.iterrows():
            yf_symbol = f"{symbol}.KA"
            # Clean company name, remove extra spaces
            company_name = str(row.get('Name', symbol)).strip()
            psx_dict[yf_symbol] = company_name
        return psx_dict
    except Exception as e:
        st.error(f"Could not fetch PSX source data. Using limited fallback list. Error: {e}")
        return {
             "ENGRO.KA": "Engro Corporation", "FFC.KA": "Fauji Fertilizer Company",
             "HUBC.KA": "Hub Power Company", "MCB.KA": "MCB Bank Limited",
             "OGDC.KA": "Oil & Gas Development Company", "LUCK.KA": "Lucky Cement"
        }

GLOBAL_TICKERS = {
    "T": "AT&T Inc.", "VZ": "Verizon Communications", "KO": "The Coca-Cola Company", 
    "JNJ": "Johnson & Johnson", "PG": "Procter & Gamble", "XOM": "Exxon Mobil Corp",
    "CVX": "Chevron Corp", "PFE": "Pfizer Inc.", "ABBV": "AbbVie Inc.", 
    "PEP": "PepsiCo, Inc.", "MO": "Altria Group", "PM": "Philip Morris International"
}

# Market Context Setup
if "Pakistan" in market_choice:
    ticker_map = get_psx_tickers_map()
    currency_symbol = "PKR"
    market_name = "PSX"
    # Performance limit for demo - remove in full production if server handles it
    ticker_map = dict(list(ticker_map.items())[:150])
else:
    ticker_map = GLOBAL_TICKERS
    currency_symbol = "USD"
    market_name = "US Market"

# -----------------------------------------------------------------------------
# 5. CORE SCREENER ENGINE (Cached)
# -----------------------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def run_screener(symbol_dict):
    results = []
    total = len(symbol_dict)
    
    # Use st.status for a cleaner loading experience
    with st.status(f"Scanning {total} tickers on {market_name}...", expanded=True) as status:
        for i, (full_ticker, company_name) in enumerate(symbol_dict.items()):
            clean_symbol = full_ticker.replace(".KA", "")
            if i % 5 == 0 or i == total - 1:
                 status.update(label=f"Scanning {market_name}: Analyzing {clean_symbol} ({i+1}/{total})...")
            
            try:
                stock = yf.Ticker(full_ticker)
                # Check activity via 5d history
                history = stock.history(period="5d")
                
                if not history.empty:
                    is_active = True
                    current_price = history["Close"].iloc[-1]
                    info = stock.info
                    raw_yield = info.get("trailingAnnualDividendYield")
                    yield_pct = (raw_yield * 100) if raw_yield else 0.0
                else:
                    is_active = False
                    current_price = 0.0
                    yield_pct = 0.0

                results.append({
                    "Symbol": clean_symbol,
                    "yf_ticker": full_ticker,
                    "Company Name": company_name,
                    "Price": current_price,
                    "Yield (%)": yield_pct / 100, # Keep as decimal for formatting later
                    "is_active": is_active
                })
            except Exception:
                pass # Skip problematic tickers silently
        
        status.update(label="Market scan complete!", state="complete", expanded=False)
            
    return pd.DataFrame(results)

# Execute Screener
screener_df = run_screener(ticker_map)

# -----------------------------------------------------------------------------
# 6. RESULTS DASHBOARD
# -----------------------------------------------------------------------------
# Filter Results
filtered_df = screener_df[
    (screener_df["Yield (%)"] * 100 >= min_yield) & 
    (screener_df["is_active"] == True)
].copy()

st.divider()
st.header(f"🎯 Screening Results")
st.caption(f"Showing active companies in {market_name} with yield ≥ {min_yield}%")

if filtered_df.empty:
    st.warning(f"No active companies currently match a yield of {min_yield}% or higher. Try lowering the filter in the sidebar.")
else:
    # Summary Metrics
    col1, col2, col3 = st.columns(3)
    col1.metric("Matches Found", f"{len(filtered_df)}")
    col2.metric("Average Yield (Matches)", f"{(filtered_df['Yield (%)'].mean() * 100):.2f}%")
    col3.metric("Highest Yield Found", f"{(filtered_df['Yield (%)'].max() * 100):.2f}%")
    
    st.markdown("###") #Spacer

    # Main Results Table with enhanced formatting
    st.dataframe(
        filtered_df,
        column_order=("Symbol", "Company Name", "Price", "Yield (%)"),
        hide_index=True,
        use_container_width=True,
        height=400,
        column_config={
            "Symbol": st.column_config.TextColumn("Ticker", help="Stock Symbol"),
            "Company Name": st.column_config.TextColumn("Company", width="medium"),
            "Price": st.column_config.NumberColumn(
                "Current Price",
                format=f"{currency_symbol} %.2f",
            ),
            "Yield (%)": st.column_config.ProgressColumn(
                "Annual Yield",
                format="%.2f%%",
                min_value=0,
                max_value=max(filtered_df["Yield (%)"].max(), 0.15), # Scale progress bar dynamically
                help="Trailing Annual Dividend Yield"
            ),
        }
    )

# -----------------------------------------------------------------------------
# 7. HISTORICAL PAYOUT DEEP DIVE
# -----------------------------------------------------------------------------
st.divider()
st.header("📜 Historical Payout Deep Dive")
st.caption("Select a company from the filtered results above to analyze its dividend consistency.")

# --- THE FIX FOR THE CRASH IS HERE ---
# Ensure columns are treated as strings before concatenation to avoid TypeErrors
filtered_df["Symbol"] = filtered_df["Symbol"].astype(str)
filtered_df["Company Name"] = filtered_df["Company Name"].astype(str)

# Create dropdown options
stock_options = dict(zip(filtered_df["yf_ticker"], filtered_df["Symbol"] + " - " + filtered_df["Company Name"]))

if not stock_options:
     st.info("👆 Adjust your filters above to find stocks for detailed analysis.")
else:
    selected_yf_ticker = st.selectbox(
        "Select Company to Analyze:",
        options=stock_options.keys(),
        format_func=lambda x: stock_options[x],
        index=None,
        placeholder="Choose a stock..."
    )

    if selected_yf_ticker:
        # Get data for selected stock
        stock_obj = yf.Ticker(selected_yf_ticker)
        
        # Use containers for a structured layout
        with st.container():
            # Fetch info for banner metrics
            info = stock_obj.info
            current_price = info.get('currentPrice', info.get('previousClose', 0))
            trailing_yield = info.get('trailingAnnualDividendYield', 0) * 100
            
            st.subheader(stock_options[selected_yf_ticker])
            mcol1, mcol2 = st.columns(2)
            mcol1.metric("Current Price", f"{currency_symbol} {current_price:,.2f}")
            mcol2.metric("Trailing Yield", f"{trailing_yield:.2f}%")

        # Fetch dividend history
        div_series = stock_obj.dividends
        
        if not div_series.empty:
            # Process Data
            div_df = pd.DataFrame(div_series).reset_index()
            div_df.columns = ["Date", "Amount"]
            div_df["Date"] = pd.to_datetime(div_df["Date"]).dt.date
            div_df = div_df.sort_values(by="Date", ascending=False).reset_index(drop=True)
            
            tab1, tab2 = st.tabs(["📊 Payout Chart", "📄 Complete Data Log"])
            
            with tab1:
                st.caption("Visualizing the last 50 payouts. Hover over bars for details.")
                # Use Plotly Express for a more beautiful, interactive chart
                fig = px.bar(
                    div_df.head(50), 
                    x="Date", 
                    y="Amount",
                    labels={"Date": "Payout Date", "Amount": f"Dividend ({currency_symbol})"},
                    title="Recent Payout History",
                    color_discrete_sequence=["#00C805"], # Green color scheme
                )
                fig.update_layout(
                    xaxis_title=None,
                    yaxis_title=None,
                    hovermode="x unified",
                    plot_bgcolor="rgba(0,0,0,0)", # Transparent background
                    paper_bgcolor="rgba(0,0,0,0)",
                    margin=dict(l=20, r=20, t=40, b=20),
                    height=350
                )
                st.plotly_chart(fig, use_container_width=True)
                
            with tab2:
                st.dataframe(
                    div_df, 
                    use_container_width=True, 
                    hide_index=True,
                    height=400,
                    column_config={
                        "Date": st.column_config.DateColumn("Payout Date", format="YYYY-MM-DD"),
                        "Amount": st.column_config.NumberColumn(f"Amount ({currency_symbol})", format="%.2f")
                    }
                )
        else:
            st.warning("No historical dividend records found for this specific stock in the database.")