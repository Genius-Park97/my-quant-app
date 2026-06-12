import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import urllib.parse
import requests
import time

# 페이지 설정
st.set_page_config(page_title="Wall Street Quant Mobile", layout="wide", initial_sidebar_state="collapsed")

# 스타일 설정 (다크 모드 및 모바일 최적화)
st.markdown("""
    <style>
    .main {
        background-color: #1e1e1e;
        color: #dcdcdc;
    }
    .stButton>button {
        width: 100%;
        border-radius: 5px;
        height: 3em;
        background-color: #005500;
        color: white;
        font-weight: bold;
    }
    .report-card {
        background-color: #000000;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #00ff00;
        margin-bottom: 20px;
    }
    .recommend-table {
        font-size: 0.8em;
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
            if df.empty or len(df) < 10: return None
            df['RSI'] = self.calculate_rsi(df['Close'], 14)
            df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
            df['EMA60'] = df['Close'].ewm(span=60, adjust=False).mean()
            return df
        except: return None

    def monitor_macro_risk(self):
        try:
            vix = yf.Ticker("^VIX").history(period="5d")['Close'].iloc[-1]
            spy = yf.Ticker("SPY").history(period="5d")['Close']
            spy_change = ((spy.iloc[-1] - spy.iloc[0]) / spy.iloc[0]) * 100
            return vix, spy_change
        except: return 0, 0

    def translate_text(self, text):
        try:
            url = f"https://api.mymemory.translated.net/get?q={urllib.parse.quote(text)}&langpair=en|ko"
            response = requests.get(url, timeout=5)
            data = response.json()
            if data.get('responseStatus') == 200:
                return data.get('responseData').get('translatedText')
            return "번역 한도 초과 또는 API 오류"
        except: return "번역 시스템 연결 실패"

    def analyze_news(self):
        try:
            news_list = self.stock.news
            if not news_list: return []
            
            impact_keywords = ['crash', 'collapse', 'recession', 'slump', 'downfall', 'bankruptcy', 'bear market', 'inflation', 'rate hike', 'layoff', 'lawsuit', 'investigation']
            positive_keywords = ['growth', 'breakthrough', 'dividend', 'buyback', 'partnership', 'earnings beat', 'upgrade']
            
            impactful_news = []
            for n in news_list:
                content = n.get('content', n)
                title = content.get('title', '')
                summary = content.get('summary', '')
                
                if any(kw in title.lower() or kw in summary.lower() for kw in impact_keywords + positive_keywords):
                    provider = content.get('provider', {}).get('displayName', '출처 미상')
                    link = content.get('clickThroughUrl', {}).get('url', '#')
                    sentences = summary.split('.')
                    key_sentence = next((s.strip() + "." for s in sentences if any(kw in s.lower() for kw in impact_keywords + positive_keywords)), title)
                    impact = "NEGATIVE" if any(kw in key_sentence.lower() for kw in impact_keywords) else "POSITIVE"
                    
                    impactful_news.append({
                        'title': title,
                        'publisher': provider,
                        'link': link,
                        'key_sentence': key_sentence,
                        'impact': impact
                    })
                if len(impactful_news) >= 2: break
            return impactful_news
        except: return []

# 메인 타이틀
st.title("🏛️ Wall Street Quant Mobile")
st.subheader("Elite 32 대폭락 감시 시스템")

# 탭 메뉴 구성
tab1, tab2 = st.tabs(["📊 종목 심층 분석", "🏆 진입 추천 순위"])

with tab1:
    ticker_input = st.text_input("분석할 티커 입력 (예: MSFT, NVDA)", key="ticker_input").upper()
    if st.button("실시간 분석 실행"):
        if ticker_input:
            with st.spinner(f"{ticker_input} 분석 중..."):
                quant = WallStreetQuant(ticker_input)
                df = quant.get_realtime_data()
                
                if df is None:
                    st.error(f"'{ticker_input}' 데이터를 가져올 수 없습니다. 티커를 확인하십시오.")
                else:
                    vix, spy_change = quant.monitor_macro_risk()
                    news = quant.analyze_news()
                    
                    curr_price = df['Close'].iloc[-1]
                    prev_price = df['Close'].iloc[-2]
                    rsi = df['RSI'].iloc[-1]
                    ema20 = df['EMA20'].iloc[-1]
                    ema60 = df['EMA60'].iloc[-1]

                    # 결론 로직
                    decision = "관망"
                    color = "#ffffff"
                    if vix > 35 or spy_change < -10:
                        decision, color = "긴급 전량 매도", "#ff0000"
                    elif rsi < 35 and curr_price < ema60:
                        decision, color = "매수 적기 (전재산 100%)", "#00ff00"
                    elif curr_price > ema20:
                        if curr_price < prev_price: decision, color = "일반 익절", "#ffff00"
                        else: decision, color = "강력 홀딩", "#00ff00"

                    st.markdown(f"""
                        <div class='report-card'>
                            <h3>최종 결론: <span style='color:{color}'>{decision}</span></h3>
                            <p>현재가: ${curr_price:,.2f} | RSI: {rsi:.2f}</p>
                            <p>VIX: {vix:.2f} | S&P500 변동: {spy_change:.2f}%</p>
                        </div>
                    """, unsafe_allow_html=True)

                    st.write("---")
                    st.write("### 펀더멘털 뉴스 분석")
                    if not news:
                        st.info("현재 판단에 영향을 주는 특이 뉴스가 없습니다.")
                    for n in news:
                        with st.expander(f"📰 {n['title']}"):
                            st.write(f"**출처:** {n['publisher']}")
                            st.write(f"**핵심 문장:** \"{n['key_sentence']}\"")
                            st.write(f"**국문 번역:** {quant.translate_text(n['key_sentence'])}")
                            st.write(f"[기사 원문 보기]({n['link']})")
        else:
            st.warning("티커를 입력하십시오.")

with tab2:
    if st.button("Elite 32 전체 순위 스캔"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        watch_list = [
            'MSFT', 'AAPL', 'NVDA', 'GOOGL', 'AMZN', 'META', 'TSLA', 'AVGO', 'ASML', 'LRCX',
            'AMAT', 'ORCL', 'ADBE', 'ISRG', 'INTU', 'PANW', 'VRT', 'BRK-B', 'JPM', 'V',
            'MA', 'BX', 'LLY', 'UNH', 'TMO', 'SYK', 'COST', 'WMT', 'PEP', 'HD', 'NFLX', 'XOM', 'PWR'
        ]
        
        results = []
        vix_data = yf.Ticker("^VIX").history(period="1d")
        vix = vix_data['Close'].iloc[-1] if not vix_data.empty else 0

        for i, ticker in enumerate(watch_list):
            status_text.text(f"스캔 중: {ticker} ({i+1}/{len(watch_list)})")
            progress_bar.progress((i + 1) / len(watch_list))
            try:
                stock = yf.Ticker(ticker)
                df = stock.history(period="1y", interval="1d")
                if df.empty: continue
                curr_price = df['Close'].iloc[-1]
                recent_drop = (df['Close'].iloc[-1] - df['Close'].iloc[-4]) / df['Close'].iloc[-4] * 100
                is_falling_knife = recent_drop < -8
                
                delta = df['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs)).iloc[-1]
                ema60 = df['Close'].ewm(span=60, adjust=False).mean().iloc[-1]

                score = (100 - rsi) + ((ema60 - curr_price) / ema60 * 200)
                risk = "안정"
                if is_falling_knife: score -= 150; risk = "!!폭락주의!!"
                elif rsi < 30: risk = "과매도(주의)"
                if vix > 30: score -= 50

                results.append({
                    '티커': ticker,
                    '현재가': f"${curr_price:.2f}",
                    'RSI': f"{rsi:.1f}",
                    '위험도': risk,
                    '추천도': "★★★★★" if score > 75 else "★★★★☆" if score > 60 else "★★★☆☆" if score > 30 else "★★☆☆☆",
                    'score': score
                })
            except: continue
        
        status_text.text("스캔 완료!")
        df_res = pd.DataFrame(results).sort_values(by='score', ascending=False).drop(columns=['score'])
        st.table(df_res)
        st.caption("※ 상위권 종목일수록 전재산 베팅 원칙에 부합하는 저점 매수 기회입니다.")

st.sidebar.markdown("### [투자 원칙 고수]")
st.sidebar.info("1. 초대형 우량주만 취급\\n2. 100% 매수/매도 원칙\\n3. 시스템 폭락 시에만 손절")
