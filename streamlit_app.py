# streamlit_app.py
# -*- coding: utf-8 -*-
"""
Streamlit UI (Home: Dashboard, Chatbot separated in sidebar menu)
- Home: 가맹점명 입력 → 선택된 가맹점 대시보드
- Chatbot: 가맹점 정보와 무관하게 독립 실행 + 새 대화 초기화
"""
# Windows 호환성 패치 (가장 먼저 실행)
import pathlib
import platform

# Windows에서 PosixPath 호환성 패치
if platform.system() == 'Windows':
    temp = pathlib.PosixPath
    pathlib.PosixPath = pathlib.WindowsPath


import os
from pathlib import Path
from PIL import Image
import traceback
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from langchain_core.messages import HumanMessage, AIMessage
from streamlit_option_menu import option_menu
import joblib
from autogluon.tabular import TabularPredictor

import dashboard as dash

# 설정
ASSETS = Path("assets")
CHAT_PLACEHOLDER = (
    "마케팅이 필요한 가맹점을 알려주세요\n"
    "(조회가능 예시: 동대*, 유유*, 똥파*, 본죽*, 본*, 원조*, 희망*, 혁이*, H커*, 케키*)"
)

from my_agent.utils.config import (
    FRANCHISE_CSV as _FRANCHISE,
    BIZ_AREA_CSV as _BIZAREA,
)

FRANCHISE_CSV = Path(_FRANCHISE).expanduser()
BIZ_AREA_CSV = Path(_BIZAREA).expanduser()

# 챗봇 파이프라인
from my_agent.utils.adapters import run_one_turn

# 타임시리즈 모델 로드 (캐싱)
@st.cache_resource
def load_predictor():
    """AutoGluon 예측 모델 로드"""
    try:
        return TabularPredictor.load("AutogluonModels/ag-20251018_185635")
    except Exception as e:
        st.error(f"모델 로드 실패: {e}")
        return None

@st.cache_resource
def load_label_encoder():
    """가맹점 ID 인코더 로드"""
    try:
        return joblib.load("data/label_encoder_store.pkl")
    except Exception as e:
        st.error(f"인코더 로드 실패: {e}")
        return None

@st.cache_data
def load_preprocessed_data():
    """전처리된 데이터 로드"""
    try:
        return pd.read_csv("data/preprocessed_df.csv")
    except Exception as e:
        st.error(f"데이터 로드 실패: {e}")
        return None

# 매출 구간 라벨 매핑
LABEL_MAP = {
    0: "6_90%초과(하위 10% 이하)",
    1: "5_75-90%",
    2: "4_50-75%",
    3: "3_25-50%",
    4: "2_10-25%",
    5: "1_10%이하"
}

# Page Config & 스타일
st.set_page_config(
    page_title="2025 빅콘테스트 - AI 비밀상담소",
    layout="wide",
)

BRAND_CSS = """
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard-dynamic-subset.css');

:root{
  --brand:#7c3aed;
  --brand-600:#5b21b6;
  --ink:#0b1220;
  --muted:#6b7280;
  --line:#e9d5ff;
  --surface:#faf5ff;
  --card:#ffffff;
}

html, body, * { 
  font-family: Pretendard, system-ui, -apple-system, Segoe UI, Roboto, sans-serif; 
}

/* 메인 컨테이너 최대 폭 */
.block-container{ 
  max-width:1120px; 
}

/* 메인 배경 */
main [data-testid="stAppViewContainer"]>.main{ 
  background: var(--surface); 
}

/* 상단 헤더 투명 */
[data-testid="stHeader"] { 
  background: transparent; 
}

/* 사이드바 배경 */
section[data-testid="stSidebar"]{
  background: #fff; 
  border-right: 1px solid var(--line);
}
section[data-testid="stSidebar"] .sidebar-content{ 
  padding:14px 12px 22px; 
}

/* 사용자 입력 박스 보라색 스타일 */
.stTextInput>div>input {
  border: 2px solid var(--brand);
  border-radius: 12px;
  padding: 8px 12px;
  outline: none;
  transition: all 0.2s ease;
}
.stTextInput>div>input:focus {
  border-color: var(--brand-600);
  box-shadow: 0 4px 12px rgba(124,58,237,0.25);
}

/* 라디오 버튼 (후보 매장 선택) */
div[role="radiogroup"] > label{
  display:flex; align-items:center; gap:10px;
  background:#fff; border:1px solid var(--line)!important;
  border-radius:999px!important; padding:10px 14px!important; margin-bottom:8px;
  font-weight:700; letter-spacing:-.2px; color:#111827;
  transition:all .15s ease;
}
div[role="radiogroup"] > label:hover{
  border-color: var(--brand)!important; 
  background:#f8f0ff;
}
div[role="radiogroup"] > label[data-checked="true"]{
  color:#fff; background:var(--brand); border-color:transparent!important;
  box-shadow:0 6px 16px rgba(124,58,237,0.22);
}

/* 카드 UI */
.ui-card{
  background:var(--card); border:1px solid var(--line); border-radius:18px; padding:18px;
  box-shadow:0 14px 30px rgba(124,58,237,0.08); margin-bottom:16px;
}
.ui-card h5{ 
  margin:0 0 10px; letter-spacing:-.2px; font-weight:900; 
}

/* Plotly 모드바 제거 */
.js-plotly-plot .modebar{ display:none !important; }

/* 기본 메뉴 및 푸터 숨김 */
#MainMenu{visibility:hidden} 
footer {visibility:hidden}

/* 버튼 스타일 */
.stButton>button{ 
  white-space:nowrap; 
}

/* 사용자 채팅 말풍선 */
.user-bubble{
  margin:8px 0 8px auto; max-width:780px;
  background:#f3e8ff; border:1px solid #e9d5ff;
  border-radius:14px 14px 4px 14px; padding:12px 14px;
  box-shadow:0 8px 18px rgba(124,58,237,.10);
  color:#0f172a; font-size:15px; line-height:1.45;
}

/* 사용자 아바타 숨김 */
[data-testid="chatAvatarIcon-user"], .stChatMessageAvatar:has([data-testid="chatAvatarIcon-user"]) { 
  display:none !important; 
}
</style>
"""


st.markdown(BRAND_CSS, unsafe_allow_html=True)
st.markdown("""
<style>
div[role="radiogroup"] > label > div:first-child{ display:unset !important; }
</style>
""", unsafe_allow_html=True)

# Helpers
@st.cache_data
def load_image(name: str):
    """assets/ 우선 → 폴백"""
    try:
        p = ASSETS / name
        if p.exists():
            return Image.open(p)
    except Exception:
        pass
    return None

def ensure_session_keys():
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = f"thread_{os.urandom(8).hex()}"
    if "current_page" not in st.session_state:
        st.session_state.current_page = "Home"
    if "pending_clarify" not in st.session_state:
        reset_clarify_state()

def clear_chat_history():
    st.session_state.messages = []
    st.session_state.thread_id = f"thread_{os.urandom(8).hex()}"
    reset_clarify_state()

def render_chat_message(role: str, content: str, idx: int):
    if role == "user":
        with st.chat_message("user", avatar=None):
            st.markdown(content, unsafe_allow_html=True)
    else:
        bee_path = str(ASSETS / "GPS.png")
        with st.chat_message("assistant", avatar=bee_path):
            st.markdown(content, unsafe_allow_html=True)

def render_sources(snips: list, meta: dict = None, limit: int = 3):
    snips = snips or []
    if not snips:
        return
    if meta:
        prov = meta.get("provider_used", "") or "auto"
        q = meta.get("query", "")
        st.caption(f"🔍 Web sources · provider={prov}" + (f", query=\"{q}\"" if q else ""))
    with st.expander("🔗 참고 출처", expanded=False):
        for s in snips[:limit]:
            title = s.get("title") or "(제목 없음)"
            url = s.get("url") or ""
            src = s.get("source") or ""
            date = s.get("published_at") or ""
            line = f"- **{title}** · {src}"
            if date: 
                line += f" · {date}"
            st.markdown(f"{line}" + (f" — [열기]({url})" if url else ""))
            snip = (s.get("snippet") or "").strip()
            if snip: 
                st.write(f"  └ {snip}")

def section(title: str, emoji: str = "✨"):
    st.markdown(
        f"<div class='ui-card' style='padding:14px 16px; margin-top:6px; margin-bottom:10px;'>"
        f"<div style='display:flex;align-items:center;gap:10px;'>"
        f"<div style='width:10px;height:10px;border-radius:3px;background:var(--brand);box-shadow:0 6px 16px rgba(27,86,255,.4)'></div>"
        f"<div style='font-weight:900;letter-spacing:-.2px'>{emoji} {title}</div>"
        f"</div></div>",
        unsafe_allow_html=True,
    )

def _candidate_label(c: dict) -> str:
    """후보 가맹점 라벨 생성"""
    name = c.get("가맹점명") or c.get("name") or "가맹점"
    addr = c.get("가맹점_주소") or c.get("address") or c.get("가맹점_지역") or c.get("region") or ""
    sid = c.get("가맹점_구분번호") or c.get("store_id") or c.get("MCT_KEY") or ""
    core = f"{name}" + (f" · {addr}" if addr else "")
    return f"{core}" + (f" (id={sid})" if sid else "")

def reset_clarify_state():
    st.session_state.pending_clarify = False
    st.session_state.clarify_candidates = []
    st.session_state.last_query_for_clarify = None
    st.session_state.clarify_selected_idx = 0
    st.session_state.last_web_snippets = None
    st.session_state.last_web_meta = None
    st.session_state.processing = False

def predict_next_month_sales(store_id: str, predictor, label_encoder, df_preprocessed):
    """다음 달 매출 구간 예측"""
    if not all([predictor, label_encoder, df_preprocessed is not None]):
        return None
    
    try:
        # 가맹점 ID 전처리: '___' 이후 부분 제거
        clean_store_id = store_id.split('___')[0] if '___' in store_id else store_id
        
        # 타임시리즈 데이터는 가맹점구분번호 사용
        store_col = None
        possible_names = ["가맹점구분번호", "가맹점_구분번호", "MCT_KEY", "store_id"]
        
        for col_name in possible_names:
            if col_name in df_preprocessed.columns:
                store_col = col_name
                break
        
        if not store_col:
            st.error(f"❌ 데이터 컬럼명 오류: 가맹점 ID 컬럼을 찾을 수 없습니다.")
            return None
        
        # label_encoder로 원본 ID를 숫자로 변환
        try:
            encoded_store_id = label_encoder.transform([clean_store_id])[0]
        except ValueError:
            st.warning(f"⚠️ 가맹점 ID `{clean_store_id}`가 학습 데이터에 없습니다.")
            return None

        # 인코딩된 ID로 데이터 필터링
        store_df = df_preprocessed[df_preprocessed[store_col] == encoded_store_id].sort_values("기준년월")
        
        if store_df.empty:
            st.warning(f"⚠️ 인코딩된 ID `{encoded_store_id}`에 해당하는 데이터가 없습니다.")
            return None
        
        latest_row = store_df.iloc[-1:].copy()
        
        # 예측에 불필요한 컬럼 제거
        drop_cols = ['매출금액_구간', '매핑용_상권명', '매핑용_업종', '기준년월', 'dt']
        latest_row = latest_row.drop(columns=drop_cols, errors='ignore')

        # 예측 수행
        pred_class = predictor.predict(latest_row).iloc[0]
        pred_proba_df = predictor.predict_proba(latest_row).iloc[0]

        pred_label = LABEL_MAP.get(int(pred_class), "알 수 없음")
        pred_prob = float(pred_proba_df[int(pred_class)])

        return {
            "predicted_class": int(pred_class),
            "predicted_label": pred_label,
            "predicted_probability": pred_prob
        }

    except Exception as e:
        st.error(f"❌ 예측 중 오류 발생: {str(e)}")
        return None

import streamlit as st
import time

# GPS 스타일 시각화 함수 (Streamlit 호환)
def render_gps_style_prediction(prediction):
    """GPS 스타일로 매출 예측 결과를 시각화"""

    # 구간별 정보 매핑
    level_info = {
        0: {"progress": 5, "emoji": "🔴", "color": "#ff4444", "status": "목표 대비 매우 부진", "icon": "🏁"},
        1: {"progress": 20, "emoji": "🟠", "color": "#ff8c42", "status": "목표 대비 부진", "icon": "🚗"},
        2: {"progress": 40, "emoji": "🟡", "color": "#ffd93d", "status": "목표 대비 보통", "icon": "🛣️"},
        3: {"progress": 62, "emoji": "🟢", "color": "#6bcf7f", "status": "목표 대비 양호", "icon": "🏙️"},
        4: {"progress": 82, "emoji": "🔵", "color": "#4d96ff", "status": "목표 대비 우수", "icon": "🌆"},
        5: {"progress": 95, "emoji": "🟣", "color": "#9b59b6", "status": "목표 초과 달성!", "icon": "🎯"}
    }

    info = level_info.get(prediction['predicted_class'], level_info[2])

    # 메인 예측 결과
    st.markdown(f"### 📊 다음달 예상 매출 구간")
    st.markdown(f"<p style='font-size:2rem; color:{info['color']}; font-weight:700;'> {prediction['predicted_label']}</p>", unsafe_allow_html=True)

    # GPS 스타일 진행도 바 + 애니메이션
    st.markdown(f"{info['icon']} {info['status']}")
    
    progress_bar = st.progress(0)
    progress_text = st.empty()
    
    for i in range(info['progress'] + 1):
        progress_bar.progress(i)
        progress_text.markdown(f"현재 위치: **{i}%** 도달")
        time.sleep(0.02)  # 애니메이션 속도 조절

    # 시작, 중간, 목표 표시
    st.markdown(
        """
        <div style='display:flex; justify-content:space-between; color:gray; font-size:0.9rem; margin-top:0.5rem;'>
            <span>🏁 시작</span>
            <span>🛣️ 중간</span>
            <span>🏆 목표</span>
        </div>
        """, 
        unsafe_allow_html=True
    )


# 사이드바
ensure_session_keys()
with st.sidebar:
    bee = load_image("GPS.png")
    if bee:
        st.image(bee, width=120)

    st.markdown(
        "<div style='font-weight:700;margin-top:8px'>2025 Big Contest · AI DATA</div>"
        "<div style='color:#6b7280;font-size:13px;margin-bottom:10px'>신한카드 소상공인 비밀상담소</div>",
        unsafe_allow_html=True,
    )

    choice = option_menu(
        menu_title=None,
        options=["Home", "Chatbot"],
        icons=["house", "chat-dots"],
        default_index=0 if st.session_state.current_page == "Home" else 1,
        styles={
            "container": {"padding": "0", "background": "#ffffff"},
            "icon": {"font-size": "16px"},
            "nav-link": {
                "font-weight": "700", "border-radius": "999px",
                "margin": "6px 0", "padding": "8px 14px"
            },
            "nav-link-selected": {"background-color": "#7c3aed", "color": "white"},
        },
    )
    st.session_state.current_page = choice

# Top Bar + 헤더
# 이미지 경로
logo_path = str(ASSETS / "logo.png")

# 이미지 출력
st.image(str(logo_path), width=150)  # width 조정 가능
st.caption("당신의 비즈니스가 어디에 있든, GPS는 늘 올바른 방향을 찾아드립니다.")

# Home 페이지
if st.session_state.current_page == "Home":
    section("Home · 가맹점 대시보드", "🏠")

    dash_err_box = st.empty()
    try:
        # 데이터 로드
        fr, bz = dash.load_all_data(FRANCHISE_CSV, BIZ_AREA_CSV)

        # 가맹점 구분코드 직접 입력
        if "MCT_KEY" not in fr.columns:
            raise KeyError("dashboard.load_all_data() 결과에 MCT_KEY 컬럼이 없습니다.")
        
        # 사용 가능한 가맹점 ID 목록
        available_store_ids = fr["MCT_KEY"].dropna().unique().tolist()
        
        # 샘플 ID 생성
        sample_ids = ", ".join(available_store_ids[:4]) if len(available_store_ids) >= 4 else ", ".join(available_store_ids[:2])
        
        # 입력값 검증 안내
        if "store_id_input_home" not in st.session_state or not st.session_state["store_id_input_home"].strip():
            st.info(f"🔍 (가맹점구분코드__가맹점명)을 입력해주세요. (총 {len(available_store_ids)}개 가맹점)")

            with st.expander("💡 사용 가능한 가맹점 코드 예시 (처음 20개)"):
                cols = st.columns(4)
                for i, sid in enumerate(available_store_ids[:20]):
                    cols[i % 4].code(sid)

        # 입력 박스
        store_id_input = st.text_input(
            "가맹점 검색",
            placeholder=f"예: {sample_ids}...",
            label_visibility="visible",
            key="store_id_input_home",
            help=f"사용 가능한 가맹점 총 {len(available_store_ids)}개"
        ).strip()

        # 입력값 검증 후 처리
        if not store_id_input:
            st.stop()

        # 대시보드용 store_id
        if store_id_input not in available_store_ids:
            st.warning(f"⚠️ 입력하신 가맹점 구분코드 `{store_id_input}`를 찾을 수 없습니다.")
            
            # 유사한 ID 찾기
            similar = [sid for sid in available_store_ids if store_id_input[:5] in str(sid)][:5]
            if similar:
                st.info("유사한 코드:")
                for sid in similar:
                    st.code(sid)
            else:
                st.info("💡 올바른 코드를 입력하거나 아래에서 확인해주세요.")
                with st.expander("사용 가능한 가맹점 코드 예시 (처음 20개)"):
                    cols = st.columns(4)
                    for i, sid in enumerate(available_store_ids[:20]):
                        cols[i % 4].code(sid)
            
            st.stop()
        
        store_id = store_id_input

        # 컨텍스트 계산
        dfm, row_now, peers, tr_row, _ = dash.compute_context(fr, bz, None, store_id)

        # KPI 카드들
        st.markdown("### 주요 지표")
        kpis = dash.build_kpi_figs(row_now, dfm, peers)

        if kpis:
            cols = st.columns(4, gap="small")
            for i, fig in enumerate(kpis[:4]):
                with cols[i]:
                    st.plotly_chart(fig, use_container_width=True,
                                    config={"displayModeBar": False})

        # 타임시리즈 예측 - GPS 스타일 적용
        st.markdown("---")
        section("AI기반 모델 예측", "🔮")
        
        predictor = load_predictor()
        label_encoder = load_label_encoder()
        df_preprocessed = load_preprocessed_data()
        
        if predictor and label_encoder and df_preprocessed is not None:
            try:
                with st.spinner("🔍 다음 달 매출을 예측하는 중..."):
                    import time
                    start_time = time.time()
                    prediction = predict_next_month_sales(
                        store_id=store_id,
                        predictor=predictor,
                        label_encoder=label_encoder,
                        df_preprocessed=df_preprocessed
                    )
                    elapsed_time = time.time() - start_time
                
                if prediction:
                    # GPS 스타일 시각화 렌더링
                    render_gps_style_prediction(prediction)
                else:
                    st.warning("⚠️ 해당 가맹점의 AI 예측을 수행할 수 없습니다.")
            except Exception as e:
                st.error(f"❌ 예측 실패: {str(e)}")

        st.markdown("---")

        # 핵심고객 Top3
        st.markdown("### 핵심고객 Top3")
        st.plotly_chart(dash.build_top3_fig(row_now), use_container_width=True, config={"displayModeBar": False})

        # 2열 레이아웃: 인구 피라미드 + 방사형
        st.markdown("---")
        colL, colR = st.columns([1, 1], gap="large")
        with colL:
            st.markdown("#### 방문 고객 구조 (인구 피라미드)")
            st.plotly_chart(dash.build_pyramid(row_now, None),
                            use_container_width=True, config={"displayModeBar": False})
        with colR:
            st.markdown("#### 매장 vs 동종·동상권 평균")
            radar_fig, mini_bars_fig = dash.build_radar_and_minibars(row_now, peers)
            st.plotly_chart(radar_fig, use_container_width=True, config={"displayModeBar": False})
            if mini_bars_fig is not None:
                st.plotly_chart(mini_bars_fig, use_container_width=True, config={"displayModeBar": False})

        # 두 그래프 아래 여백
        st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)

        # 2열 레이아웃: 24개월 트렌드
        st.markdown("---")
        st.markdown("#### 24개월 트렌드")
        st.plotly_chart(dash.build_trend_24m(dfm),
                        use_container_width=True, config={"displayModeBar": False})

        # 히트맵
        st.markdown("---")
        st.markdown("### 요일 × 시간대 히트맵 (상권별)")

        hm_kind = st.radio(
            "데이터 선택", ["유동인구", "매출"], horizontal=True, index=0,
            help="유동인구 혹은 매출 금액 기준으로 시간대-요일 패턴을 봅니다."
        )
        kind_key = "flow" if hm_kind == "유동인구" else "sales"
        heatmap_fig = dash.build_heatmap(tr_row, kind=kind_key)
        st.plotly_chart(heatmap_fig, use_container_width=True, config={"displayModeBar": False})
        

    except Exception:
        dash_err_box.error("대시보드 렌더 중 오류가 발생했습니다.")
        st.code("".join(traceback.format_exc()), language="python")

# Chatbot 페이지
else:
    # 보라색 버튼을 위한 CSS 추가
    st.markdown("""
        <style>
        div.stButton > button[kind="primary"] {
            background-color: #7c3aed !important;
            border-color: #7c3aed !important;
        }
        div.stButton > button[kind="primary"]:hover {
            background-color: #6d28d9 !important;
            border-color: #6d28d9 !important;
        }
        div.stButton > button[kind="primary"]:active {
            background-color: #5b21b6 !important;
            border-color: #5b21b6 !important;
        }
        </style>
    """, unsafe_allow_html=True)
    
    colL, colR = st.columns([6, 2])
    with colL:
        st.markdown("### 🤖 Chatbot · 비밀상담")
    with colR:
        st.button("🧹 새 대화 시작", use_container_width=True, on_click=clear_chat_history)

    # 기존 대화 렌더
    for i, m in enumerate(st.session_state.messages):
        role = "user" if isinstance(m, HumanMessage) else "assistant"
        render_chat_message(role, m.content, i)

    # Clarify UI
    if st.session_state.get("pending_clarify"):
        st.markdown("---")
        st.info("🔍 후보가 여러 개입니다. 지점을 선택해주세요.")

        cands = st.session_state.get("clarify_candidates") or []
        
        if not cands:
            st.error("❌ 후보 목록이 비어있습니다.")
            if st.button("🔄 초기화"):
                reset_clarify_state()
                st.rerun()
            st.stop()
        
        options = {i: _candidate_label(cands[i]) for i in range(len(cands))}
        
        selected_idx = st.radio(
            "가맹점 선택",
            options=list(options.keys()),
            format_func=lambda x: options[x],
            key="clarify_radio",
            index=0
        )

        if st.button("✅ 선택 완료", type="primary", use_container_width=True):
            picked = cands[selected_idx]
            label = options[selected_idx]
            last_q = st.session_state.get("last_query_for_clarify", "")

            store_id = str(picked.get("가맹점_구분번호", ""))
            
            st.session_state.messages.append(HumanMessage(content=f"→ {label}"))

            import time
            start_time = time.time()

            with st.spinner("🔍 당신의 나침반이 올바른 방향을 찾고 있어요..."):
                from my_agent.utils.adapters import run_one_turn_with_store
                
                re = run_one_turn_with_store(
                    user_query=last_q,
                    store_id=store_id,
                    thread_id=st.session_state.thread_id,
                )

            elapsed_time = time.time() - start_time

            status = re.get("status", "ok")
            if status == "error":
                err = re.get("error") or "알 수 없는 오류가 발생했습니다."
                st.session_state.messages.append(AIMessage(content=f"❌ {err}"))
            else:
                reply = re.get("final_response") or "응답을 생성할 수 없습니다."

                st.session_state.messages.append(AIMessage(content=reply))
                st.session_state.last_web_snippets = re.get("web_snippets") or re.get("state", {}).get("web_snippets")
                st.session_state.last_web_meta = re.get("web_meta") or re.get("state", {}).get("web_meta")

            reset_clarify_state()
            st.rerun()
        st.markdown("---")

    # 입력 처리
    if st.session_state.get("pending_clarify"):
        st.text_input("메시지 입력", placeholder="위에서 지점을 먼저 선택해주세요", disabled=True, key="disabled_input")
    else:
        if query := st.chat_input(CHAT_PLACEHOLDER):
            st.session_state.messages.append(HumanMessage(content=query))
            st.rerun()

    # 메시지 처리
    if (not st.session_state.get("pending_clarify") and 
        st.session_state.messages and 
        isinstance(st.session_state.messages[-1], HumanMessage) and
        not st.session_state.get("processing")):
        
        st.session_state.processing = True
        last_query = st.session_state.messages[-1].content

        import time
        start_time = time.time()

        with st.spinner("🔍 당신의 나침반이 올바른 방향을 찾고 있어요..."):
            try:
                result = run_one_turn(
                    user_query=last_query,
                    thread_id=st.session_state.thread_id,
                )
            except Exception as e:
                err = f"⚠️ 처리 중 오류 발생: {e}"
                st.session_state.messages.append(AIMessage(content=err))
                st.session_state.processing = False
                st.rerun()

        elapsed_time = time.time() - start_time
        status = result.get("status", "ok")

        if status == "need_clarify":
            st.session_state.pending_clarify = True
            st.session_state.clarify_candidates = result.get("store_candidates", []) or []
            st.session_state.last_query_for_clarify = last_query

            candidates = st.session_state.clarify_candidates
            if not candidates:
                # ✅ 후보 없음 → 오류 메시지로 처리
                err_msg = result.get("error") or result.get("message") or "검색 결과가 없습니다."
                reply = f"❌ {err_msg}"
                # clarify 모드 종료 (후보가 없으므로 선택 대기할 필요 없음)
                st.session_state.pending_clarify = False
            else:
                # ✅ 후보 있음 → 정상 후보 선택 모드
                reply = result.get("final_response") or "🔍 후보가 여러 개입니다. 지점을 선택해주세요."

            st.session_state.messages.append(AIMessage(content=reply))
            st.session_state.processing = False
            st.rerun()

        else:
            reply = result.get("final_response") or "응답을 생성할 수 없습니다."
            # time_footer 제거
            st.session_state.messages.append(AIMessage(content=reply))

            st.session_state.last_web_snippets = result.get("web_snippets") or result.get("state", {}).get("web_snippets")
            st.session_state.last_web_meta = result.get("web_meta") or result.get("state", {}).get("web_meta")

            st.session_state.processing = False
            st.rerun()