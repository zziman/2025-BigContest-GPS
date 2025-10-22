# streamlit_app.py
# -*- coding: utf-8 -*-
"""
Streamlit UI (Home: Dashboard, Chatbot separated in sidebar menu)
- Home: 가맹점명 입력 → 선택된 가맹점 대시보드
- Chatbot: 가맹점 정보와 무관하게 독립 실행 + 새 대화 초기화
"""

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

# ─────────────────────────────────────────
# 설정
# ─────────────────────────────────────────
ASSETS = Path("assets")
CHAT_PLACEHOLDER = (
    "마케팅이 필요한 가맹점을 알려주세요\n"
    "(조회가능 예시: 동대*, 유유*, 똥파*, 본죽*, 본*, 원조*, 희망*, 혁이*, H커*, 케키*)"
)

# config에서 그대로 가져오기
from my_agent.utils.config import (
    FRANCHISE_CSV as _FRANCHISE,
    BIZ_AREA_CSV as _BIZAREA,
)

FRANCHISE_CSV = Path(_FRANCHISE).expanduser()
BIZ_AREA_CSV = Path(_BIZAREA).expanduser()

# 챗봇 파이프라인
from my_agent.utils.adapters import run_one_turn

# ─────────────────────────────────────────
# 타임시리즈 모델 로드 (캐싱)
# ─────────────────────────────────────────
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

# ─────────────────────────────────────────
# Page Config & 스타일
# ─────────────────────────────────────────
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

html, body, * { font-family:Pretendard, system-ui, -apple-system, Segoe UI, Roboto, sans-serif; }
.block-container{ max-width:1120px; }
main [data-testid="stAppViewContainer"]>.main{ background:var(--surface); }
[data-testid="stHeader"] { background:transparent; }

section[data-testid="stSidebar"]{
  background:#fff; border-right:1px solid var(--line);
}
section[data-testid="stSidebar"] .sidebar-content{ padding:14px 12px 22px; }

div[role="radiogroup"] > label{
  display:flex; align-items:center; gap:10px;
  background:#fff; border:1px solid var(--line)!important;
  border-radius:999px!important; padding:10px 14px!important; margin-bottom:8px;
  font-weight:700; letter-spacing:-.2px; color:#111827;
  transition:all .15s ease;
}
div[role="radiogroup"] > label:hover{
  border-color:#e0c3ff!important; background:#f8f0ff;
}
div[role="radiogroup"] > label[data-checked="true"]{
  color:#fff; background:var(--brand); border-color:transparent!important;
  box-shadow:0 6px 16px rgba(124,58,237,0.22);
}

.ui-card{
  background:var(--card); border:1px solid var(--line); border-radius:18px; padding:18px;
  box-shadow:0 14px 30px rgba(124,58,237,0.08); margin-bottom:16px;
}
.ui-card h5{ margin:0 0 10px; letter-spacing:-.2px; font-weight:900; }

.js-plotly-plot .modebar{ display:none !important; }

#MainMenu{visibility:hidden} footer {visibility:hidden}

.stButton>button{ white-space:nowrap; }

.user-bubble{
  margin:8px 0 8px auto; max-width:780px;
  background:#f3e8ff; border:1px solid #e9d5ff;
  border-radius:14px 14px 4px 14px; padding:12px 14px;
  box-shadow:0 8px 18px rgba(124,58,237,.10);
  color:#0f172a; font-size:15px; line-height:1.45;
}

[data-testid="chatAvatarIcon-user"], .stChatMessageAvatar:has([data-testid="chatAvatarIcon-user"]) { display:none !important; }
</style>
"""

st.markdown(BRAND_CSS, unsafe_allow_html=True)
st.markdown("""
<style>
div[role="radiogroup"] > label > div:first-child{ display:unset !important; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────
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

def predict_next_month_sales(store_id: str, predictor, label_encoder, df_preprocessed):
    """다음 달 매출 구간 예측"""
    if not all([predictor, label_encoder, df_preprocessed is not None]):
        return None
    
    try:
        store_col = None
        possible_names = ["가맹점_구분번호", "가맹점구분번호", "MCT_KEY", "store_id"]
        
        for col_name in possible_names:
            if col_name in df_preprocessed.columns:
                store_col = col_name
                break
        
        if not store_col:
            return None
        
        try:
            encoded_store_id = label_encoder.transform([store_id])[0]
        except ValueError:
            return None

        store_df = df_preprocessed[df_preprocessed[store_col] == encoded_store_id].sort_values("기준년월")
        
        if store_df.empty:
            return None

        latest_row = store_df.iloc[-1:].copy()
        
        drop_cols = ['매출금액_구간', '매핑용_상권명', '매핑용_업종', '기준년월']
        latest_row = latest_row.drop(columns=drop_cols, errors='ignore')

        pred_class = predictor.predict(latest_row).iloc[0]
        pred_proba_df = predictor.predict_proba(latest_row).iloc[0]

        pred_label = LABEL_MAP.get(int(pred_class), "알 수 없음")
        pred_prob = float(pred_proba_df[int(pred_class)])

        return {
            "predicted_class": int(pred_class),
            "predicted_label": pred_label,
            "predicted_probability": pred_prob
        }

    except Exception:
        return None

# ─────────────────────────────────────────
# 사이드바
# ─────────────────────────────────────────
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

# ─────────────────────────────────────────
# Top Bar + 헤더
# ─────────────────────────────────────────
st.markdown("## GPS")
st.caption("당신의 비즈니스가 어디에 있든, GPS는 늘 올바른 방향을 찾아드립니다.")

# ─────────────────────────────────────────
# Home 페이지
# ─────────────────────────────────────────
if st.session_state.current_page == "Home":
    section("Home · 가맹점 대시보드", "🏠")

    dash_err_box = st.empty()
    try:
        # 데이터 로드
        fr, bz = dash.load_all_data(FRANCHISE_CSV, BIZ_AREA_CSV)

        # 검색어 입력
        name_col = "가맹점명" if "가맹점명" in fr.columns else None
        c1, _ = st.columns([3, 1])
        with c1:
            query = st.text_input("가맹점명 검색", placeholder="예: 본죽, 동대, 원조...", label_visibility="visible").strip()

        # 옵션 구성
        if "MCT_KEY" not in fr.columns:
            raise KeyError("dashboard.load_all_data() 결과에 MCT_KEY 컬럼이 없습니다.")

        df_opt = fr[["MCT_KEY", name_col]].drop_duplicates() if name_col else fr[["MCT_KEY"]].drop_duplicates()
        if query and name_col:
            df_opt = df_opt[df_opt[name_col].astype(str).str.contains(query, case=False, na=False)]

        if name_col:
            store_opts_df = df_opt.assign(
                label=lambda d: d[name_col] + " (" + d["MCT_KEY"].astype(str) + ")",
                value=lambda d: d["MCT_KEY"].astype(str),
            )
        else:
            store_opts_df = df_opt.assign(label=lambda d: d["MCT_KEY"], value=lambda d: d["MCT_KEY"])

        store_opts = store_opts_df[["label", "value"]].to_dict("records")
        if not store_opts:
            st.info("검색 결과가 없습니다. 다른 키워드를 입력해 보세요.")
            st.stop()

        # 선택 박스
        store_id = st.selectbox(
            "가맹점 선택",
            options=store_opts,
            index=0,
            format_func=lambda x: x["label"],
            key="store_picker_home",
        )["value"]

        # 컨텍스트 계산 (행정동 데이터 None)
        dfm, row_now, peers, tr_row, _ = dash.compute_context(fr, bz, None, store_id)

        # KPI 카드들
        st.markdown("### 주요 지표")
        kpis = dash.build_kpi_figs(row_now, dfm, peers)

        # KPI 카드 렌더 부분
        if kpis:
            cols = st.columns(4, gap="small")  # CHANGED: gap 추가
            for i, fig in enumerate(kpis[:4]):
                with cols[i]:
                    st.plotly_chart(fig, use_container_width=True,
                                    config={"displayModeBar": False})


        # 타임시리즈 예측
        st.markdown("---")
        section("다음 달 매출 예측 (AI 기반)", "🔮")
        
        predictor = load_predictor()
        label_encoder = load_label_encoder()
        df_preprocessed = load_preprocessed_data()
        
        if predictor and label_encoder and df_preprocessed is not None:
            available_ids = label_encoder.classes_
            
            if store_id not in available_ids:
                st.warning(f"⚠️ 선택된 가맹점({store_id})은 타임시리즈 학습 데이터에 포함되지 않았습니다.")
            else:
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
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric(
                            label="📊 예상 매출 구간",
                            value=prediction['predicted_label'],
                            delta=None
                        )
                    
                    with col2:
                        st.metric(
                            label="🎯 예측 확률",
                            value=f"{prediction['predicted_probability']*100:.1f}%",
                            delta=None
                        )
                    
                    with col3:
                        st.metric(
                            label="⏱️ 예측 시간",
                            value=f"{elapsed_time:.2f}초",
                            delta=None
                        )
                    
                    st.info("""
                    **💡 AI 예측 정보**
                    - AutoGluon 모델 기반 다음 달 매출 구간 예측
                    - 과거 매출 패턴, 고객 행동, 상권 데이터 종합 분석
                    - 예측 확률이 70% 이상일 때 신뢰도 높음
                    """)
                else:
                    st.warning("⚠️ 해당 가맹점의 AI 예측을 수행할 수 없습니다.")

        st.markdown("---")

        # 핵심고객 Top3
        st.markdown("### 핵심고객 Top3")
        st.plotly_chart(dash.build_top3_fig(row_now), use_container_width=True, config={"displayModeBar": False})

        # 2열 레이아웃: 인구 피라미드 + 방사형
        st.markdown("---")
        colL, colR = st.columns([1, 1], gap="large")  # CHANGED: gap="large"
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

        # 두 그래프 아래 여백 조금 더
        st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)  # CHANGED: 10px → 18px


        # 2열 레이아웃: 24개월 트렌드 + 격차
        st.markdown("---")
        st.markdown("#### 24개월 트렌드 (매출·재방문·객단가)")
        st.plotly_chart(dash.build_trend_24m(dfm),
                        use_container_width=True, config={"displayModeBar": False})

        # 히트맵
        st.markdown("---")
        st.markdown("### 요일 × 시간대 히트맵 (상권 기준, Z-정규화)")

        hm_kind = st.radio(
            "데이터 선택", ["유동인구", "매출"], horizontal=True, index=0,
            help="유동인구 혹은 매출 금액 기준으로 시간대-요일 패턴을 봅니다."
        )
        kind_key = "flow" if hm_kind == "유동인구" else "sales"  # CHANGED
        heatmap_fig = dash.build_heatmap(tr_row, kind=kind_key)
        st.plotly_chart(heatmap_fig, use_container_width=True, config={"displayModeBar": False})
        
        st.caption("© 상태만 보여주는 대시보드(데모) — 전략/추천 문구 없음")

    except Exception:
        dash_err_box.error("대시보드 렌더 중 오류가 발생했습니다.")
        st.code("".join(traceback.format_exc()), language="python")

# ─────────────────────────────────────────
# Chatbot 페이지
# ─────────────────────────────────────────
else:
    colL, colR = st.columns([6, 2])
    with colL:
        st.markdown("### 🤖 Chatbot · 비밀상담")
    with colR:
        st.button("🧹 새 대화 시작", use_container_width=True, on_click=clear_chat_history)

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

            with st.spinner("🔍 선택하신 지점을 분석 중..."):
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
                time_footer = f"\n\n---\n⏱️ 응답 생성 시간: **{elapsed_time:.1f}초**"
                reply_with_time = reply + time_footer
                st.session_state.messages.append(AIMessage(content=reply_with_time))

                st.session_state.last_web_snippets = re.get("web_snippets") or re.get("state", {}).get("web_snippets")
                st.session_state.last_web_meta = re.get("web_meta") or re.get("state", {}).get("web_meta")

            reset_clarify_state()
            st.rerun()
        st.markdown("---")

    # 기존 대화 렌더
    for i, m in enumerate(st.session_state.messages):
        role = "user" if isinstance(m, HumanMessage) else "assistant"
        render_chat_message(role, m.content, i)

    # 웹 출처
    if (st.session_state.messages and isinstance(st.session_state.messages[-1], AIMessage)
        and st.session_state.get("last_web_snippets")):
        render_sources(
            st.session_state.last_web_snippets,
            st.session_state.get("last_web_meta"),
            limit=3
        )

    # 입력 처리
    if st.session_state.get("pending_clarify"):
        st.text_input("메시지 입력", placeholder="위에서 지점을 먼저 선택해주세요", disabled=True, key="disabled_input")
    else:
        if query := st.chat_input(CHAT_PLACEHOLDER):
            st.session_state.messages.append(HumanMessage(content=query))

            import time
            start_time = time.time()

            with st.spinner("🔍 분석 중..."):
                try:
                    result = run_one_turn(
                        user_query=query,
                        thread_id=st.session_state.thread_id,
                    )
                except Exception as e:
                    err = f"⚠️ 처리 중 오류 발생: {e}"
                    st.session_state.messages.append(AIMessage(content=err))
                    st.rerun()

            elapsed_time = time.time() - start_time
            status = result.get("status", "ok")

            if status == "need_clarify":
                st.session_state.pending_clarify = True
                st.session_state.clarify_candidates = result.get("store_candidates", []) or []
                st.session_state.last_query_for_clarify = query

                reply = result.get("final_response") or "후보가 여러 개입니다. 지점을 선택해주세요."
                st.session_state.messages.append(AIMessage(content=reply))
                st.rerun()

            elif status == "error":
                err = result.get("error") or "알 수 없는 오류가 발생했습니다."
                st.session_state.messages.append(AIMessage(content=f"❌ {err}"))
                st.rerun()

            else:
                reply = result.get("final_response") or "응답을 생성할 수 없습니다."
                time_footer = f"\n\n---\n⏱️ 응답 생성 시간: **{elapsed_time:.1f}초**"
                reply_with_time = reply + time_footer
                st.session_state.messages.append(AIMessage(content=reply_with_time))

                st.session_state.last_web_snippets = result.get("web_snippets") or result.get("state", {}).get("web_snippets")
                st.session_state.last_web_meta = result.get("web_meta") or result.get("state", {}).get("web_meta")

                st.rerun()