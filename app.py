import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from psx import tickers as psx_tickers

# -----------------------------------------------------------------------------
# 1. PAGE CONFIGURATION, STYLING & STATE MANAGEMENT
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Dividend Scout",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- SESSION STATE INITIALIZATION (The key to "Load More") ---
# Initialize the counter at 20 if it doesn't exist yet.
if 'display_count' not in st.session_state:
    st.session_state.display_count = 20

# Reset count if market changes to avoid trying to load index 100 of a 12-item list
if 'last_market' not in st.session_state:
    st.session_state.last_market = None

# Custom CSS
st.markdown("""
<style>
    .main .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    h1 { font-family: 'Helvetica Neue', sans-serif; font-weight: 700; color: #0E1117; }
    h2, h3 { font-family: 'Helvetica Neue', sans-serif; font-weight: 600; color: #262730; }
    .stDataFrame { font-size: 0.95rem; }
    /* Style for the Load More button container */
    .load-more-container { text-align: center; margin-top: 20px; margin-bottom: 40px;}
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. HEADER
# -----------------------------------------------------------------------------
st.title("📈 Dividend Scout")
st.caption("A professional screener for high-yield, actively trading dividend stocks.")

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
    
    # Reset display count if user switches markets
    if st.session_state.last_market != market_choice:
        st.session_state.display_count = 20
        st.session_state.last_market = market_choice

    st.divider()
    
    st.subheader("Filters")
    min_yield = st.slider(
        "Minimum Annual Yield (%)",
        min_value=0.0,
        max_value=25.0,
        value=5.0,
        step=0.5,
        format="%d%%",
        help="Filter stocks with a trailing annual dividend yield below this value."
    )

    st.divider()
    if "Pakistan" in market_choice:
        st.info("💡 **PSX Note:** Data is fetched via Yahoo Finance using '.KA' suffix. Yield data might be delayed or missing for some scrips.")

# -----------------------------------------------------------------------------
# 4. DATA ACQUISITION (Cached)
# -----------------------------------------------------------------------------
PSX_FALLBACK_TICKERS = {
    "FFC.KA": "Fauji Fertilizer Company", "EFERT.KA": "Engro Fertilizers",
    "ENGRO.KA": "Engro Corporation", "HUBC.KA": "Hub Power Company",
    "UBL.KA": "United Bank Limited", "MCB.KA": "MCB Bank Limited",
    "HBL.KA": "Habib Bank Limited", "MEBL.KA": "Meezan Bank Limited",
    "OGDC.KA": "Oil & Gas Development Co", "PPL.KA": "Pakistan Petroleum Ltd",
    "POL.KA": "Pakistan Oilfields Ltd", "MARI.KA": "Mari Petroleum Company",
    "LUCK.KA": "Lucky Cement Limited", "KOHC.KA": "Kohat Cement Company",
    "SYS.KA": "Systems Limited", "TRG.KA": "TRG Pakistan",
    "AVN.KA": "Avanceon Limited", "PSO.KA": "Pakistan State Oil",
    "SNGP.KA": "Sui Northern Gas Pipelines", "SSGC.KA": "Sui Southern Gas Corp",
    "KAPCO.KA": "Kot Addu Power Company", "NCPL.KA": "Nishat Chunian Power",
    "NPL.KA": "Nishat Power Limited", "PKGS.KA": "Packages Limited",
    "INDU.KA": "Indus Motor Company", "MTL.KA": "Millat Tractors Limited",
    "FATIMA.KA": "Fatima Fertilizer Company", "BAFL.KA": "Bank Alfalah Limited",
    "BAHL.KA": "Bank AL Habib Limited", "AKBL.KA": "Askari Bank Limited",
    "FABL.KA": "Faysal Bank Limited", "BOP.KA": "The Bank of Punjab",
    "KEL.KA": "K-Electric Limited", "PAEL.KA": "Pak Elektron Limited",
    "PIOC.KA": "Pioneer Cement", "CHCC.KA": "Cherat Cement",
    "MLCF.KA": "Maple Leaf Cement", "FCCL.KA": "Fauji Cement Company"
}

@st.cache_data(ttl=86400, show_spinner=False)
def get_psx_tickers_map():
    psx_dict = {}
    data_source = "live"
    try:
        tickers_df = psx_tickers()
        if tickers_df.empty: raise ValueError("Empty ticker list returned")
             
        for symbol, row in tickers_df.iterrows():
            yf_symbol = f"{symbol}.KA"
            company_name = str(row.get('Name', symbol)).strip()
            psx_dict[yf_symbol] = company_name
            
        if len(psx_dict) < 50:
             psx_dict.update(PSX_FALLBACK_TICKERS)
             data_source = "hybrid"
    except Exception as e:
        psx_dict = PSX_FALLBACK_TICKERS
        data_source = "fallback"
        print(f"PSX Data Error: {e}. Using fallback list.")
    return psx_dict, data_source

GLOBAL_TICKERS = {
    "T": "AT&T Inc.", "VZ": "Verizon Communications", "KO": "The Coca-Cola Company", 
    "JNJ": "Johnson & Johnson", "PG": "Procter & Gamble", "XOM": "Exxon Mobil Corp",
    "CVX": "Chevron Corp", "PFE": "Pfizer Inc.", "ABBV": "AbbVie Inc.", 
    "PEP": "PepsiCo, Inc.", "MO": "Altria Group", "PM": "Philip Morris International",
    "O": "Realty Income Corp", "MAIN": "Main Street Capital", "IRM": "Iron Mountain"
}

# --- MARKET CONTEXT SETUP & SLICING ---
if "Pakistan" in market_choice:
    full_ticker_map, source_status = get_psx_tickers_map()
    currency_symbol = "PKR"
    market_name = "PSX"
    if source_status == "fallback": st.toast("Using curated PSX list due to API issues.", icon="ℹ️")
    elif source_status == "hybrid": st.toast("Using mixed live/curated PSX list.", icon="ℹ️")
else:
    full_ticker_map = GLOBAL_TICKERS
    currency_symbol = "USD"
    market_name = "US Market"

# Convert full map to list items for slicing
all_ticker_items = list(full_ticker_map.items())
total_tickers_available = len(all_ticker_items)

# Slice the list based on the current session state count
current_batch_items = all_ticker_items[:st.session_state.display_count]
# Convert back to dict for the screener function
current_ticker_map = dict(current_batch_items)

# -----------------------------------------------------------------------------
# 5. CORE SCREENER ENGINE (Cached based on batch size)
# -----------------------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def run_screener(symbol_dict, market_context):
    results = []
    total_in_batch = len(symbol_dict)
    
    # Use a spinner instead of status container for smoother "load more" updates
    with st.spinner(f"Fetching data for {total_in_batch} companies from Yahoo Finance..."):
        for i, (full_ticker, company_name) in enumerate(symbol_dict.items()):
            try:
                stock = yf.Ticker(full_ticker)
                history = stock.history(period="5d")
                
                if not history.empty:
                    is_active = True
                    current_price = history["Close"].iloc[-1]
                    info = stock.info
                    raw_yield = info.get("trailingAnnualDividendYield")
                    yield_decimal = raw_yield if raw_yield is not None else 0.0
                else:
                    is_active = False
                    current_price = 0.0
                    yield_decimal = 0.0

                results.append({
                    "Symbol": full_ticker.replace(".KA", ""),
                    "yf_ticker": full_ticker,
                    "Company Name": company_name,
                    "Price": current_price,
                    "Yield Decimal": yield_decimal, 
                    "is_active": is_active
                })
            except Exception:
                pass
            
    return pd.DataFrame(results)

# Execute Screener on current batch
screener_df = run_screener(current_ticker_map, market_name)

# -----------------------------------------------------------------------------
# 6. RESULTS DASHBOARD & LOAD MORE BUTTON
# -----------------------------------------------------------------------------
filtered_df = screener_df[
    (screener_df["Yield Decimal"] * 100 >= min_yield) & 
    (screener_df["is_active"] == True)
].copy()

st.divider()
st.header(f"🎯 Screening Results")
# Show how many we have scanned out of the total available
st.caption(f"Scanned {len(screener_df)} of {total_tickers_available} potential tickers in {market_name}. Showing results with yield ≥ {min_yield}%")

if filtered_df.empty:
    st.warning(f"No active companies in the current batch of {len(screener_df)} scanned stocks match your criteria. Try lowering the filter or clicking 'Load More'.")
else:
    # Main Results Table
    st.dataframe(
        filtered_df,
        column_order=("Symbol", "Company Name", "Price", "Yield Decimal"),
        hide_index=True,
        use_container_width=True,
        height=400,
        column_config={
            "Symbol": st.column_config.TextColumn("Ticker", help="Stock Symbol"),
            "Company Name": st.column_config.TextColumn("Company", width="medium"),
            "Price": st.column_config.NumberColumn("Current Price", format=f"{currency_symbol} %.2f"),
            "Yield Decimal": st.column_config.ProgressColumn(
                "Annual Yield",
                format="%.2f%%",
                min_value=0,
                max_value=max(filtered_df["Yield Decimal"].max(), 0.15), 
                help="Trailing Annual Dividend Yield reported by Yahoo Finance"
            ),
        }
    )

# --- LOAD MORE BUTTON LOGIC ---
st.markdown("<div class='load-more-container'>", unsafe_allow_html=True)

# Only show button if we haven't displayed everything yet
if st.session_state.display_count < total_tickers_available:
    remaining = total_tickers_available - st.session_state.display_count
    next_batch_size = min(20, remaining) # Load 20, or whatever is left
    
    if st.button(f"🔄 Load {next_batch_size} More Results", type="primary", use_container_width=True):
        # Increment session state count
        st.session_state.display_count += 20
        # Rerun script immediately to fetch new batch
        st.rerun()
else:
    if total_tickers_available > 0:
        st.info("✅ All available tickers for this market have been scanned.")

st.markdown("</div>", unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# 7. HISTORICAL PAYOUT DEEP DIVE
# -----------------------------------------------------------------------------
st.divider()
st.header("📜 Historical Payout Deep Dive")

# Ensure strings before concatenation
filtered_df["Symbol"] = filtered_df["Symbol"].astype(str)
filtered_df["Company Name"] = filtered_df["Company Name"].astype(str)

stock_options = dict(zip(filtered_df["yf_ticker"], filtered_df["Symbol"] + " - " + filtered_df["Company Name"]))

if not stock_options:
     st.info("👆 Found stocks will appear in the dropdown here for analysis.")
else:
    selected_yf_ticker = st.selectbox(
        "Select Company to Analyze:",
        options=stock_options.keys(),
        format_func=lambda x: stock_options[x],
        index=None,
        placeholder="Choose a stock from results above..."
    )

    if selected_yf_ticker:
        stock_obj = yf.Ticker(selected_yf_ticker)
        
        with st.container():
            info = stock_obj.info
            current_price = info.get('currentPrice', info.get('previousClose', 0))
            raw_trailing_yield = info.get('trailingAnnualDividendYield')
            trailing_yield = (raw_trailing_yield * 100) if raw_trailing_yield is not None else 0.0
            
            st.subheader(stock_options[selected_yf_ticker])
            mcol1, mcol2 = st.columns(2)
            mcol1.metric("Current Price", f"{currency_symbol} {current_price:,.2f}")
            mcol2.metric("Reported Trailing Yield", f"{trailing_yield:.2f}%")

        div_series = stock_obj.dividends
        if not div_series.empty:
            div_df = pd.DataFrame(div_series).reset_index()
            div_df.columns = ["Date", "Amount"]
            div_df["Date"] = pd.to_datetime(div_df["Date"]).dt.date
            div_df = div_df.sort_values(by="Date", ascending=False).reset_index(drop=True)
            
            tab1, tab2 = st.tabs(["📊 Payout Chart", "📄 Complete Data Log"])
            with tab1:
                fig = px.bar(
                    div_df.head(60),
                    x="Date", y="Amount",
                    labels={"Date": "Payout Date", "Amount": f"Dividend ({currency_symbol})"},
                    color_discrete_sequence=["#00C805"],
                )
                fig.update_layout(hovermode="x unified", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", height=350)
                st.plotly_chart(fig, use_container_width=True)
            with tab2:
                st.dataframe(
                    div_df, use_container_width=True, hide_index=True, height=400,
                    column_config={"Date": st.column_config.DateColumn("Payout Date", format="YYYY-MM-DD"), "Amount": st.column_config.NumberColumn(f"Amount ({currency_symbol})", format="%.2f")}
                )
        else:
            st.warning("No historical dividend records found for this stock.")