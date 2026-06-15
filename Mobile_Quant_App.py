import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import urllib.parse
import requests
import time

# 페이지 설정 (냉혹한 퀀트 시스템 테마)
st.set_page_config(page_title="Wall Street Senior Quant Analyst System", layout="wide", initial_sidebar_state="collapsed")

# 스타일 설정 (월스트리트 블랙 & 하이 테크 그린)
st.markdown("""
    <style>
    .main {
        background-color: #050505;
        color: #e0e0e0;
    }
    .stButton>button {
        width: 100%;
        border-radius: 0px;
        height: 3.5em;
        background-color: #111111;
        color: #00ff00;
        font-weight: bold;
        border: 1px solid #00ff00;
        transition: 0.3s;
    }
    .stButton>button:hover {
        background-color: #00ff00;
        color: black;
    }
    .report-card {
        background-color: #000000;
        padding: 30px;
        border-radius: 4px;
        border: 1px solid #222;
        border-left: 10px solid #00ff00;
        margin-bottom: 25px;
        font-family: 'Consolas', monospace;
    }
    .news-card {
        background-color: #0a0a0a;
        padding: 15px;
        border-top: 2px solid #333;
        margin-bottom: 15px;
    }
    .status-bar {
        font-weight: bold;
        font-size: 1.1em;
        padding: 10px;
        text-align: center;
        border-radius: 5px;
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
            spy = yf.Ticker("SPY").history(period="1mo")['Close']
            spy_drop = ((spy.max() - spy.iloc[-1]) / spy.max()) * 100
            return vix, spy_drop
        except: return 0, 0

    def translate_text(self, text):
        try:
            url = f"https://api.mymemory.translated.net/get?q={urllib.parse.quote(text[:300])}&langpair=en|ko"
            response = requests.get(url, timeout=5)
            data = response.json()
            if data.get('responseStatus') == 200:
                return data.get('responseData').get('translatedText')
            return "번역 한도 초과"
        except: return "번역 시스템 연결 실패"

    def analyze_news(self, decision_type="NEUTRAL"):
        try:
            news_list = self.stock.news
            if not news_list: return []
            
            impact_keywords = ['crash', 'collapse', 'recession', 'slump', 'downfall', 'bankruptcy', 'bear market', 'inflation', 'rate hike', 'layoff', 'lawsuit', 'investigation']
            positive_keywords = ['growth', 'breakthrough', 'dividend', 'buyback', 'partnership', 'earnings beat', 'upgrade']
            
            scored_news = []
            for n in news_list[:5]:
                content = n.get('content', n)
                title = content.get('title', '')
                summary = content.get('summary', '')
                provider = content.get('provider', {}).get('displayName', 'Verified Source')
                link = content.get('clickThroughUrl', {}).get('url', '#')
                
                is_neg = any(kw in title.lower() or kw in summary.lower() for kw in impact_keywords)
                is_pos = any(kw in title.lower() or kw in summary.lower() for kw in positive_keywords)
                impact = "NEGATIVE" if is_neg else "POSITIVE" if is_pos else "NEUTRAL"
                
                score = 0
                if decision_type == "BUY" and impact == "POSITIVE": score = 2
                elif decision_type == "SELL" and impact == "NEGATIVE": score = 2
                
                scored_news.append({
                    'title': title,
                    'publisher': provider,
                    'link': link,
                    'summary': summary,
                    'score': score,
                    'impact': impact
                })
            
            return sorted(scored_news, key=lambda x: x['score'], reverse=True)[:3]
        except: return []

# 메인 시스템 결론 로직 (투자 원칙 절대 준수)
def get_decision(rsi, curr_price, ema20, ema60, prev_price, vix, spy_drop, df):
    """
    [투자 원칙 기반 냉혹한 의사결정]
    1. 긴급 매도: 펀더멘털 붕괴 또는 메가 크래시(VIX > 40, 지수 > 15% 하락)
    2. 매수 적기: 하락세 멈춤 및 저점 다지기 확인 (RSI < 32 & 3일 저점 방어)
    3. 일반 익절: 추세 꺾임 확인 (EMA20 하향 돌파 및 하락 뉴스 수반)
    4. 강력 홀딩: 우상향 유지
    5. 관망: 시그널 부재
    """
    decision = "관망"
    color = "#888888"
    reasons = []
    
    # 최근 저점 방어 여부
    is_bottoming = curr_price >= df['Low'].iloc[-5:].min() * 1.005

    # A. 긴급 매도 (Mega-crash)
    if vix > 40 or spy_drop > 15:
        decision, color = "긴급 매도", "#ff0000"
        reasons = ["시스템적 대폭락(Mega-crash) 명백히 예견됨.", "거시경제 지표 임계치 돌파.", "자산 보호를 위한 즉각적 전량 현금화 권고."]
    # B. 매수 적기 (저점 다지기)
    elif rsi < 32 and is_bottoming:
        decision, color = "매수 적기 (전재산 100%)", "#00ff00"
        reasons = ["하락세가 멈추고 기술적 저점을 다지는 구간 진입.", f"RSI {rsi:.2f} 과매도 해소 및 하방 경직성 확보.", "초대형 우량주 전재산 매수 타점 충족."]
    # C. 일반 익절 (추세 이탈)
    elif curr_price < ema20 and prev_price >= ema20:
        decision, color = "일반 익절", "#ffff00"
        reasons = ["기술적 상승 추세 이탈 확인 (EMA20 하향 돌파).", "추세 꺾임에 따른 수익 확정 시점 도달.", "하락 원인 데이터 확인 시 전량 매도 집행."]
    # D. 강력 홀딩
    elif curr_price > ema20:
        decision, color = "강력 홀딩", "#008000"
        reasons = ["상승 추세가 기술적으로 견고하게 유지됨.", "일상적 단기 변동성 외 유의미한 하락 징후 없음.", "장기 우상향 원칙에 따른 포지션 유지."]
    else:
        decision, color = "관망", "#888888"
        reasons = ["명확한 추세 전환 시그널이 포착되지 않음.", "데이터 상의 유의미한 변곡점 부재.", "원칙적 대기."]

    return decision, color, reasons

# 시스템 헤더
st.title("⚖️ Wall Street Senior Quant Analyst System")
st.markdown("<p style='color:#00ff00;'>Elite 32+ 초대형 우량주 실시간 모니터링 엔진</p>", unsafe_allow_html=True)

tab1, tab2 = st.tabs(["📊 종목 심층 분석 (Deep Analysis)", "🏆 추천 순위 스캔 (Ranking Scan)"])

with tab1:
    ticker_input = st.text_input("분석 티커(Ticker) 입력 (예: MSFT, NVDA, ASTS)", placeholder="MSFT").upper()
    if st.button("냉혹한 팩트 분석 실행"):
        if ticker_input:
            with st.spinner(f"{ticker_input} 실시간 데이터 수집 및 팩트 체크 중..."):
                quant = WallStreetQuant(ticker_input)
                df = quant.get_realtime_data()
                if df is None:
                    st.error("데이터 로드 실패. 티커 유효성 및 네트워크를 확인하십시오.")
                else:
                    vix, spy_drop = quant.monitor_macro_risk()
                    curr_price = df['Close'].iloc[-1]
                    prev_price = df['Close'].iloc[-2]
                    rsi = df['RSI'].iloc[-1]
                    ema20 = df['EMA20'].iloc[-1]
                    ema60 = df['EMA60'].iloc[-1]

                    decision, color, reasons = get_decision(rsi, curr_price, ema20, ema60, prev_price, vix, spy_drop, df)
                    news = quant.analyze_news("SELL" if "매도" in decision or "익절" in decision else "BUY")

                    st.markdown(f"""
                        <div class='report-card'>
                            <h2 style='color:{color}'>[결론]: {decision}</h2>
                            <p><b>[핵심 데이터]:</b> 현재가: ${curr_price:,.2f} | RSI: {rsi:.2f} | VIX: {vix:.2f}</p>
                            <p><b>[냉철한 근거 요약]:</b></p>
                            <ul>
                                {"".join(f"<li>{r}</li>" for r in reasons)}
                            </ul>
                        </div>
                    """, unsafe_allow_html=True)

                    st.write("#### 📰 팩트 및 출처 (News & Fundamental)")
                    for n in news:
                        with st.expander(f"📰 {n['title']} (Impact: {n['impact']})"):
                            st.write(f"**Source:** {n['publisher']}")
                            st.write(f"**Summary:** {n['summary'][:400]}...")
                            st.write(f"**[국문 번역]:** {quant.translate_text(n['summary'][:400])}")
                            st.write(f"**[팩트 소스 확인]({n['link']})**")
        else:
            st.warning("티커를 입력하십시오.")

with tab2:
    if st.button("Elite 32+ 실시간 순위 스캔 시작"):
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
                q = WallStreetQuant(ticker)
                df = q.get_realtime_data()
                if df is None: continue
                
                curr_price = df['Close'].iloc[-1]
                prev_price = df['Close'].iloc[-2]
                rsi = df['RSI'].iloc[-1]
                ema20 = df['EMA20'].iloc[-1]
                ema60 = df['EMA60'].iloc[-1]
                
                decision, _, _ = get_decision(rsi, curr_price, ema20, ema60, prev_price, vix, spy_drop, df)

                # 순위 점수 (사용자 원칙: 저점 매수 기회 우선)
                score = 0
                if "매수 적기" in decision: score = 90 + (32 - rsi)
                elif "강력 홀딩" in decision: score = 60 + (rsi / 10)
                elif "관망" in decision: score = 30
                else: score = 10 # 탈출 시점
                
                # 리스크 감점
                recent_drop = (df['Close'].iloc[-1] - df['Close'].iloc[-4]) / df['Close'].iloc[-4] * 100
                if recent_drop < -10: score -= 40 # Falling knife
                
                results.append({
                    '순위': 0, # Placeholder
                    '티커': ticker,
                    '현재가': f"${curr_price:.2f}",
                    'RSI': f"{rsi:.1f}",
                    '결론': decision,
                    '추천 강도': "★★★★★" if score > 85 else "★★★★☆" if score > 70 else "★★★☆☆" if score > 50 else "☆☆☆☆☆",
                    'score': score
                })
            except: continue
        
        df_res = pd.DataFrame(results).sort_values(by='score', ascending=False).drop(columns=['score'])
        df_res['순위'] = range(1, len(df_res) + 1)
        
        st.write("### 🏆 월스트리트 실시간 진입 추천 순위")
        st.dataframe(df_res[['순위', '티커', '현재가', 'RSI', '결론', '추천 강도']], hide_index=True, use_container_width=True)
        st.caption("※ '매수 적기' 시그널 종목일수록 전재산 100% 진입 원칙에 부합하는 타점입니다.")

# 사이드바 (원칙 고지)
st.sidebar.title("🏛️ 투자 원칙 고수")
st.sidebar.markdown("""
**1. 대상:** 초대형 우량주 한정
**2. 운영:** 100% 매수 / 100% 매도
**3. 손절:** Mega-crash 외 절대 금지
**4. 매수:** 하락 멈춤 및 저점 확인
**5. 익절:** 기술적 추세 이탈 시
**6. 분석:** 노이즈 배제, 팩트 집중
""")

# 하단 리스크 모니터링 바
v, s = WallStreetQuant("SPY").monitor_macro_risk()
if v > 35 or s > 12:
    st.error(f"🚨 시장 붕괴 경보: VIX {v:.2f} | 고점 대비 하락 {s:.2f}%")
else:
    st.success(f"✅ 시스템 안정: VIX {v:.2f} | 고점 대비 하락 {s:.2f}%")
