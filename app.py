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

# Custom CSS for a cleaner look
st.markdown("""
<style>
    .main .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    h1 { font-family: 'Helvetica Neue', sans-serif; font-weight: 700; color: #0E1117; }
    h2, h3 { font-family: 'Helvetica Neue', sans-serif; font-weight: 600; color: #262730; }
    .stDataFrame { font-size: 0.95rem; }
    [data-testid="stMetric"] {
        background-color: #f8f9fa;
        border-radius: 0.5rem;
        padding: 1rem;
        border: 1px solid #e9ecef;
    }
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

    st.divider()
    
    st.subheader("Filters")
    # Lowered default to 5% to ensure results appear immediately
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
        st.info("💡 **PSX Note:** Data is fetched via Yahoo Finance using '.KA' suffix. Yield data may be delayed for some scrips.")

# -----------------------------------------------------------------------------
# 4. DATA ACQUISITION (Cached)
# -----------------------------------------------------------------------------
# Robust fallback list of known high-dividend PSX stocks to ensure results
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
    "FABL.KA": "Faysal Bank Limited", "BOP.KA": "The Bank of Punjab"
}

@st.cache_data(ttl=86400, show_spinner=False)
def get_psx_tickers_map():
    psx_dict = {}
    data_source = "live"
    try:
        # Try fetching live list first
        tickers_df = psx_tickers()
        if tickers_df.empty:
             raise ValueError("Empty ticker list returned from API")
             
        for symbol, row in tickers_df.iterrows():
            yf_symbol = f"{symbol}.KA"
            company_name = str(row.get('Name', symbol)).strip()
            psx_dict[yf_symbol] = company_name
            
        # If live fetch yielded too few results, merge with fallback
        if len(psx_dict) < 50:
             psx_dict.update(PSX_FALLBACK_TICKERS)
             data_source = "hybrid"
             
    except Exception as e:
        # On any error, use the robust fallback list
        psx_dict = PSX_FALLBACK_TICKERS
        data_source = "fallback"
        print(f"PSX Data Error: {e}. Using fallback list.")
        
    return psx_dict, data_source

GLOBAL_TICKERS = {
    "T": "AT&T Inc.", "VZ": "Verizon Communications", "KO": "The Coca-Cola Company", 
    "JNJ": "Johnson & Johnson", "PG": "Procter & Gamble", "XOM": "Exxon Mobil Corp",
    "CVX": "Chevron Corp", "PFE": "Pfizer Inc.", "ABBV": "AbbVie Inc.", 
    "PEP": "PepsiCo, Inc.", "MO": "Altria Group", "PM": "Philip Morris International"
}

# Market Context Setup
if "Pakistan" in market_choice:
    ticker_map, source_status = get_psx_tickers_map()
    currency_symbol = "PKR"
    market_name = "PSX"
    
    if source_status == "fallback":
         st.toast("Using curated list of top PSX dividend stocks due to API connectivity issues.", icon="ℹ️")
    elif source_status == "hybrid":
         st.toast("Using hybrid list of live and curated PSX stocks.", icon="ℹ️")

    # Performance limit for demo - keep it brisk
    ticker_map = dict(list(ticker_map.items())[:100])
else:
    ticker_map = GLOBAL_TICKERS
    currency_symbol = "USD"
    market_name = "US Market"

# -----------------------------------------------------------------------------
# 5. CORE SCREENER ENGINE (Cached)
# -----------------------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def run_screener(symbol_dict, market_context):
    results = []
    total = len(symbol_dict)
    
    with st.status(f"Scanning {total} tickers on {market_context}...", expanded=True) as status:
        for i, (full_ticker, company_name) in enumerate(symbol_dict.items()):
            clean_symbol = full_ticker.replace(".KA", "")
            if i % 5 == 0 or i == total - 1:
                 status.update(label=f"Scanning {market_context}: Analyzing {clean_symbol} ({i+1}/{total})...")
            
            try:
                stock = yf.Ticker(full_ticker)
                # Check activity via 5d history to ensure it's not delisted
                history = stock.history(period="5d")
                
                if not history.empty:
                    is_active = True
                    current_price = history["Close"].iloc[-1]
                    info = stock.info
                    
                    # --- YIELD FETCHING LOGIC ---
                    # Yahoo often returns None for PSX yields.
                    raw_yield = info.get("trailingAnnualDividendYield")
                    
                    if raw_yield is not None:
                        yield_decimal = raw_yield
                    else:
                        # If Yahoo data is missing, assume 0 for now to avoid crashing.
                        # (In a full prod app, we would calculate TTM yield manually here)
                        yield_decimal = 0.0
                        
                else:
                    is_active = False
                    current_price = 0.0
                    yield_decimal = 0.0

                results.append({
                    "Symbol": clean_symbol,
                    "yf_ticker": full_ticker,
                    "Company Name": company_name,
                    "Price": current_price,
                    # Store as decimal (e.g., 0.12 for 12%) for easier filtering later
                    "Yield Decimal": yield_decimal, 
                    "is_active": is_active
                })
            except Exception:
                pass # Skip problematic tickers silently
        
        status.update(label=f"Scan complete. Found data for {len(results)} companies.", state="complete", expanded=False)
            
    return pd.DataFrame(results)

# Execute Screener
screener_df = run_screener(ticker_map, market_name)

# -----------------------------------------------------------------------------
# 6. RESULTS DASHBOARD
# -----------------------------------------------------------------------------
# Filter Results: Convert decimal yield to percentage for comparison against slider
filtered_df = screener_df[
    (screener_df["Yield Decimal"] * 100 >= min_yield) & 
    (screener_df["is_active"] == True)
].copy()

st.divider()
st.header(f"🎯 Screening Results")
st.caption(f"Showing active companies in {market_name} with reported yield ≥ {min_yield}%")

if filtered_df.empty:
    st.warning(f"No active companies found with a reported yield of {min_yield}% or higher. Yahoo Finance may be missing yield data for these specific tickers right now. Try lowering the filter.")
else:
    # Summary Metrics
    col1, col2, col3 = st.columns(3)
    col1.metric("Matches Found", f"{len(filtered_df)}")
    avg_yield = filtered_df['Yield Decimal'].mean() * 100
    max_yield = filtered_df['Yield Decimal'].max() * 100
    col2.metric("Average Yield (Matches)", f"{avg_yield:.2f}%")
    col3.metric("Highest Yield Found", f"{max_yield:.2f}%")
    
    st.markdown("###") #Spacer

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
            "Price": st.column_config.NumberColumn(
                "Current Price",
                format=f"{currency_symbol} %.2f",
            ),
            # Display the decimal column as a percentage progress bar
            "Yield Decimal": st.column_config.ProgressColumn(
                "Annual Yield",
                format="%.2f%%",
                min_value=0,
                # Dynamic max for progress bar scaling
                max_value=max(filtered_df["Yield Decimal"].max(), 0.15), 
                help="Trailing Annual Dividend Yield reported by Yahoo Finance"
            ),
        }
    )

# -----------------------------------------------------------------------------
# 7. HISTORICAL PAYOUT DEEP DIVE
# -----------------------------------------------------------------------------
st.divider()
st.header("📜 Historical Payout Deep Dive")
st.caption("Select a company from the filtered results above to analyze its dividend consistency.")

# Ensure columns are string type before concatenation to prevent TypeErrors
filtered_df["Symbol"] = filtered_df["Symbol"].astype(str)
filtered_df["Company Name"] = filtered_df["Company Name"].astype(str)

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
        stock_obj = yf.Ticker(selected_yf_ticker)
        
        with st.container():
            # Fetch info for banner metrics based on selection
            info = stock_obj.info
            current_price = info.get('currentPrice', info.get('previousClose', 0))
            # Handle cases where yield is missing in info block
            raw_trailing_yield = info.get('trailingAnnualDividendYield')
            trailing_yield = (raw_trailing_yield * 100) if raw_trailing_yield is not None else 0.0
            
            st.subheader(stock_options[selected_yf_ticker])
            mcol1, mcol2 = st.columns(2)
            mcol1.metric("Current Price", f"{currency_symbol} {current_price:,.2f}")
            mcol2.metric("Reported Trailing Yield", f"{trailing_yield:.2f}%")

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
                st.caption("Visualizing payouts. Hover over bars for details.")
                # Plotly Express Chart
                fig = px.bar(
                    div_df.head(60), # Show last ~15 years of quarterly payouts
                    x="Date", 
                    y="Amount",
                    labels={"Date": "Payout Date", "Amount": f"Dividend ({currency_symbol})"},
                    color_discrete_sequence=["#00C805"], # Green color scheme
                )
                fig.update_layout(
                    xaxis_title=None,
                    yaxis_title=None,
                    hovermode="x unified",
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    margin=dict(l=20, r=20, t=20, b=20),
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