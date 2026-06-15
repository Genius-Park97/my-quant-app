import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import urllib.parse
import requests

# 페이지 설정
st.set_page_config(page_title="Quant Engine: Buy The Dip", layout="wide", initial_sidebar_state="collapsed")

# 월스트리트 퀀트 터미널 스타일링
st.markdown("""
    <style>
    .main { background-color: #050505; color: #e0e0e0; }
    .stButton>button { 
        width: 100%; border-radius: 0px; height: 3.5em; 
        background-color: #111; color: #00ff00; font-weight: bold; 
        border: 1px solid #00ff00; transition: 0.3s;
    }
    .stButton>button:hover { background-color: #00ff00; color: black; }
    .report-card { 
        background-color: #0a0a0a; padding: 25px; border-radius: 0px; 
        border: 1px solid #222; border-left: 8px solid #00ff00; 
        margin-bottom: 25px; font-family: 'Consolas', monospace;
    }
    .metric-box {
        background-color: #000; padding: 15px; border: 1px solid #333; text-align: center;
        border-radius: 4px;
    }
    .dip-score { font-size: 2em; font-weight: bold; color: #00ff00; }
    </style>
    """, unsafe_allow_html=True)

class ProfessionalQuant:
    def __init__(self, ticker):
        self.ticker = ticker.upper()
        self.stock = yf.Ticker(self.ticker)
        
    def get_enriched_data(self):
        try:
            df = self.stock.history(period="1y", interval="1d")
            if df.empty or len(df) < 60: return None
            
            # RSI 계산
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            df['RSI'] = 100 - (100 / (1 + (gain / loss)))
            
            # 이동평균 및 이격도 (EMA60 기준)
            df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
            df['EMA60'] = df['Close'].ewm(span=60, adjust=False).mean()
            df['Disparity'] = (df['Close'] / df['EMA60']) * 100 # 100 미만이면 60일선 아래 (저점 구간)
            
            return df
        except: return None

    def get_macro_data(self):
        try:
            vix = yf.Ticker("^VIX").history(period="1d")['Close'].iloc[-1]
            spy = yf.Ticker("SPY").history(period="1mo")['Close']
            spy_drop = ((spy.max() - spy.iloc[-1]) / spy.max()) * 100
            return vix, spy_drop
        except: return 0, 0

    def translate_text(self, text):
        try:
            url = f"https://api.mymemory.translated.net/get?q={urllib.parse.quote(text[:400])}&langpair=en|ko"
            response = requests.get(url, timeout=5)
            data = response.json()
            if data.get('responseStatus') == 200:
                return data.get('responseData').get('translatedText')
            return "번역 한도 초과 또는 일시적 오류"
        except: return "번역 서버 연결 실패"

    def analyze_news(self):
        # 뉴스가 아예 없는 상황을 방지하기 위한 기본 폴백(Fallback) 메시지 세팅
        fallback_news = [{
            'title': f"{self.ticker} 최근 주요 변동 사항 없음",
            'publisher': "System Analyst",
            'link': "#",
            'summary': "현재 시장에서 해당 종목의 펀더멘털을 훼손할 만한 치명적 악재나 급격한 호재가 포착되지 않았습니다.",
            'key_sentence': "No significant news reported recently. The fundamental remains stable.",
            'impact': "⚪ 기타(중립)"
        }]

        try:
            news_list = self.stock.news
            if not news_list: return fallback_news
            
            impact_keywords = ['crash', 'collapse', 'recession', 'slump', 'downfall', 'bankruptcy', 'bear market', 'inflation', 'rate hike', 'layoff', 'lawsuit', 'investigation', 'plunge', 'missed']
            positive_keywords = ['growth', 'breakthrough', 'dividend', 'buyback', 'partnership', 'earnings beat', 'upgrade', 'surge', 'record', 'soar']
            
            analyzed_news = []
            for n in news_list[:3]:
                content = n.get('content', n)
                title = content.get('title', '')
                summary = content.get('summary', '요약 정보 없음')
                provider = content.get('provider', {}).get('displayName', 'Unknown Source')
                link = content.get('clickThroughUrl', {}).get('url', '#')
                
                # 감성 분석 (호재/악재 판별)
                is_neg = any(kw in title.lower() or kw in summary.lower() for kw in impact_keywords)
                is_pos = any(kw in title.lower() or kw in summary.lower() for kw in positive_keywords)
                
                if is_pos: impact = "🟢 호재"
                elif is_neg: impact = "🔴 악재"
                else: impact = "⚪ 기타(중립)"
                
                # 핵심 문장 추출 (키워드가 포함된 문장 또는 첫 문장)
                sentences = summary.split('. ')
                key_sentence = next((s + "." for s in sentences if any(kw in s.lower() for kw in impact_keywords + positive_keywords)), sentences[0] + "." if sentences else title)
                
                analyzed_news.append({
                    'title': title,
                    'publisher': provider,
                    'link': link,
                    'summary': summary,
                    'key_sentence': key_sentence,
                    'impact': impact
                })
            
            return analyzed_news if analyzed_news else fallback_news
        except: 
            return fallback_news

# 저점 매수(Buy the Dip) 특화 의사결정 알고리즘
def analyze_dip_signal(df, vix, spy_drop):
    curr = df.iloc[-1]
    prev = df.iloc[-2]
    
    rsi = curr['RSI']
    disparity = curr['Disparity']
    price = curr['Close']
    ema20 = curr['EMA20']
    
    # 1. 저점 매수 매력도 (Dip Score) 계산 (100점 만점)
    rsi_score = max(0, (45 - rsi) * 2.5) 
    disp_score = max(0, (100 - disparity) * 3) 
    
    recent_min = df['Low'].iloc[-5:].min()
    is_bottoming = price >= recent_min * 1.015
    bottom_bonus = 20 if is_bottoming else -20
    
    dip_score = min(100, max(0, rsi_score + disp_score + bottom_bonus))
    
    # 2. 상태(Action) 결정
    decision = "관망"
    color = "#888888"
    reasons = []

    if vix > 38 or spy_drop > 15:
        decision, color = "긴급 매도", "#ff0000"
        dip_score = 0
        reasons = ["시스템 대폭락 감지. 저점 매수 원칙 일시 중단 및 현금화."]
    elif dip_score >= 80 and is_bottoming:
        decision, color = "매수 적기 (100%)", "#00ff00"
        reasons = [
            f"RSI {rsi:.1f}의 극심한 과매도 상태.",
            f"장기 이평선(EMA60) 대비 {100-disparity:.1f}% 할인된 가격 (이격도 {disparity:.1f}%).",
            "하락세가 멈추고 저점 지지(Bottoming)가 확인된 최적의 진입 타점."
        ]
    elif dip_score >= 50:
        decision, color = "저점 진입 대기", "#ffff00"
        reasons = [
            f"주가가 할인 구간에 진입함 (Dip Score: {dip_score:.1f}점).",
            "완벽한 바닥 지지가 확인될 때까지 100% 매수 대기."
        ]
    elif price > ema20 and prev['Close'] < prev['EMA20']:
        decision, color = "강력 홀딩 (반등장)", "#008000"
        dip_score = 30
        reasons = ["저점을 다지고 단기 추세선(EMA20)을 돌파함.", "보유자 영역. 수익 극대화."]
    elif price > ema20:
        decision, color = "강력 홀딩", "#008000"
        dip_score = 10
        reasons = ["우상향 추세 진행 중.", "신규 '저점 매수' 타점은 이미 지나감."]
    elif price < ema20 and prev['Close'] >= prev['EMA20']:
        decision, color = "일반 익절", "#ff6600"
        dip_score = 0
        reasons = ["단기 상승 추세(EMA20) 이탈.", "추세 꺾임에 따른 수익 확정 권고."]
    else:
        decision, color = "관망", "#888888"
        reasons = ["현재가와 지표가 애매한 중간 지대에 위치함."]

    return decision, color, reasons, dip_score

# 공통 분석 렌더링 함수
def render_analysis_ui(ticker):
    with st.spinner(f"'{ticker}' 데이터 추출 및 심층 분석 중..."):
        engine = ProfessionalQuant(ticker)
        df = engine.get_enriched_data()
        if df is not None:
            vix, spy_drop = engine.get_macro_data()
            decision, color, reasons, dip_score = analyze_dip_signal(df, vix, spy_drop)
            
            st.markdown(f"""
                <div class='report-card' style='border-left-color:{color};'>
                    <h1 style='color:{color}; margin-bottom:0px;'>{decision}</h1>
                    <p style='color:gray; font-size:0.9em;'>※ 100% 매매 원칙에 의거한 결론입니다.</p>
                    <p style='font-size:1.1em; margin-top:20px;'><b>[팩트 기반 근거]:</b></p>
                    <ul>
                        {"".join(f"<li>{r}</li>" for r in reasons)}
                    </ul>
                </div>
            """, unsafe_allow_html=True)
            
            c1, c2, c3, c4 = st.columns(4)
            c1.markdown(f"<div class='metric-box'>현재가<br><b>${df['Close'].iloc[-1]:,.2f}</b></div>", unsafe_allow_html=True)
            c2.markdown(f"<div class='metric-box'>RSI<br><b>{df['RSI'].iloc[-1]:.2f}</b></div>", unsafe_allow_html=True)
            c3.markdown(f"<div class='metric-box'>이격도(EMA60)<br><b>{df['Disparity'].iloc[-1]:.2f}%</b></div>", unsafe_allow_html=True)
            c4.markdown(f"<div class='metric-box'><b>저점 매력도 (Dip Score)</b><br><span class='dip-score'>{dip_score:.0f}점</span></div>", unsafe_allow_html=True)
            
            st.markdown("""
            <div style='font-size: 0.85em; color: #888; margin-top: 15px; padding: 10px; border: 1px dashed #333;'>
            <b>※ 지표 설명</b><br>
            - <b>RSI (Relative Strength Index)</b>: 30 이하일 경우 강력한 과매도(주가 바닥) 상태를 의미합니다.<br>
            - <b>이격도 (Disparity)</b>: 현재 주가가 장기 평균(60일선) 대비 얼마나 높은지/낮은지를 나타냅니다. 100% 미만이면 평균보다 싸게 거래 중임을 의미합니다.<br>
            - <b>Dip Score</b>: RSI, 이격도, 최근 바닥 지지 여부를 종합해 산출한 '저점 매수 타점 점수'입니다. 80점 이상 시 전재산 진입을 고려합니다.
            </div>
            """, unsafe_allow_html=True)

            st.write("---")
            st.write("#### 📰 뉴스 팩트 및 투심 분석")
            news = engine.analyze_news()
            for n in news:
                with st.expander(f"[{n['impact']}] {n['title']}", expanded=True):
                    st.write(f"**출처:** {n['publisher']}")
                    st.write(f"**핵심 문장(Key Sentence):** {n['key_sentence']}")
                    st.write(f"**번역(Translation):** {engine.translate_text(n['key_sentence'])}")
                    st.write(f"[원문 전체 보기]({n['link']})")
        else:
            st.error("데이터 로드 실패.")

# --- 앱 인터페이스 ---
st.title("⚖️ Wall Street Quant: Buy The Dip Engine")
st.markdown("<p style='color:#00ff00;'>초우량주 전용 저점 포착 및 대폭락 감시 터미널</p>", unsafe_allow_html=True)

WATCH_LIST = [
    'MSFT', 'AAPL', 'NVDA', 'GOOGL', 'AMZN', 'META', 'TSLA', 'AVGO', 'ASML', 'LRCX',
    'AMAT', 'ORCL', 'ADBE', 'ISRG', 'INTU', 'PANW', 'VRT', 'BRK-B', 'JPM', 'V',
    'MA', 'BX', 'LLY', 'UNH', 'TMO', 'SYK', 'COST', 'WMT', 'PEP', 'HD', 'NFLX', 'XOM', 'PWR',
    'ASTS', 'RKLB'
]

# 세션 상태 초기화 (랭킹 데이터 보존용)
if "scan_results" not in st.session_state:
    st.session_state.scan_results = None

tab1, tab2 = st.tabs(["[ 📊 개별 종목 저점 분석 ]", "[ 🏆 실시간 저점 매수 랭킹 ]"])

with tab1:
    ticker = st.text_input("분석 티커 입력 (예: MSFT, NVDA):", placeholder="NVDA").upper()
    if st.button("저점 타점 분석 실행"):
        if ticker:
            render_analysis_ui(ticker)

with tab2:
    st.markdown("### 🏆 가장 싸게 살 수 있는 초우량주 순위 (Dip Score 기준)")
    st.write("모든 초우량주(비전 및 장기 우상향이 검증된 종목) 중 현재 가장 깊은 조정(Dip)을 받고 바닥을 다지는 종목을 찾습니다.")
    
    if st.button("전체 종목 저점 스캔 실행"):
        results = []
        vix, spy_drop = ProfessionalQuant("SPY").get_macro_data()
        progress = st.progress(0)
        
        for i, t in enumerate(WATCH_LIST):
            progress.progress((i + 1) / len(WATCH_LIST))
            try:
                e = ProfessionalQuant(t)
                d = e.get_enriched_data()
                if d is None: continue
                dec, col, _, score = analyze_dip_signal(d, vix, spy_drop)
                results.append({
                    'TICKER': t,
                    'PRICE': f"${d['Close'].iloc[-1]:.2f}",
                    'RSI': d['RSI'].iloc[-1],
                    'DISPARITY(%)': d['Disparity'].iloc[-1],
                    'ACTION': dec,
                    'DIP SCORE': score
                })
            except: continue
            
        # Dip Score 기준으로 내림차순 정렬 (높을수록 저점 매수에 적합)
        df_rank = pd.DataFrame(results).sort_values(by='DIP SCORE', ascending=False)
        df_rank['DISPARITY(%)'] = df_rank['DISPARITY(%)'].apply(lambda x: f"{x:.1f}%")
        df_rank['RSI'] = df_rank['RSI'].apply(lambda x: f"{x:.1f}")
        df_rank['DIP SCORE'] = df_rank['DIP SCORE'].apply(lambda x: f"{x:.1f}점")
        df_rank.insert(0, 'RANK', range(1, len(df_rank) + 1))
        
        # 결과를 세션 스테이트에 저장
        st.session_state.scan_results = df_rank

    # 스캔 결과가 있으면 화면에 표시하고 연동 분석 기능 제공
    if st.session_state.scan_results is not None:
        st.dataframe(st.session_state.scan_results, hide_index=True, use_container_width=True)
        
        st.markdown("""
        <div style='font-size: 0.85em; color: #888; margin-top: 10px; padding: 10px; border: 1px dashed #333;'>
        <b>※ 항목 설명</b><br>
        - <b>RSI</b>: 낮을수록 하락 압력이 컸음(저점 가능성)을 의미합니다. (통상 30 이하 시 과매도)<br>
        - <b>DISPARITY(%)</b>: 60일 이동평균선 대비 현재 가격. 100% 미만은 장기 추세선보다 싸게 거래되고 있음을 나타냅니다.<br>
        - <b>DIP SCORE</b>: 과매도(RSI), 할인율(이격도), 하락세 진정(Bottoming)을 종합한 100점 만점의 점수. 높을수록 '매수 적기' 타점입니다.
        </div>
        """, unsafe_allow_html=True)
        
        st.write("---")
        st.subheader("🔍 순위권 종목 정밀 분석")
        
        # 순위표에서 티커를 선택하면 자동으로 심층 분석 렌더링
        selected_ticker = st.selectbox("위 순위표에서 정밀 분석할 티커를 선택하세요:", ["선택하세요"] + st.session_state.scan_results['TICKER'].tolist())
        
        if selected_ticker != "선택하세요":
            render_analysis_ui(selected_ticker)

st.sidebar.title("🏛️ INVEST PRINCIPLES")
st.sidebar.markdown("""
**[목적]**
비전이 훌륭하여 장기 우상향이 확실한 초대형 우량주의 **최적의 저점 매수(Buy the Dip)** 타이밍을 포착.

**[운칙]**
- **자금**: 무조건 전재산 100% 매수/매도
- **손절**: 대폭락(Mega-crash) 외 절대 금지
- **매수**: 하락 멈춤 및 저점 지지 확인 시
- **익절**: 기술적 상승 추세 꺾임 시
""")

# 상시 감시 바
v, s = ProfessionalQuant("SPY").get_macro_data()
if v > 35 or s > 15: st.error(f"🚨 시스템 폭락 경보: VIX {v:.2f}")
else: st.success(f"✅ 거시 경제 안정: VIX {v:.2f}")
