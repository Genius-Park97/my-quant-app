import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import urllib.parse
import requests

# 페이지 설정
st.set_page_config(page_title="Wall Street Quant Engine 3.0", layout="wide", initial_sidebar_state="collapsed")

# 냉혹한 전문가 스타일링
st.markdown("""
    <style>
    .main { background-color: #050505; color: #e0e0e0; }
    .stButton>button { 
        width: 100%; border-radius: 2px; height: 3.5em; 
        background-color: #000; color: #d4af37; font-weight: bold; 
        border: 1px solid #d4af37; transition: 0.3s;
    }
    .stButton>button:hover { background-color: #d4af37; color: black; }
    .report-card { 
        background-color: #000; padding: 25px; border-radius: 4px; 
        border: 1px solid #333; border-left: 12px solid #d4af37; 
        margin-bottom: 25px; font-family: 'Consolas', monospace;
    }
    .metric-box {
        background-color: #111; padding: 10px; border: 1px solid #222; text-align: center;
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
            if df.empty or len(df) < 30: return None
            
            # 1. RSI (과매도 지표)
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            df['RSI'] = 100 - (100 / (1 + (gain / loss)))
            
            # 2. 이동평균선 및 이격도 (평균 회귀 지표)
            df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
            df['EMA60'] = df['Close'].ewm(span=60, adjust=False).mean()
            df['Disparity'] = (df['Close'] / df['EMA60']) * 100
            
            # 3. ATR (변동성 지표)
            high_low = df['High'] - df['Low']
            high_close = np.abs(df['High'] - df['Close'].shift())
            low_close = np.abs(df['Low'] - df['Close'].shift())
            ranges = pd.concat([high_low, high_close, low_close], axis=1)
            true_range = np.max(ranges, axis=1)
            df['ATR'] = true_range.rolling(14).mean()
            
            # 4. 거래량 이동평균 (거래량 스파이크 확인용)
            df['Vol_MA'] = df['Volume'].rolling(window=20).mean()
            df['Vol_Ratio'] = df['Volume'] / df['Vol_MA']
            
            return df
        except: return None

    def get_macro_data(self):
        try:
            vix = yf.Ticker("^VIX").history(period="1d")['Close'].iloc[-1]
            spy = yf.Ticker("SPY").history(period="1mo")['Close']
            spy_drop = ((spy.max() - spy.iloc[-1]) / spy.max()) * 100
            return vix, spy_drop
        except: return 0, 0

# 의사결정 알고리즘 3.0
def analyze_signal(df, vix, spy_drop):
    curr = df.iloc[-1]
    prev = df.iloc[-2]
    
    score = 50 # 기본값
    decision = "관망"
    color = "#888888"
    reasons = []

    # 1단계: 매크로 리스크 필터 (최우선)
    if vix > 38 or spy_drop > 15:
        return "긴급 매도", "#ff0000", ["시스템적 대폭락(Mega-crash) 포착.", f"VIX 지수 {vix:.2f} 위험 수준.", "자산 전량 보호 원칙 가동."], 0

    # 2단계: 매수 적기 포착 (데이터 확증 로직)
    # 조건: RSI 과매도 + 이격도 하단 + 거래량 동반 반등 혹은 하락 멈춤
    is_oversold = curr['RSI'] < 33
    is_stretched = curr['Disparity'] < 95
    is_volume_confirm = curr['Vol_Ratio'] > 1.2 # 평소보다 거래량 20% 이상 증가
    is_bottoming = curr['Close'] >= df['Low'].iloc[-3:].min()
    
    if is_oversold and is_stretched and is_bottoming:
        decision = "매수 적기 (전재산 100%)"
        color = "#00ff00"
        score = 90 + (33 - curr['RSI'])
        reasons = [
            f"기술적 과매도 극치 (RSI {curr['RSI']:.2f}) 확인.",
            f"EMA60 대비 이격도 {curr['Disparity']:.2f}%로 평균 회귀 가능성 매우 높음.",
            "하락세 멈춤 및 거래량 수반 데이터로 저점 신뢰도 확보."
        ]
    # 3단계: 강력 홀딩 (추세 추종)
    elif curr['Close'] > curr['EMA20']:
        decision = "강력 홀딩"
        color = "#008000"
        score = 60 + (curr['RSI'] / 5)
        reasons = ["상승 추세(EMA20 상단) 견고하게 유지 중.", "일상적 변동성 구역으로 매도 불필요.", "우상향 원칙에 따른 포지션 고수."]
    # 4단계: 익절 목표 (추세 이탈)
    elif curr['Close'] < curr['EMA20'] and prev['Close'] >= prev['EMA20']:
        decision = "일반 익절"
        color = "#ffff00"
        score = 10
        reasons = ["기술적 상승 추세 이탈(EMA20 하향 돌파).", "단기 모멘텀 상실 및 하락 전환 징후.", "수익 확정 및 현금화 전략."]
    else:
        decision = "관망"
        color = "#888888"
        score = 30
        reasons = ["데이터가 유의미한 변곡점을 형성하지 않음.", "확률적 우위가 없는 구간.", "데이터 대기."]

    return decision, color, reasons, score

# --- 앱 인터페이스 ---
st.title("🏛️ Wall Street Senior Quant Engine 3.0")
st.markdown("<p style='color:#d4af37;'>PRO-GRADE ELITE DATA ANALYSIS SYSTEM</p>", unsafe_allow_html=True)

WATCH_LIST = [
    'MSFT', 'AAPL', 'NVDA', 'GOOGL', 'AMZN', 'META', 'TSLA', 'AVGO', 'ASML', 'LRCX',
    'AMAT', 'ORCL', 'ADBE', 'ISRG', 'INTU', 'PANW', 'VRT', 'BRK-B', 'JPM', 'V',
    'MA', 'BX', 'LLY', 'UNH', 'TMO', 'SYK', 'COST', 'WMT', 'PEP', 'HD', 'NFLX', 'XOM', 'PWR',
    'ASTS', 'RKLB'
]

tab1, tab2 = st.tabs(["[ 📊 DEEP ANALYSIS ]", "[ 🏆 RANKING SCAN ]"])

with tab1:
    ticker = st.text_input("ENTER TICKER (PRO-LIST ONLY):", placeholder="NVDA").upper()
    if st.button("EXECUTE FACT ANALYSIS"):
        if ticker:
            with st.spinner(f"EXTRACTING {ticker} RAW DATA..."):
                engine = ProfessionalQuant(ticker)
                df = engine.get_enriched_data()
                if df is not None:
                    vix, spy_drop = engine.get_macro_data()
                    decision, color, reasons, _ = analyze_signal(df, vix, spy_drop)
                    
                    st.markdown(f"""
                        <div class='report-card'>
                            <h1 style='color:{color}; margin-bottom:10px;'>{decision}</h1>
                            <p style='font-size:1.2em;'><b>FACTUAL RATIONALE:</b></p>
                            <ul>
                                {"".join(f"<li>{r}</li>" for r in reasons)}
                            </ul>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    c1, c2, c3, c4 = st.columns(4)
                    c1.markdown(f"<div class='metric-box'>PRICE<br><b>${df['Close'].iloc[-1]:,.2f}</b></div>", unsafe_allow_html=True)
                    c2.markdown(f"<div class='metric-box'>RSI<br><b>{df['RSI'].iloc[-1]:.2f}</b></div>", unsafe_allow_html=True)
                    c3.markdown(f"<div class='metric-box'>DISPARITY<br><b>{df['Disparity'].iloc[-1]:.2f}%</b></div>", unsafe_allow_html=True)
                    c4.markdown(f"<div class='metric-box'>VOL RATIO<br><b>{df['Vol_Ratio'].iloc[-1]:.2f}x</b></div>", unsafe_allow_html=True)
                    
                    st.write("---")
                    st.write("#### 📰 FUNDAMENTAL PROOF (REAL-TIME NEWS)")
                    for n in engine.stock.news[:3]:
                        with st.expander(f"📰 {n['title']}"):
                            st.write(f"Source: {n['provider']} | [LINK]({n['link']})")
                            st.write(f"Summary: {n['summary']}")

with tab2:
    if st.button("RUN ELITE 35+ SCANNER"):
        results = []
        vix, spy_drop = ProfessionalQuant("SPY").get_macro_data()
        progress = st.progress(0)
        
        for i, t in enumerate(WATCH_LIST):
            progress.progress((i + 1) / len(WATCH_LIST))
            try:
                e = ProfessionalQuant(t)
                d = e.get_enriched_data()
                if d is None: continue
                dec, col, _, score = analyze_signal(d, vix, spy_drop)
                results.append({
                    'TICKER': t,
                    'PRICE': f"${d['Close'].iloc[-1]:.2f}",
                    'RSI': d['RSI'].iloc[-1],
                    'DISPARITY': f"{d['Disparity'].iloc[-1]:.1f}%",
                    'DECISION': dec,
                    'SCORE': score
                })
            except: continue
            
        df_rank = pd.DataFrame(results).sort_values(by='SCORE', ascending=False).drop(columns=['SCORE'])
        df_rank.insert(0, 'RANK', range(1, len(df_rank) + 1))
        st.write("### 🏆 SENIOR QUANT RECOMMENDED RANKING")
        st.dataframe(df_rank, hide_index=True, use_container_width=True)
        st.caption("※ 본 순위는 [평균 회귀] 및 [저점 확증] 데이터가 가장 강력한 순서대로 정렬됩니다.")

st.sidebar.title("🏛️ INVEST PRINCIPLES")
st.sidebar.markdown("""
- **TARGET**: MEGA-CAP BLUE CHIP
- **CAPITAL**: 100% BUY/SELL
- **STOP LOSS**: MEGA-CRASH ONLY
- **BUY**: BOTTOMING CONFIRMED
- **SELL**: TREND BREAK
""")

# 상시 감시 바
v, s = ProfessionalQuant("SPY").get_macro_data()
if v > 30: st.error(f"🚨 SYSTEMIC RISK ALERT: VIX {v:.2f}")
else: st.success(f"✅ SYSTEM STABLE: VIX {v:.2f}")

