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

# 저점 매수(Buy the Dip) 특화 의사결정 알고리즘
def analyze_dip_signal(df, vix, spy_drop):
    curr = df.iloc[-1]
    prev = df.iloc[-2]
    
    rsi = curr['RSI']
    disparity = curr['Disparity']
    price = curr['Close']
    ema20 = curr['EMA20']
    
    # 1. 저점 매수 매력도 (Dip Score) 계산 (100점 만점)
    # 우량주는 언젠가 오른다는 전제하에, "얼마나 싸게, 안전하게 살 수 있는가?"를 수치화
    
    # RSI 점수 (RSI가 45 이하일 때부터 점수 부여, 낮을수록 고득점)
    rsi_score = max(0, (45 - rsi) * 2.5) 
    
    # 이격도 점수 (EMA60선 아래로 떨어질수록 고득점, 즉 100% 미만일 때)
    disp_score = max(0, (100 - disparity) * 3) 
    
    # 바닥 확인 가점 (떨어지는 칼날 피하기)
    recent_min = df['Low'].iloc[-5:].min()
    is_bottoming = price >= recent_min * 1.015 # 최근 5일 최저점 대비 1.5% 이상 반등했는가?
    bottom_bonus = 20 if is_bottoming else -20 # 아직 하락 중이면 감점
    
    # 총점 계산
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
        dip_score = 30 # 이미 올랐으므로 신규 매수 점수는 낮음
        reasons = ["저점을 다지고 단기 추세선(EMA20)을 돌파함.", "보유자 영역. 수익 극대화."]
    elif price > ema20:
        decision, color = "강력 홀딩", "#008000"
        dip_score = 10 # 고점 영역
        reasons = ["우상향 추세 진행 중.", "신규 '저점 매수' 타점은 이미 지나감."]
    elif price < ema20 and prev['Close'] >= prev['EMA20']:
        decision, color = "일반 익절", "#ff6600"
        dip_score = 0
        reasons = ["단기 상승 추세(EMA20) 이탈.", "추세 꺾임에 따른 수익 확정 권고."]
    else:
        decision, color = "관망", "#888888"
        reasons = ["현재가와 지표가 애매한 중간 지대에 위치함."]

    return decision, color, reasons, dip_score

# --- 앱 인터페이스 ---
st.title("⚖️ Wall Street Quant: Buy The Dip Engine")
st.markdown("<p style='color:#00ff00;'>초우량주 전용 저점 포착 및 대폭락 감시 터미널</p>", unsafe_allow_html=True)

WATCH_LIST = [
    'MSFT', 'AAPL', 'NVDA', 'GOOGL', 'AMZN', 'META', 'TSLA', 'AVGO', 'ASML', 'LRCX',
    'AMAT', 'ORCL', 'ADBE', 'ISRG', 'INTU', 'PANW', 'VRT', 'BRK-B', 'JPM', 'V',
    'MA', 'BX', 'LLY', 'UNH', 'TMO', 'SYK', 'COST', 'WMT', 'PEP', 'HD', 'NFLX', 'XOM', 'PWR',
    'ASTS', 'RKLB'
]

tab1, tab2 = st.tabs(["[ 📊 개별 종목 저점 분석 ]", "[ 🏆 실시간 저점 매수 랭킹 ]"])

with tab1:
    ticker = st.text_input("분석 티커 입력 (예: MSFT, NVDA):", placeholder="NVDA").upper()
    if st.button("저점 타점 분석 실행"):
        if ticker:
            with st.spinner("데이터 추출 및 Dip Score 계산 중..."):
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
                    
                    st.write("---")
                    st.write("#### 📰 뉴스 팩트 체크")
                    try:
                        for n in engine.stock.news[:3]:
                            with st.expander(f"📰 {n.get('content', n).get('title', '제목 없음')}"):
                                st.write(n.get('content', n).get('summary', '요약 없음'))
                                st.write(f"[원문 링크]({n.get('content', n).get('clickThroughUrl', {}).get('url', '#')})")
                    except: st.write("뉴스 데이터를 불러오지 못했습니다.")
                else:
                    st.error("데이터 로드 실패.")

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
        
        st.dataframe(df_rank, hide_index=True, use_container_width=True)
        st.caption("※ 이격도가 100% 미만이고 RSI가 낮을수록 점수가 높습니다. '매수 적기' 시그널이 뜬 상위 종목에 전재산 100% 진입을 고려하십시오.")

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
