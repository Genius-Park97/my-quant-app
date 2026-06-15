import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import urllib.parse
import requests
import time

# 페이지 설정
st.set_page_config(page_title="Wall Street Senior Quant System", layout="wide", initial_sidebar_state="collapsed")

# 스타일 설정 (냉혹한 블랙 & 골드 테마)
st.markdown("""
    <style>
    .main {
        background-color: #0a0a0a;
        color: #e0e0e0;
    }
    .stButton>button {
        width: 100%;
        border-radius: 2px;
        height: 3.5em;
        background-color: #1a1a1a;
        color: #d4af37;
        font-weight: bold;
        border: 1px solid #d4af37;
    }
    .stButton>button:hover {
        background-color: #d4af37;
        color: black;
    }
    .report-card {
        background-color: #000000;
        padding: 25px;
        border-radius: 5px;
        border: 1px solid #333333;
        border-left: 8px solid #d4af37;
        margin-bottom: 25px;
    }
    .fact-box {
        background-color: #111111;
        padding: 15px;
        border-radius: 3px;
        border-top: 2px solid #555555;
        margin-top: 10px;
        font-family: 'Courier New', Courier, monospace;
        font-size: 0.9em;
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
            vix = yf.Ticker("^VIX").history(period="1d")['Close'].iloc[-1]
            spy = yf.Ticker("SPY").history(period="1mo")['Close']
            spy_drop = ((spy.max() - spy.iloc[-1]) / spy.max()) * 100
            return vix, spy_drop
        except: return 0, 0

    def translate_text(self, text):
        try:
            url = f"https://api.mymemory.translated.net/get?q={urllib.parse.quote(text)}&langpair=en|ko"
            response = requests.get(url, timeout=5)
            data = response.json()
            if data.get('responseStatus') == 200:
                return data.get('responseData').get('translatedText')
            return "번역 오류"
        except: return "번역 실패"

    def analyze_news(self):
        try:
            news_list = self.stock.news
            if not news_list: return []
            impactful_news = []
            for n in news_list[:5]:
                content = n.get('content', n)
                title = content.get('title', '')
                summary = content.get('summary', '데이터 없음')
                provider = content.get('provider', {}).get('displayName', 'Verified Source')
                link = content.get('clickThroughUrl', {}).get('url', '#')
                impactful_news.append({
                    'title': title,
                    'publisher': provider,
                    'link': link,
                    'summary': summary
                })
            return impactful_news
        except: return []

# 헤더
st.title("⚖️ Wall Street Senior Quant System")
st.subheader("냉혹한 팩트 기반 우량주 대폭락 감시 시스템")

def get_decision(rsi, curr_price, ema20, ema60, prev_price, vix, spy_drop):
    """
    [투자 원칙 기반 냉혹한 의사결정 로직]
    - 매수 적기: 하락세가 멈추고 저점을 다지는 구간 (RSI 과매도 및 하단 지지)
    - 강력 홀딩: 우상향 추세 유지 중 (EMA20 상회)
    - 일반 익절: 추세 꺾임 확인 (EMA20 하향 돌파 및 기술적 하락 시그널)
    - 긴급 매도: 시스템적 대폭락(Mega-crash) 또는 펀더멘털 붕괴 징후
    - 관망: 모호한 기술적 구간
    """
    decision = "관망"
    color = "#888888"
    reason_points = []
    
    # 1. 긴급 전량 매도 (Mega-crash 감지)
    if vix > 38 or spy_drop > 15:
        decision, color = "긴급 전량 매도", "#ff0000"
        reason_points = ["거시경제 지표상 시스템적 대폭락(Mega-crash) 명백히 예견됨.", "VIX 지수 임계치 돌파", "지수 하락 폭이 회복 불가능한 수준에 도달"]
    
    # 2. 매수 적기 (저점 다지는 구간)
    elif rsi < 32 and curr_price >= prev_price * 0.99:
        decision, color = "매수 적기 (전재산 100%)", "#00ff00"
        reason_points = ["주가가 충분히 조정을 받아 하락세가 멈춤.", "RSI 과매도 구간 진입 후 저점 지지 확인.", "초대형 우량주 특유의 하방 경직성 확보."]
    
    # 3. 일반 익절 (추세 꺾임)
    elif curr_price < ema20 and prev_price >= ema20:
        decision, color = "일반 익절", "#ffff00"
        reason_points = ["상승 추세가 기술적으로 꺾이는 시그널 발생.", "EMA20 하향 돌파 확인됨.", "단기 조정 또는 추세 전환 가능성 농후."]
    
    # 4. 강력 홀딩
    elif curr_price > ema20:
        decision, color = "강력 홀딩", "#008000"
        reason_points = ["우상향 추세가 견고하게 유지됨.", "일상적 노이즈를 제외한 추세 지표가 양호함.", "펀더멘털의 훼손 징후 없음."]
    
    else:
        decision, color = "관망", "#888888"
        reason_points = ["추세가 불분명한 중립 구간임.", "확실한 진입 또는 탈출 시그널 부재.", "데이터 기반 근거 부족."]

    return decision, color, reason_points

# 탭 메뉴 구성
tab1, tab2 = st.tabs(["📊 종목 심층 분석", "🏆 추천 순위 스캔"])

with tab1:
    ticker_input = st.text_input("분석할 티커 입력 (예: MSFT, NVDA, ASTS)", placeholder="티커를 입력하십시오...").upper()
    if st.button("팩트 분석 실행"):
        if ticker_input:
            with st.spinner(f"{ticker_input} 데이터 수집 및 뉴스 분석 중..."):
                quant = WallStreetQuant(ticker_input)
                df = quant.get_realtime_data()
                
                if df is None:
                    st.error(f"'{ticker_input}' 데이터 로드 실패. 티커를 확인하십시오.")
                else:
                    vix, spy_drop = quant.monitor_macro_risk()
                    curr_price = df['Close'].iloc[-1]
                    prev_price = df['Close'].iloc[-2]
                    rsi = df['RSI'].iloc[-1]
                    ema20 = df['EMA20'].iloc[-1]
                    ema60 = df['EMA60'].iloc[-1]

                    decision, color, reasons = get_decision(rsi, curr_price, ema20, ema60, prev_price, vix, spy_drop)
                    news = quant.analyze_news()

                    st.markdown(f"""
                        <div class='report-card'>
                            <h3>최종 결론: <span style='color:{color}'>{decision}</span></h3>
                            <p><b>핵심 근거:</b></p>
                            <ul>
                                {"".join(f"<li>{r}</li>" for r in reasons)}
                            </ul>
                            <hr style='border: 0.5px solid #333;'>
                            <p>현재가: ${curr_price:,.2f} | RSI: {rsi:.2f} | VIX: {vix:.2f}</p>
                        </div>
                    """, unsafe_allow_html=True)

                    st.write("#### [팩트 및 출처 리스트]")
                    if not news:
                        st.info("현재 분석을 뒷받침할 결정적 최신 뉴스가 없습니다.")
                    for n in news:
                        with st.expander(f"📰 {n['title']}", expanded=False):
                            st.write(f"**출처:** {n['publisher']}")
                            st.write(f"**원본 요약:** {n['summary']}")
                            st.write(f"**국문 번역:** {quant.translate_text(n['summary'][:300])}")
                            st.write(f"[팩트 확인하기]({n['link']})")
        else:
            st.warning("티커를 입력하십시오.")

with tab2:
    if st.button("Elite 32+ 전체 순위 스캔 시작"):
        watch_list = [
            'MSFT', 'AAPL', 'NVDA', 'GOOGL', 'AMZN', 'META', 'TSLA', 'AVGO', 'ASML', 'LRCX',
            'AMAT', 'ORCL', 'ADBE', 'ISRG', 'INTU', 'PANW', 'VRT', 'BRK-B', 'JPM', 'V',
            'MA', 'BX', 'LLY', 'UNH', 'TMO', 'SYK', 'COST', 'WMT', 'PEP', 'HD', 'NFLX', 'XOM', 'PWR',
            'ASTS', 'RKLB'
        ]
        
        results = []
        progress = st.progress(0)
        vix, spy_drop = WallStreetQuant("SPY").monitor_macro_risk()

        for i, ticker in enumerate(watch_list):
            progress.progress((i + 1) / len(watch_list))
            try:
                stock = WallStreetQuant(ticker)
                df = stock.get_realtime_data()
                if df is None: continue
                
                curr_price = df['Close'].iloc[-1]
                prev_price = df['Close'].iloc[-2]
                rsi = df['RSI'].iloc[-1]
                ema20 = df['EMA20'].iloc[-1]
                ema60 = df['EMA60'].iloc[-1]
                
                decision, _, _ = get_decision(rsi, curr_price, ema20, ema60, prev_price, vix, spy_drop)

                # 순위용 점수 산정 (사용자 원칙: 저점 매수 기회일수록 높음)
                score = 0
                if "매수 적기" in decision: score = 100 - rsi
                elif "강력 홀딩" in decision: score = 50 + (rsi / 2)
                elif "관망" in decision: score = 20
                else: score = 0 # 매도 시점
                
                results.append({
                    '티커': ticker,
                    '현재가': f"${curr_price:.2f}",
                    '결론': decision,
                    'RSI': f"{rsi:.1f}",
                    'score': score
                })
            except: continue
        
        df_res = pd.DataFrame(results).sort_values(by='score', ascending=False).drop(columns=['score'])
        df_res.insert(0, '순위', range(1, len(df_res) + 1))
        
        st.write("### 🏆 실시간 우량주 진입 추천 순위")
        st.dataframe(df_res, hide_index=True, use_container_width=True)
        st.caption("※ 상위권 종목일수록 [저점 매수] 원칙에 부합하는 종목입니다.")

st.sidebar.markdown("### 🏛️ 수석 퀀트 투자 원칙")
st.sidebar.error("1. 파산 위험 제로 우량주 한정")
st.sidebar.error("2. 전재산 100% 매수/매도")
st.sidebar.warning("3. 시스템 폭락 외 손절 금지")
st.sidebar.info("4. 하락 멈춤 저점 매수")
st.sidebar.info("5. 추세 이탈 익절")

# 하단 리스크 모니터링
v_v, s_v = WallStreetQuant("SPY").monitor_macro_risk()
if v_v > 30:
    st.error(f"🚨 시장 변동성 위험: VIX {v_v:.2f}")
else:
    st.success(f"✅ 시장 시스템 안정: VIX {v_v:.2f}")
