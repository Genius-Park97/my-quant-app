import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import urllib.parse
import requests
import google.generativeai as genai
import json
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

    def analyze_news_with_ai(self, api_key):
        """Gemini AI를 활용하여 문맥 기반 호재/악재 분류 및 핵심 팩트 문장 추출"""
        fallback_news = [{
            'title': f"[{self.ticker}] 최근 주요 변동 사항 없음",
            'publisher': "System Analyst",
            'link': "#",
            'summary': "데이터를 가져올 수 없거나 펀더멘털을 훼손할 악재가 없습니다.",
            'key_sentence': "안정적인 상태가 유지되고 있습니다.",
            'impact': "⚪ 기타(중립)"
        }]

        try:
            news_list = self.stock.news
            if not news_list: return fallback_news
            
            # 종목 필터링 
            try: company_name = self.stock.info.get('shortName', self.ticker).split()[0].lower()
            except: company_name = self.ticker.lower()
            target_ids = [self.ticker.lower(), company_name]
            
            filtered_news = []
            for n in news_list:
                if len(filtered_news) >= 3: break
                title = n.get('content', n).get('title', '')
                summary = n.get('content', n).get('summary', '')
                full_text = (title + " " + summary).lower()
                
                # 티커나 기업명이 포함된 뉴스만 1차 통과
                if any(tid in full_text for tid in target_ids):
                    filtered_news.append(n)
            
            if not filtered_news: return fallback_news

            if not api_key:
                # API 키가 없으면 그냥 원래대로 추출
                return self._basic_news_extract(filtered_news)

            # AI 분석 시작
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            analyzed_results = []
            for n in filtered_news:
                content = n.get('content', n)
                title = content.get('title', '')
                summary = content.get('summary', '')
                publisher = content.get('provider', {}).get('displayName', 'Unknown Source')
                link = content.get('clickThroughUrl', {}).get('url', '#')
                
                prompt = f"""
                다음은 주식 '{self.ticker}'에 관한 뉴스입니다. 
                이 뉴스를 분석하여 다음의 JSON 포맷으로 답해주세요.
                
                [뉴스]
                제목: {title}
                요약: {summary}
                
                [요청 사항]
                1. impact: 이 뉴스가 주가에 미치는 영향을 문맥을 파악하여 결정하세요. 무조건 다음 세 가지 중 하나만 선택하세요: "🟢 호재", "🔴 악재", "⚪ 기타(중립)"
                2. key_sentence: 이 뉴스가 호재, 악재, 혹은 중립인 이유를 명확하게 팩트 기반으로 증명할 수 있는 '핵심 문장 1개(한국어 번역)'를 작성하세요. 쓸데없는 배경 설명 없이, 구체적인 수치나 결정적인 이유(예: 실적 달성 실패, 파트너십 체결 등)를 포함해야 합니다.
                
                [응답 형식 (JSON만 출력)]
                {{"impact": "선택된감성", "key_sentence": "핵심팩트문장"}}
                """
                
                try:
                    res = model.generate_content(prompt)
                    match = re.search(r'\{.*\}', res.text, re.DOTALL)
                    if match:
                        ai_data = json.loads(match.group())
                        analyzed_results.append({
                            'title': title,
                            'publisher': publisher,
                            'link': link,
                            'key_sentence': ai_data.get('key_sentence', '분석 실패'),
                            'impact': ai_data.get('impact', '⚪ 기타(중립)')
                        })
                    else:
                        analyzed_results.append(self._fallback_single_news(n))
                except:
                    analyzed_results.append(self._fallback_single_news(n))
            
            return analyzed_results if analyzed_results else fallback_news
            
        except Exception as e: 
            return fallback_news

    def _fallback_single_news(self, n):
        content = n.get('content', n)
        return {
            'title': content.get('title', ''),
            'publisher': content.get('provider', {}).get('displayName', 'Unknown'),
            'link': content.get('clickThroughUrl', {}).get('url', '#'),
            'key_sentence': content.get('summary', '')[:100] + "... (AI 분석 실패)",
            'impact': "⚪ 기타(중립)"
        }

    def _basic_news_extract(self, filtered_news):
        analyzed_news = []
        for n in filtered_news:
            content = n.get('content', n)
            analyzed_news.append({
                'title': content.get('title', ''),
                'publisher': content.get('provider', {}).get('displayName', 'Unknown Source'),
                'link': content.get('clickThroughUrl', {}).get('url', '#'),
                'key_sentence': content.get('summary', 'API 키를 입력하면 AI가 핵심 팩트를 추출합니다.'),
                'impact': "⚪ AI 연동 대기중"
            })
        return analyzed_news

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
    elif price > ema20 and prev['Close'] < prev['EMA20']:
        decision, color = "강력 홀딩 (반등장)", "#008000"
        dip_score = 30
        reasons = ["EMA20 단기 추세선 돌파. 수익 극대화 구간."]
    elif price > ema20:
        decision, color = "강력 홀딩", "#008000"
        dip_score = 10
        reasons = ["우상향 추세 진행 중."]
    elif price < ema20 and prev['Close'] >= prev['EMA20']:
        decision, color = "일반 익절", "#ff6600"
        dip_score = 0
        reasons = ["단기 상승 추세선(EMA20) 하향 돌파. 수익 확정 권고."]
    else:
        decision, color = "관망", "#888888"
        reasons = ["방향성이 뚜렷하지 않은 구간."]

    return decision, color, reasons, dip_score

# UI 렌더링
def render_analysis_ui(ticker, api_key):
    with st.spinner(f"'{ticker}' 기술적 지표 및 AI 뉴스 분석 중..."):
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
            st.write("#### 📰 AI 팩트 체크 및 투심 분석")
            news = engine.analyze_news_with_ai(api_key)
            for n in news:
                with st.expander(f"[{n['impact']}] {n['title']}", expanded=True):
                    st.write(f"**출처:** {n['publisher']}")
                    st.write(f"**AI 분석 핵심 팩트:** {n['key_sentence']}")
                    st.write(f"[원문 기사 보기]({n['link']})")
        else:
            st.error("데이터 로드 실패.")

# --- 앱 메인 ---
st.title("⚖️ Wall Street Quant: Buy The Dip Engine")
st.markdown("<p style='color:#00ff00;'>초우량주 전용 저점 포착 및 AI 뉴스 분석 터미널</p>", unsafe_allow_html=True)

# 상단에 API 키 입력란 추가 (뉴스 분석용)
api_key = st.text_input("Gemini API Key (뉴스 문맥 분석용):", type="password", placeholder="AI 뉴스 판별을 원하시면 키를 입력하세요")

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
            render_analysis_ui(ticker, api_key)

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
        
        st.write("---")
        st.subheader("🔍 순위권 종목 정밀 분석")
        selected_ticker = st.selectbox("위 순위표에서 정밀 분석할 티커를 선택하세요:", ["선택하세요"] + st.session_state.scan_results['TICKER'].tolist())
        
        if selected_ticker != "선택하세요":
            render_analysis_ui(selected_ticker, api_key)

# 리스크 체크 (사이드바 숨김 대신 하단 배치)
st.write("---")
v, s = ProfessionalQuant("SPY").get_macro_data()
if v > 35 or s > 15: st.error(f"🚨 시스템 폭락 경보: VIX {v:.2f}")
else: st.success(f"✅ 거시 경제 안정: VIX {v:.2f}")

