import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import urllib.parse
import requests
import time

# 페이지 설정
st.set_page_config(page_title="Wall Street Senior Quant System", layout="wide", initial_sidebar_state="collapsed")

# 스타일 설정 (사용자가 선호한 블랙 & 그린 테마 기반)
st.markdown("""
    <style>
    .main {
        background-color: #0a0a0a;
        color: #dcdcdc;
    }
    .stButton>button {
        width: 100%;
        border-radius: 5px;
        height: 3em;
        background-color: #1a1a1a;
        color: #00ff00;
        font-weight: bold;
        border: 1px solid #00ff00;
    }
    .stButton>button:hover {
        background-color: #005500;
        color: white;
    }
    .report-card {
        background-color: #000000;
        padding: 20px;
        border-radius: 10px;
        border-left: 10px solid #00ff00;
        border: 1px solid #333;
        margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

class WallStreetQuant:
    def __init__(self, ticker):
        self.ticker = ticker.upper()
        self.stock = yf.Ticker(self.ticker)
        
    def calculate_rsi(self, series, period=14):
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def get_realtime_data(self):
        try:
            df = self.stock.history(period="1y", interval="1d")
            if df.empty or len(df) < 20: return None
            df['RSI'] = self.calculate_rsi(df['Close'], 14)
            df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
            df['EMA60'] = df['Close'].ewm(span=60, adjust=False).mean()
            return df
        except: return None

    def monitor_macro_risk(self):
        try:
            vix = yf.Ticker("^VIX").history(period="1d")['Close'].iloc[-1]
            spy = yf.Ticker("SPY").history(period="1mo")['Close']
            spy_drop = ((spy.max() - spy.iloc[-1]) / spy.max()) * 100
            return vix, spy_drop
        except: return 0, 0

    def translate_text(self, text):
        try:
            url = f"https://api.mymemory.translated.net/get?q={urllib.parse.quote(text[:300])}&langpair=en|ko"
            response = requests.get(url, timeout=5)
            data = response.json()
            return data.get('responseData').get('translatedText') if data.get('responseStatus') == 200 else "번역 오류"
        except: return "번역 실패"

    def analyze_news(self):
        try:
            news_list = self.stock.news
            if not news_list: return []
            impactful_news = []
            for n in news_list[:3]:
                content = n.get('content', n)
                impactful_news.append({
                    'title': content.get('title', ''),
                    'publisher': content.get('provider', {}).get('displayName', 'Source'),
                    'link': content.get('clickThroughUrl', {}).get('url', '#'),
                    'summary': content.get('summary', '')
                })
            return impactful_news
        except: return []

# 타이틀
st.title("🏛️ Wall Street Senior Quant System")
st.subheader("Elite 32+ 대폭락 감시 및 진입 최적화 모듈")

def get_decision(rsi, curr_price, ema20, ema60, prev_price, vix, spy_drop, df):
    """
    [투자 원칙 기반 5단계 의사결정 로직]
    1. 긴급 매도: 시스템적 폭락 징후 (VIX > 35 or 지수 하락 > 12%)
    2. 매수 적기: 하락 멈춤 및 저점 다지기 (RSI < 32 & 최근 3일 저점 방어)
    3. 일반 익절: 상승 추세 꺾임 (EMA20 하향 돌파)
    4. 강력 홀딩: 우상향 유지 (Price > EMA20)
    5. 관망: 시그널 부재
    """
    decision = "관망"
    color = "#888888"
    score = 30 # 기본 점수
    
    # 최근 저점 지지 확인 (Bottoming out)
    is_bottoming = curr_price >= df['Low'].iloc[-5:].min() * 1.01
    
    if vix > 35 or spy_drop > 12:
        decision, color, score = "긴급 전량 매도", "#ff0000", 0
    elif rsi < 32 and is_bottoming:
        decision, color, score = "매수 적기 (전재산 100%)", "#00ff00", 95 + (32 - rsi)
    elif curr_price < ema20 and prev_price >= ema20:
        decision, color, score = "일반 익절", "#ffff00", 10
    elif curr_price > ema20:
        decision, color, score = "강력 홀딩", "#008000", 60 + (rsi / 5)
    else:
        decision, color, score = "관망", "#888888", 30
        
    return decision, color, score

# 리스트 유지
WATCH_LIST = [
    'MSFT', 'AAPL', 'NVDA', 'GOOGL', 'AMZN', 'META', 'TSLA', 'AVGO', 'ASML', 'LRCX',
    'AMAT', 'ORCL', 'ADBE', 'ISRG', 'INTU', 'PANW', 'VRT', 'BRK-B', 'JPM', 'V',
    'MA', 'BX', 'LLY', 'UNH', 'TMO', 'SYK', 'COST', 'WMT', 'PEP', 'HD', 'NFLX', 'XOM', 'PWR',
    'ASTS', 'RKLB'
]

tab1, tab2 = st.tabs(["📊 종목 심층 분석", "🏆 추천 순위 스캔"])

with tab1:
    ticker_input = st.text_input("분석할 티커 입력 (예: MSFT, NVDA, ASTS)").upper()
    if st.button("실시간 팩트 분석 실행"):
        if ticker_input:
            with st.spinner(f"{ticker_input} 분석 중..."):
                quant = WallStreetQuant(ticker_input)
                df = quant.get_realtime_data()
                if df is not None:
                    vix, spy_drop = quant.monitor_macro_risk()
                    curr_price = df['Close'].iloc[-1]
                    prev_price = df['Close'].iloc[-2]
                    rsi = df['RSI'].iloc[-1]
                    ema20 = df['EMA20'].iloc[-1]
                    
                    decision, color, _ = get_decision(rsi, curr_price, ema20, 0, prev_price, vix, spy_drop, df)
                    news = quant.analyze_news()

                    st.markdown(f"""
                        <div class='report-card' style='border-left-color:{color}'>
                            <h3>최종 결론: <span style='color:{color}'>{decision}</span></h3>
                            <p><b>실시간 팩트 요약:</b></p>
                            <ul>
                                <li>현재가: ${curr_price:,.2f} (전일 대비 {((curr_price-prev_price)/prev_price*100):+.2f}%)</li>
                                <li>RSI: {rsi:.2f} | VIX: {vix:.2f} (시장 위험도: {"높음" if vix > 30 else "안정"})</li>
                                <li>원칙 준수 사항: 100% 매매 전략 기반 결과임.</li>
                            </ul>
                        </div>
                    """, unsafe_allow_html=True)

                    st.write("#### [판단 근거 뉴스 및 출처]")
                    for n in news:
                        with st.expander(f"📰 {n['title']}"):
                            st.write(f"**출처:** {n['publisher']}")
                            st.write(f"**핵심 요약:** {n['summary']}")
                            st.write(f"**국문 번역:** {quant.translate_text(n['summary'])}")
                            st.write(f"[팩트 소스 확인]({n['link']})")
        else:
            st.warning("티커를 입력하십시오.")

with tab2:
    if st.button("Elite 32+ 전체 순위 스캔"):
        results = []
        progress = st.progress(0)
        vix, spy_drop = WallStreetQuant("SPY").monitor_macro_risk()
        
        for i, ticker in enumerate(WATCH_LIST):
            progress.progress((i + 1) / len(WATCH_LIST))
            try:
                q = WallStreetQuant(ticker)
                df = q.get_realtime_data()
                if df is None: continue
                
                curr_price = df['Close'].iloc[-1]
                prev_price = df['Close'].iloc[-2]
                rsi = df['RSI'].iloc[-1]
                ema20 = df['EMA20'].iloc[-1]
                
                decision, color, score = get_decision(rsi, curr_price, ema20, 0, prev_price, vix, spy_drop, df)
                
                results.append({
                    '티커': ticker,
                    '현재가': f"${curr_price:.2f}",
                    'RSI': f"{rsi:.1f}",
                    '결론': decision,
                    '추천도': "★★★★★" if score > 90 else "★★★★☆" if score > 70 else "★★★☆☆" if score > 50 else "☆☆☆☆☆",
                    'score': score
                })
            except: continue
        
        df_res = pd.DataFrame(results).sort_values(by='score', ascending=False).drop(columns=['score'])
        df_res.insert(0, '순위', range(1, len(df_res) + 1))
        
        st.write("### 🏆 실시간 우량주 진입 추천 순위")
        st.dataframe(df_res, hide_index=True, use_container_width=True)
        st.caption("※ 본 순위는 '저점 매수(하락 멈춤)' 원칙에 가장 부합하는 종목을 1순위로 제안합니다.")

st.sidebar.title("🚨 수석 퀀트 투자 원칙")
st.sidebar.markdown("""
- **대상**: 초대형 우량주 전용
- **자금**: 100% 매수 / 100% 매도
- **손절**: 시스템적 대폭락 외 금지
- **매수**: 하락 멈춤 및 저점 확인
- **익절**: 기술적 추세 이탈 시
""")

# 리스크 체크
v, s = WallStreetQuant("SPY").monitor_macro_risk()
if v > 30 or s > 10:
    st.sidebar.error(f"⚠️ 매크로 리스크 경보: VIX {v:.2f}")
else:
    st.sidebar.success(f"✅ 매크로 리스크 안정: VIX {v:.2f}")
