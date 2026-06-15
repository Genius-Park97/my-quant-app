import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import urllib.parse
import requests
import re

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
    .info-box {
        font-size: 0.85em; color: #888; margin-top: 15px; padding: 15px; 
        border: 1px dashed #333; background-color: #0a0a0a;
    }
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
            
            # 이동평균 및 이격도
            df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
            df['EMA60'] = df['Close'].ewm(span=60, adjust=False).mean()
            df['Disparity'] = (df['Close'] / df['EMA60']) * 100 
            
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

    def analyze_news_local(self):
        """외부 API(Gemini) 없이, 자체 룰베이스 알고리즘으로 뉴스 팩트 판별"""
        fallback_news = [{
            'title': f"[{self.ticker}] 특이 동향 없음",
            'publisher': "System Analyst",
            'link': "#",
            'summary': "펀더멘털을 훼손할 악재나 급격한 상승 모멘텀을 발생시킬 호재가 발견되지 않았습니다.",
            'key_sentence': f"{self.ticker} maintains stable trend.",
            'impact': "⚪ 기타(중립)"
        }]

        try:
            news_list = self.stock.news
            if not news_list: return fallback_news
            
            # 종목 필터링 
            try: company_name = self.stock.info.get('shortName', self.ticker).split()[0].lower()
            except: company_name = self.ticker.lower()
            target_ids = [self.ticker.lower(), company_name]
            
            # 강력한 팩트 기반 키워드 사전 (가중치 부여)
            pos_dict = {
                'surpass': 2, 'beat estimate': 3, 'upgrade': 2, 'record high': 2, 'raised guidance': 3, 
                'breakthrough': 2, 'fda approval': 3, 'awarded': 2, 'soar': 1, 'jumped': 1, 'outperform': 2, 'profit': 1
            }
            neg_dict = {
                'missed estimate': 3, 'downgrade': 2, 'lawsuit': 3, 'investigation': 3, 'layoff': 2, 
                'bankruptcy': 3, 'slump': 1, 'plunge': 1, 'cut guidance': 3, 'warning': 2, 'sued': 2, 'loss': 1
            }
            
            analyzed_results = []
            
            for n in news_list:
                if len(analyzed_results) >= 3: break
                
                content = n.get('content', n)
                title = content.get('title', '')
                summary = content.get('summary', '')
                full_text = (title + " " + summary).lower()
                publisher = content.get('provider', {}).get('displayName', 'Unknown Source')
                link = content.get('clickThroughUrl', {}).get('url', '#')
                
                # 1. 1차 필터링: 해당 종목 언급 여부
                if not any(tid in full_text for tid in target_ids): continue
                
                # 2. 자체 스코어링 로직
                pos_score = sum(weight for kw, weight in pos_dict.items() if kw in full_text)
                neg_score = sum(weight for kw, weight in neg_dict.items() if kw in full_text)
                
                # 3. 감성 결정 및 핵심 문장 추출
                sentences = summary.split('. ')
                if not sentences: sentences = [title]
                
                impact = "⚪ 기타(중립)"
                key_sentence = ""
                
                # 임계치(Threshold) 이상일 때만 호재/악재 판정 (모호한 것은 중립 처리)
                if pos_score > neg_score and pos_score >= 2:
                    impact = "🟢 호재"
                    # 호재 가중치가 높은 단어가 포함된 문장 우선 추출
                    for s in sentences:
                        if any(kw in s.lower() for kw in pos_dict.keys()):
                            key_sentence = s + "."
                            break
                    if not key_sentence: key_sentence = title
                elif neg_score > pos_score and neg_score >= 2:
                    impact = "🔴 악재"
                    for s in sentences:
                        if any(kw in s.lower() for kw in neg_dict.keys()):
                            key_sentence = s + "."
                            break
                    if not key_sentence: key_sentence = title
                else:
                    impact = "⚪ 기타(중립)"
                    # 중립 기사는 팩트 판단을 위해 '숫자'가 포함된 문장 추출
                    for s in sentences:
                        if any(char.isdigit() for char in s):
                            key_sentence = s + "."
                            break
                    if not key_sentence: key_sentence = sentences[0] + "." if sentences else title

                analyzed_results.append({
                    'title': title,
                    'publisher': publisher,
                    'link': link,
                    'summary': summary,
                    'key_sentence': key_sentence.strip(),
                    'impact': impact
                })
            
            return analyzed_results if analyzed_results else fallback_news
            
        except Exception as e: 
            return fallback_news

# 저점 매수 특화 의사결정
def analyze_dip_signal(df, vix, spy_drop):
    curr = df.iloc[-1]
    prev = df.iloc[-2]
    
    rsi = curr['RSI']
    disparity = curr['Disparity']
    price = curr['Close']
    ema20 = curr['EMA20']
    
    rsi_score = max(0, (45 - rsi) * 2.5) 
    disp_score = max(0, (100 - disparity) * 3) 
    
    recent_min = df['Low'].iloc[-5:].min()
    is_bottoming = price >= recent_min * 1.015
    bottom_bonus = 20 if is_bottoming else -20
    
    dip_score = min(100, max(0, rsi_score + disp_score + bottom_bonus))
    
    decision = "관망"
    color = "#888888"
    reasons = []

    if vix > 38 or spy_drop > 15:
        decision, color = "긴급 매도", "#ff0000"
        dip_score = 0
        reasons = ["시스템 대폭락 감지. 저점 매수 일시 중단."]
    elif dip_score >= 80 and is_bottoming:
        decision, color = "매수 적기 (100%)", "#00ff00"
        reasons = [
            f"RSI {rsi:.1f}의 극심한 과매도 상태.",
            f"EMA60 대비 이격도 {disparity:.1f}%로 가격 할인율 높음.",
            "하락세가 멈추고 저점 지지(Bottoming) 확인됨."
        ]
    elif dip_score >= 50:
        decision, color = "저점 진입 대기", "#ffff00"
        reasons = [f"할인 구간 진입(Dip Score {dip_score:.0f}점). 바닥 지지 대기 중."]
    elif price > ema20 and prev['Close'] <= prev['EMA20']:
        decision, color = "강력 홀딩 (반등장)", "#008000"
        dip_score = 30
        reasons = ["어제까지 EMA20 아래였으나, 오늘 상승 돌파 성공.", "하락 추세를 끝내고 본격적인 반등이 시작되는 초기 지점."]
    elif price > ema20:
        decision, color = "강력 홀딩", "#008000"
        dip_score = 10
        reasons = ["우상향 추세 안정적으로 진행 중."]
    elif price < ema20 and prev['Close'] >= prev['EMA20']:
        decision, color = "일반 익절", "#ff6600"
        dip_score = 0
        reasons = ["단기 상승 추세선(EMA20) 하향 돌파. 수익 확정 권고."]
    else:
        decision, color = "관망", "#888888"
        reasons = ["방향성이 뚜렷하지 않은 구간."]

    return decision, color, reasons, dip_score

# UI 렌더링
def render_analysis_ui(ticker):
    with st.spinner(f"'{ticker}' 기술적 지표 및 자체 엔진 뉴스 분석 중..."):
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
            
            # 지표 및 액션 설명 통합 박스
            st.markdown("""
            <div class='info-box'>
            <b>📊 주요 지표 설명</b><br>
            - <b>RSI</b>: 30 이하면 강력한 과매도(바닥) 상태.<br>
            - <b>이격도</b>: 100% 미만이면 장기 평균(60일선)보다 싸게 거래 중임을 의미.<br>
            - <b>Dip Score</b>: 과매도, 할인율, 바닥 지지 여부를 종합한 점수. 80점 이상 시 타점 유효.<br><br>
            <b>🚨 의사결정(ACTION) 기준</b><br>
            - <span style='color:#ff0000;'><b>긴급 매도</b></span>: 매크로 시스템 붕괴 (VIX 38↑ 등) 시 전량 현금화.<br>
            - <span style='color:#00ff00;'><b>매수 적기 (100%)</b></span>: 충분한 하락 후 저점 지지(Bottoming)가 확인된 최적의 100% 진입 타점.<br>
            - <span style='color:#ffff00;'><b>저점 진입 대기</b></span>: 주가가 할인 구간에 들어왔으나, 아직 하락세가 완전히 멈추지 않아 지지를 기다리는 상태.<br>
            - <span style='color:#008000;'><b>강력 홀딩 (반등장)</b></span>: 계속 하락하다가 방금 막 상승 추세선(EMA20)을 뚫고 올라온 '상승 초입' 구간.<br>
            - <span style='color:#008000;'><b>강력 홀딩</b></span>: 이미 반등하여 상승 추세(EMA20 상회)를 탔거나 안정적으로 유지 중인 상태 (보유자 영역).<br>
            - <span style='color:#ff6600;'><b>일반 익절</b></span>: 상승 추세선(EMA20)이 무너지며 단기 모멘텀이 꺾인 수익 확정 타점.<br>
            - <span style='color:#888888;'><b>관망</b></span>: 방향성이 모호한 중립 구간.
            </div>
            """, unsafe_allow_html=True)

            st.write("---")
            st.write("#### 📰 팩트 체크 및 투심 분석 (Engine Ver.)")
            news = engine.analyze_news_local()
            for n in news:
                with st.expander(f"[{n['impact']}] {n['title']}", expanded=True):
                    st.write(f"**출처:** {n['publisher']}")
                    st.write(f"**핵심 증거 문장:** {n['key_sentence']}")
                    st.write(f"**국문 번역:** {engine.translate_text(n['key_sentence'])}")
                    st.write(f"[원문 기사 보기]({n['link']})")
        else:
            st.error("데이터 로드 실패.")

# --- 앱 메인 ---
st.title("⚖️ Wall Street Quant: Buy The Dip Engine")
st.markdown("<p style='color:#00ff00;'>초우량주 전용 저점 포착 및 자체 팩트 체크 터미널</p>", unsafe_allow_html=True)

WATCH_LIST = [
    'MSFT', 'AAPL', 'NVDA', 'GOOGL', 'AMZN', 'META', 'TSLA', 'AVGO', 'ASML', 'LRCX',
    'AMAT', 'ORCL', 'ADBE', 'ISRG', 'INTU', 'PANW', 'VRT', 'BRK-B', 'JPM', 'V',
    'MA', 'BX', 'LLY', 'UNH', 'TMO', 'SYK', 'COST', 'WMT', 'PEP', 'HD', 'NFLX', 'XOM', 'PWR',
    'ASTS', 'RKLB'
]

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
            
        df_rank = pd.DataFrame(results).sort_values(by='DIP SCORE', ascending=False)
        df_rank['DISPARITY(%)'] = df_rank['DISPARITY(%)'].apply(lambda x: f"{x:.1f}%")
        df_rank['RSI'] = df_rank['RSI'].apply(lambda x: f"{x:.1f}")
        df_rank['DIP SCORE'] = df_rank['DIP SCORE'].apply(lambda x: f"{x:.1f}점")
        df_rank.insert(0, 'RANK', range(1, len(df_rank) + 1))
        
        st.session_state.scan_results = df_rank

    if st.session_state.scan_results is not None:
        st.dataframe(st.session_state.scan_results, hide_index=True, use_container_width=True)
        
        st.markdown("""
        <div class='info-box'>
        <b>📊 주요 지표 설명</b><br>
        - <b>RSI</b>: 30 이하면 강력한 과매도(바닥) 상태.<br>
        - <b>DISPARITY(%)</b>: 100% 미만이면 장기 평균(60일선)보다 싸게 거래 중임을 의미.<br>
        - <b>DIP SCORE</b>: 과매도, 할인율, 바닥 지지 여부를 종합한 점수. 80점 이상 시 타점 유효.<br><br>
        <b>🚨 의사결정(ACTION) 기준</b><br>
        - <span style='color:#ff0000;'><b>긴급 매도</b></span>: 매크로 시스템 붕괴 (VIX 38↑ 등) 시 전량 현금화.<br>
        - <span style='color:#00ff00;'><b>매수 적기 (100%)</b></span>: 하락 후 저점 지지(Bottoming)가 확인된 최적의 100% 진입 타점.<br>
        - <span style='color:#ffff00;'><b>저점 진입 대기</b></span>: 할인 구간에 들어왔으나, 아직 하락세가 멈추지 않아 지지를 기다리는 상태.<br>
        - <span style='color:#008000;'><b>강력 홀딩 (반등장)</b></span>: 어제까지 하락 추세였으나, 오늘 <b>상승 추세선(EMA20)을 뚫고 올라온 반등 초기 시점.</b><br>
        - <span style='color:#008000;'><b>강력 홀딩</b></span>: 이미 반등하여 상승 추세(EMA20 상회)를 탔거나 안정적으로 유지 중 (신규 진입 금지).<br>
        - <span style='color:#ff6600;'><b>일반 익절</b></span>: 상승 추세선(EMA20)이 무너지며 단기 모멘텀이 꺾인 수익 확정 타점.<br>
        - <span style='color:#888888;'><b>관망</b></span>: 방향성이 모호한 중립 구간.
        </div>
        """, unsafe_allow_html=True)
        
        st.write("---")
        st.subheader("🔍 순위권 종목 정밀 분석")
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

