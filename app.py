import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import requests
from datetime import datetime
import pytz
import warnings
import io

# Suppress yfinance timezone warnings
warnings.filterwarnings("ignore", category=FutureWarning)

# -----------------------------------------------------------------------------
# 1. PAGE CONFIGURATION & STYLING
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Dividend Scout Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }
    h1, h2, h3 { font-family: 'Helvetica Neue', sans-serif; color: #1E1E1E; }
    .stDataFrame { font-size: 0.95rem; }
    [data-testid="stMetric"] {
        background-color: #f8f9fa;
        border-radius: 0.5rem;
        padding: 1rem;
        border: 1px solid #e9ecef;
    }
    .time-header {
        font-size: 1.05rem;
        font-weight: 600;
        color: #555555;
        background-color: #f1f3f5;
        padding: 8px 15px;
        border-radius: 8px;
        display: inline-block;
        margin-bottom: 15px;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. HELPER FUNCTIONS (Time & Excel Export)
# -----------------------------------------------------------------------------
def get_current_pkt_time():
    """Returns formatted current time in Pakistan Standard Time (PKT)."""
    tz = pytz.timezone('Asia/Karachi')
    return datetime.now(tz).strftime('%A, %B %d, %Y | %I:%M:%S %p PKT')

def convert_df_to_excel(df):
    """Converts a pandas dataframe to an Excel file in memory."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Data')
    return output.getvalue()

# -----------------------------------------------------------------------------
# 3. HEADER & LIVE CLOCK
# -----------------------------------------------------------------------------
st.title("📈 Dividend Scout Pro")
st.markdown(f"<div class='time-header'>🕒 {get_current_pkt_time()}</div>", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 4. SIDEBAR & STATE MANAGEMENT
# -----------------------------------------------------------------------------
if 'last_market' not in st.session_state:
    st.session_state.last_market = None

with st.sidebar:
    st.header("🔍 Screener Settings")
    market_choice = st.radio("Select Market:", ["🇵🇰 Pakistan (PSX)", "🌎 Global (US Major)"], index=0)

    st.divider()
    min_yield = st.slider("Minimum Annual Yield (%)", 0.0, 30.0, 5.0, 0.5)

is_psx = "Pakistan" in market_choice
currency_symbol = "PKR" if is_psx else "USD"

# -----------------------------------------------------------------------------
# 5. TICKER DICTIONARIES
# -----------------------------------------------------------------------------
PSX_TICKERS = {
    "HUBC": "Hub Power Company", "EFERT": "Engro Fertilizers", 
    "FFC": "Fauji Fertilizer Company", "ENGRO": "Engro Corporation",
    "MEBL": "Meezan Bank Limited", "UBL": "United Bank Limited", 
    "MCB": "MCB Bank Limited", "HBL": "Habib Bank Limited",
    "OGDC": "Oil & Gas Development Co", "PPL": "Pakistan Petroleum Ltd",
    "POL": "Pakistan Oilfields Ltd", "MARI": "Mari Petroleum Company",
    "LUCK": "Lucky Cement Limited", "SYS": "Systems Limited", 
    "PSO": "Pakistan State Oil", "KAPCO": "Kot Addu Power Company", 
    "MTL": "Millat Tractors Limited", "BAFL": "Bank Alfalah Limited",
    "BAHL": "Bank AL Habib Limited", "BOP": "The Bank of Punjab",
    "LOTCHEM": "Lotte Chemical Pakistan", "FCCL": "Fauji Cement Company",
    "NATF": "National Foods", "EFOODS": "Engro Foods (FrieslandCampina)",
    "TRG": "TRG Pakistan", "INIL": "International Industries",
    "ISL": "International Steels", "DGKC": "DG Khan Cement",
    "CHCC": "Cherat Cement", "MLCF": "Maple Leaf Cement",
    "PIOC": "Pioneer Cement", "FABL": "Faysal Bank Limited",
    "AKBL": "Askari Bank Limited", "SNGP": "Sui Northern Gas",
    "SSGC": "Sui Southern Gas", "NRL": "National Refinery",
    "PRL": "Pakistan Refinery", "ATRL": "Attock Refinery",
    "APL": "Attock Petroleum", "SEARL": "The Searle Company",
    "ABOT": "Abbott Laboratories", "GLAXO": "GlaxoSmithKline",
    "NESTLE": "Nestle Pakistan", "PAEL": "Pak Elektron Limited",
    "KEL": "K-Electric Limited", "SAZEW": "Sazgar Engineering",
    "HCAR": "Honda Atlas Cars", "INDU": "Indus Motor Company",
    "AVN": "Avanceon Limited", "NETSOL": "NetSol Technologies",
    "EPCL": "Engro Polymer", "ICI": "ICI Pakistan"
}

GLOBAL_TICKERS = {
    "T": "AT&T Inc.", "VZ": "Verizon Communications", "KO": "The Coca-Cola Company", 
    "JNJ": "Johnson & Johnson", "PG": "Procter & Gamble", "XOM": "Exxon Mobil Corp",
    "CVX": "Chevron Corp", "PFE": "Pfizer Inc.", "ABBV": "AbbVie Inc.", 
    "PEP": "PepsiCo, Inc.", "MO": "Altria Group", "PM": "Philip Morris International",
    "O": "Realty Income Corp", "MAIN": "Main Street Capital"
}

active_tickers = PSX_TICKERS if is_psx else GLOBAL_TICKERS

# -----------------------------------------------------------------------------
# 6. DIRECT API DATA FETCHING (User's Working Logic + Expanded Stats)
# -----------------------------------------------------------------------------
@st.cache_data(ttl=1800, show_spinner=False)
def fetch_psx_full_data():
    """Fetches live prices, highs, lows, and changes directly from the PSX API."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get("https://dps.psx.com.pk/api/marketData", headers=headers, timeout=10)
        if response.status_code == 200:
            return {item['symbol']: item for item in response.json()}
    except Exception:
        pass
    return {}

@st.cache_data(ttl=3600, show_spinner=False)
def run_screener(ticker_dict, is_psx_market):
    results = []
    psx_api_data = fetch_psx_full_data() if is_psx_market else {}
    one_year_ago = pd.Timestamp.now(tz='UTC') - pd.DateOffset(years=1)

    with st.spinner("Analyzing market data and calculating dividend yields..."):
        for symbol, name in ticker_dict.items():
            yf_symbol = f"{symbol}.KA" if is_psx_market else symbol
            
            try:
                stock = yf.Ticker(yf_symbol)
                
                # Default metrics
                current_price = 0.0
                high_price = 0.0
                low_price = 0.0
                change_pkr = 0.0
                change_pct = 0.0

                # 1. Determine Price & Market Stats (PSX API prioritized)
                if is_psx_market and symbol in psx_api_data:
                    raw_item = psx_api_data[symbol]
                    current_price = float(raw_item.get('price', 0))
                    high_price = float(raw_item.get('high', 0))
                    low_price = float(raw_item.get('low', 0))
                    change_pkr = float(raw_item.get('change', 0))
                    
                    prev_close = current_price - change_pkr
                    if prev_close != 0:
                        change_pct = (change_pkr / prev_close) * 100
                else:
                    # YF Fallback
                    hist = stock.history(period="5d")
                    if not hist.empty:
                        current_price = hist["Close"].iloc[-1]
                        high_price = hist["High"].iloc[-1]
                        low_price = hist["Low"].iloc[-1]

                if current_price <= 0:
                    continue 

                # 2. Calculate Exact Trailing Dividend Yield manually
                yield_decimal = 0.0
                div_history = stock.dividends
                
                if not div_history.empty:
                    if div_history.index.tz is None:
                        div_history.index = div_history.index.tz_localize('UTC')
                    else:
                        div_history.index = div_history.index.tz_convert('UTC')
                        
                    recent_divs = div_history[div_history.index >= one_year_ago]
                    annual_payout = recent_divs.sum()
                    
                    if annual_payout > 0:
                        yield_decimal = annual_payout / current_price

                # Fallback to Yahoo's recorded yield for Global stocks
                if yield_decimal == 0 and not is_psx_market:
                    info_yield = stock.info.get("trailingAnnualDividendYield")
                    if info_yield:
                        yield_decimal = info_yield

                results.append({
                    "Symbol": symbol,
                    "yf_ticker": yf_symbol,
                    "Company Name": name,
                    "Price": current_price,
                    "High": high_price,
                    "Low": low_price,
                    "24h Change (PKR)": round(change_pkr, 2),
                    "24h Change (%)": round(change_pct, 2),
                    "Yield (%)": round(yield_decimal * 100, 2)
                })
                
            except Exception:
                pass 
                
    return pd.DataFrame(results)

# Run main data pipeline
df = run_screener(active_tickers, is_psx)

# -----------------------------------------------------------------------------
# 7. TABBED INTERFACE
# -----------------------------------------------------------------------------
tab1, tab2 = st.tabs(["📊 Dividend Screener & Payouts", "🏛️ Full Market Overview"])

# =============================================================================
# TAB 1: DIVIDEND SCREENER
# =============================================================================
with tab1:
    st.header("Dividend Screener")
    
    # Search & Dropdown Controls
    col_search, col_entries = st.columns([3, 1])
    with col_search:
        search_query = st.text_input("🔍 Search by Company Name or Symbol:", "").strip().lower()
    with col_entries:
        num_entries = st.selectbox("Show entries:", options=[10, 20, 50, 100], index=2) # Default = 50

    # Filter Dataframe
    if not df.empty:
        filtered_df = df[df["Yield (%)"] >= min_yield].copy()
        
        # Apply Search Filter
        if search_query:
            filtered_df = filtered_df[
                filtered_df["Symbol"].str.lower().str.contains(search_query) | 
                filtered_df["Company Name"].str.lower().str.contains(search_query)
            ]
            
        filtered_df = filtered_df.sort_values("Yield (%)", ascending=False)
        display_df = filtered_df.head(num_entries)

        # Export Button & Summary
        col_summary, col_export = st.columns([3, 1])
        with col_summary:
            st.caption(f"Showing **{len(display_df)}** of **{len(filtered_df)}** matching companies with yield ≥ {min_yield}%")
        with col_export:
            if not display_df.empty:
                excel_bytes = convert_df_to_excel(display_df[["Symbol", "Company Name", "Price", "Yield (%)"]])
                st.download_button(
                    label="📥 Export Table to Excel",
                    data=excel_bytes,
                    file_name=f"Dividend_Screener_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )

        if display_df.empty:
            st.warning("No companies match your current yield slider or search query.")
        else:
            # Main Dataframe
            st.dataframe(
                display_df[["Symbol", "Company Name", "Price", "Yield (%)"]],
                hide_index=True,
                use_container_width=True,
                height=380,
                column_config={
                    "Price": st.column_config.NumberColumn(f"Price ({currency_symbol})", format="%.2f"),
                    "Yield (%)": st.column_config.ProgressColumn("Annual Yield", format="%.2f%%", min_value=0, max_value=max(display_df["Yield (%)"].max(), 0.1))
                }
            )

            # Historical Deep Dive
            st.divider()
            st.subheader("📜 Detailed Dividend History")
            
            display_df["Dropdown"] = display_df["Symbol"] + " - " + display_df["Company Name"]
            option_map = dict(zip(display_df["Dropdown"], display_df["yf_ticker"]))
            
            selected_display = st.selectbox(
                "Select a company to inspect payout history:",
                options=list(option_map.keys()),
                index=0
            )

            if selected_display:
                yf_target = option_map[selected_display]
                target_data = display_df[display_df["Dropdown"] == selected_display].iloc[0]
                
                m1, m2 = st.columns(2)
                m1.metric("Current Closing Price", f"{currency_symbol} {target_data['Price']:,.2f}")
                m2.metric("Calculated Trailing Yield", f"{target_data['Yield (%)']:.2f}%")

                stock_obj = yf.Ticker(yf_target)
                div_history = stock_obj.dividends
                
                if not div_history.empty:
                    div_df = pd.DataFrame(div_history).reset_index()
                    div_df.columns = ["Date", "Amount"]
                    div_df["Date"] = pd.to_datetime(div_df["Date"]).dt.tz_localize(None).dt.date
                    div_df = div_df.sort_values(by="Date", ascending=False).reset_index(drop=True)
                    
                    subtab1, subtab2 = st.tabs(["📊 Payout Chart", "📄 Payout Log"])
                    with subtab1:
                        fig = px.bar(
                            div_df.head(40),
                            x="Date", y="Amount",
                            labels={"Date": "Payout Date", "Amount": f"Dividend ({currency_symbol})"},
                            color_discrete_sequence=["#1b9e77"]
                        )
                        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
                        st.plotly_chart(fig, use_container_width=True)
                        
                    with subtab2:
                        st.dataframe(
                            div_df,
                            use_container_width=True,
                            hide_index=True,
                            height=300,
                            column_config={"Amount": st.column_config.NumberColumn(f"Amount ({currency_symbol})", format="%.2f")}
                        )
                else:
                    st.info("No recorded dividend payout history found for this company.")
    else:
        st.error("Unable to load market data.")

# =============================================================================
# TAB 2: FULL MARKET OVERVIEW (High, Low, 24h Change)
# =============================================================================
with tab2:
    st.header("Full Market Overview")
    st.caption("Complete market metrics including daily High, Low, and 24-hour price movements.")
    
    if not df.empty:
        market_overview_df = df[["Symbol", "Company Name", "Price", "High", "Low", "24h Change (PKR)", "24h Change (%)"]].copy()
        
        # Color styling function for price changes
        def style_change(val):
            color = '#00875A' if val > 0 else '#DE350B' if val < 0 else '#5E6C84'
            return f'color: {color}; font-weight: 600;'

        styled_market_df = market_overview_df.style.map(
            style_change, subset=['24h Change (PKR)', '24h Change (%)']
        ).format({
            "Price": "{:.2f}",
            "High": "{:.2f}",
            "Low": "{:.2f}",
            "24h Change (PKR)": "{:+.2f}",
            "24h Change (%)": "{:+.2f}%"
        })

        col_m_info, col_m_export = st.columns([3, 1])
        with col_m_info:
            st.write(f"Displaying **{len(market_overview_df)}** listed companies")
        with col_m_export:
            excel_market_bytes = convert_df_to_excel(market_overview_df)
            st.download_button(
                label="📥 Export Market Data to Excel",
                data=excel_market_bytes,
                file_name=f"PSX_Full_Market_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

        st.dataframe(
            styled_market_df,
            hide_index=True,
            use_container_width=True,
            height=550
        )
    else:
        st.error("Market data is currently unavailable.")
