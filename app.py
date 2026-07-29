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
    .main .block-container { padding-top: 1rem; padding-bottom: 2rem; }
    h1, h2, h3 { font-family: 'Helvetica Neue', sans-serif; color: #1E1E1E; }
    .stDataFrame { font-size: 0.95rem; }
    [data-testid="stMetric"] {
        background-color: #f8f9fa;
        border-radius: 0.5rem;
        padding: 1rem;
        border: 1px solid #e9ecef;
    }
    .time-display {
        font-size: 1.1rem;
        font-weight: 500;
        color: #4A4A4A;
        margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. HELPER FUNCTIONS (Time & Export)
# -----------------------------------------------------------------------------
def get_current_pkt_time():
    """Returns formatted current time in Pakistan Standard Time (PKT)."""
    tz = pytz.timezone('Asia/Karachi')
    return datetime.now(tz).strftime('%A, %B %d, %Y at %I:%M:%S %p PKT')

def convert_df_to_excel(df):
    """Converts a pandas dataframe to an Excel file object in memory."""
    output = io.BytesIO()
    # Using openpyxl as the engine since it is standard for Pandas Excel export
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    return output.getvalue()

# -----------------------------------------------------------------------------
# 3. ROBUST TICKER DICTIONARY (PSX ONLY)
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
    "APL": "Attock Petroleum", "HASCOL": "Hascol Petroleum",
    "SEARL": "The Searle Company", "AGP": "AGP Limited",
    "ABOT": "Abbott Laboratories", "GLAXO": "GlaxoSmithKline",
    "NESTLE": "Nestle Pakistan", "PAEL": "Pak Elektron Limited",
    "KEL": "K-Electric Limited", "SAZEW": "Sazgar Engineering",
    "HCAR": "Honda Atlas Cars", "INDU": "Indus Motor Company",
    "PSMC": "Pak Suzuki Motor", "GTYR": "General Tyre",
    "AVN": "Avanceon Limited", "NETSOL": "NetSol Technologies",
    "EPCL": "Engro Polymer", "ICI": "ICI Pakistan",
    "BATM": "Bata Pakistan", "SRVI": "Service Industries",
    "NML": "Nishat Mills", "GATM": "Gul Ahmed Textile"
}

# -----------------------------------------------------------------------------
# 4. DIRECT API DATA FETCHING (Works 24/7)
# -----------------------------------------------------------------------------
@st.cache_data(ttl=900, show_spinner=False)
def fetch_psx_market_data():
    """
    Fetches live market data from PSX API, including high, low, and change.
    Returns a processed dataframe.
    """
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get("https://dps.psx.com.pk/api/marketData", headers=headers, timeout=10)
        
        if response.status_code == 200:
            raw_data = response.json()
            processed_data = []
            
            for item in raw_data:
                symbol = item.get('symbol')
                if symbol in PSX_TICKERS:
                    current_price = float(item.get('price', 0))
                    high_price = float(item.get('high', 0))
                    low_price = float(item.get('low', 0))
                    change = float(item.get('change', 0))
                    
                    if current_price - change != 0:
                        change_percent = (change / (current_price - change)) * 100
                    else:
                        change_percent = 0.0

                    processed_data.append({
                        "Symbol": symbol,
                        "Company Name": PSX_TICKERS[symbol],
                        "Current Price": current_price,
                        "High": high_price,
                        "Low": low_price,
                        "Change (PKR)": change,
                        "Change (%)": round(change_percent, 2)
                    })
            
            return pd.DataFrame(processed_data)
    except Exception as e:
        st.error(f"Failed to connect to PSX API: {e}")
    
    return pd.DataFrame()

@st.cache_data(ttl=3600, show_spinner=False)
def get_dividend_yield(symbol, current_price):
    """Calculates manual trailing dividend yield using yfinance."""
    if current_price <= 0: return 0.0
    
    yf_symbol = f"{symbol}.KA"
    one_year_ago = pd.Timestamp.now(tz='UTC') - pd.DateOffset(years=1)
    
    try:
        stock = yf.Ticker(yf_symbol)
        div_history = stock.dividends
        
        if not div_history.empty:
            if div_history.index.tz is None:
                div_history.index = div_history.index.tz_localize('UTC')
            else:
                div_history.index = div_history.index.tz_convert('UTC')
                
            recent_divs = div_history[div_history.index >= one_year_ago]
            annual_payout = recent_divs.sum()
            
            if annual_payout > 0:
                return (annual_payout / current_price) * 100
    except Exception:
        pass
    
    return 0.0

# -----------------------------------------------------------------------------
# 5. HEADER & CLOCK
# -----------------------------------------------------------------------------
st.title("📈 PSX Market & Dividend Scout")
st.markdown(f"<div class='time-display'>🕒 {get_current_pkt_time()}</div>", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 6. MAIN DATA LOADING
# -----------------------------------------------------------------------------
market_df = fetch_psx_market_data()

# -----------------------------------------------------------------------------
# 7. TABBED INTERFACE
# -----------------------------------------------------------------------------
if not market_df.empty:
    tab1, tab2 = st.tabs(["📊 Dividend Screener & History", "🏛️ Full Market Overview"])
    
    # =========================================================================
    # TAB 1: DIVIDEND SCREENER & HISTORY (With Search & Dropdown)
    # =========================================================================
    with tab1:
        st.header("Dividend Screener")
        
        col_search, col_yield, col_entries = st.columns([2, 1, 1])
        with col_search:
            search_query = st.text_input("🔍 Search Company Name or Symbol:", "").lower()
        with col_yield:
            min_yield = st.number_input("Min Yield (%)", min_value=0.0, max_value=30.0, value=5.0, step=0.5)
        with col_entries:
            num_entries = st.selectbox("Entries to display:", options=[10, 20, 50, 100], index=2) 
            
        st.divider()

        screener_data = []
        with st.spinner("Analyzing dividend yields..."):
            for index, row in market_df.iterrows():
                symbol = row['Symbol']
                name = row['Company Name']
                price = row['Current Price']
                
                if search_query and (search_query not in symbol.lower() and search_query not in name.lower()):
                    continue
                
                yield_pct = get_dividend_yield(symbol, price)
                
                if yield_pct >= min_yield:
                    screener_data.append({
                        "Symbol": symbol,
                        "Company Name": name,
                        "Price": price,
                        "Yield (%)": round(yield_pct, 2)
                    })
                    
        screener_df = pd.DataFrame(screener_data)
        
        if not screener_df.empty:
            display_df = screener_df.sort_values("Yield (%)", ascending=False).head(num_entries)
            
            excel_data_1 = convert_df_to_excel(display_df)
            st.download_button(
                label="📥 Export Screener Results to Excel",
                data=excel_data_1,
                file_name=f"PSX_Dividend_Screen_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
            st.dataframe(
                display_df,
                hide_index=True,
                use_container_width=True,
                height=400,
                column_config={
                    "Price": st.column_config.NumberColumn("Price (PKR)", format="%.2f"),
                    "Yield (%)": st.column_config.ProgressColumn("Annual Yield", format="%.2f%%", min_value=0, max_value=max(display_df["Yield (%)"].max(), 0.1))
                }
            )
            
            st.subheader("📜 Detailed Dividend History")
            display_df["Dropdown"] = display_df["Symbol"] + " - " + display_df["Company Name"]
            selected_display = st.selectbox("Select a stock to view its complete payout history:", options=display_df["Dropdown"].tolist(), index=None)

            if selected_display:
                selected_symbol = selected_display.split(" - ")[0]
                yf_target = f"{selected_symbol}.KA"
                target_data = display_df[display_df["Dropdown"] == selected_display].iloc[0]
                
                m1, m2 = st.columns(2)
                m1.metric("Latest Closing Price", f"PKR {target_data['Price']:,.2f}")
                m2.metric("Calculated Trailing Yield", f"{target_data['Yield (%)']:.2f}%")

                stock_obj = yf.Ticker(yf_target)
                div_history = stock_obj.dividends
                
                if not div_history.empty:
                    div_df = pd.DataFrame(div_history).reset_index()
                    div_df.columns = ["Date", "Amount"]
                    div_df["Date"] = pd.to_datetime(div_df["Date"]).dt.tz_localize(None).dt.date
                    div_df = div_df.sort_values(by="Date", ascending=False).reset_index(drop=True)
                    
                    tab_chart, tab_log = st.tabs(["📊 Payout Timeline", "📄 Raw Data Log"])
                    
                    with tab_chart:
                        fig = px.bar(div_df.head(40), x="Date", y="Amount", labels={"Date": "Payout Date", "Amount": "Dividend (PKR)"}, color_discrete_sequence=["#1b9e77"])
                        st.plotly_chart(fig, use_container_width=True)
                        
                    with tab_log:
                        st.dataframe(div_df, use_container_width=True, hide_index=True, height=350)
                else:
                    st.info("Dividend records are not available for this entity.")
        else:
            st.warning("No stocks match the current search or filter criteria.")

    # =========================================================================
    # TAB 2: FULL MARKET OVERVIEW (High, Low, Change)
    # =========================================================================
    with tab2:
        st.header("Full Market Overview")
        st.caption("Live prices, daily highs, lows, and 24-hour changes for tracked companies.")
        
        def style_change(val):
            color = 'green' if val > 0 else 'red' if val < 0 else 'gray'
            return f'color: {color}'

        styled_market_df = market_df.style.map(style_change, subset=['Change (PKR)', 'Change (%)']).format({
            "Current Price": "{:.2f}",
            "High": "{:.2f}",
            "Low": "{:.2f}",
            "Change (PKR)": "{:+.2f}",
            "Change (%)": "{:+.2f}%"
        })

        excel_data_2 = convert_df_to_excel(market_df)
        st.download_button(
            label="📥 Export Full Market Data to Excel",
            data=excel_data_2,
            file_name=f"PSX_Market_Data_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        st.dataframe(
            styled_market_df,
            hide_index=True,
            use_container_width=True,
            height=600
        )

else:
    st.error("Unable to load market data. Please check your internet connection or try again later.")
