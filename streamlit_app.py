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

# 대시보드 모듈 직접 사용
import dashboard as dash

# ─────────────────────────────────────────
# 설정
# ─────────────────────────────────────────
ASSETS = Path("assets")
CHAT_PLACEHOLDER = (
    "마케팅이 필요한 가맹점을 알려주세요\n"
    "(조회가능 예시: 동대*, 유유*, 똥파*, 본죽*, 본*, 원조*, 희망*, 혁이*, H커*, 케키*)"
)

# 데이터 경로
FRANCHISE_CSV   = "./data/franchise_data.csv"
BIZ_AREA_CSV    = "./data/biz_area.csv"
ADMIN_DONG_CSV  = "./data/admin_dong.csv"

# 챗봇 파이프라인
from my_agent.utils.adapters import run_one_turn

# ─────────────────────────────────────────
# Page Config & 스타일
# ─────────────────────────────────────────
st.set_page_config(
    page_title="2025 빅콘테스트 - AI 비밀상담소",
    layout="wide",
)

st.markdown("""
<style>
.block-container { max-width: 1100px; }
.stChatInput textarea {
    border-radius: 16px !important;
    padding: 14px 16px !important;
    font-size: 16px !important;
}
.stButton>button {
    width:100%;
    border-radius: 12px;
}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────
@st.cache_data
def load_image(name: str):
    try:
        return Image.open(ASSETS / name)
    except Exception:
        return None

def ensure_session_keys():
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = f"thread_{os.urandom(8).hex()}"
    if "current_page" not in st.session_state:
        st.session_state.current_page = "Home"

def clear_chat_history():
    st.session_state.messages = []
    st.session_state.thread_id = f"thread_{os.urandom(8).hex()}"

def render_chat_message(role: str, content: str):
    with st.chat_message(role):
        st.markdown(content.replace("<br>", " \n"))

def render_sources(snips: list, meta: dict | None = None, limit: int = 3):
    """웹 스니펫/출처 블록 렌더 (web_augment → postprocess 주입 결과를 UI로 표시)"""
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
            url   = s.get("url") or ""
            src   = s.get("source") or ""
            date  = s.get("published_at") or ""
            line  = f"- **{title}** · {src}"
            if date:
                line += f" · {date}"
            if url:
                st.markdown(f"{line} — [열기]({url})")
            else:
                st.markdown(line)
            snip = (s.get("snippet") or "").strip()
            if snip:
                st.write(f"  └ {snip}")

# ─────────────────────────────────────────
# 사이드바 (메뉴 & 공통)
# ─────────────────────────────────────────
ensure_session_keys()

with st.sidebar:
    logo = load_image("shc_ci_basic_00.png")
    if logo:
        st.image(logo, use_container_width=True)

    st.markdown("<p style='text-align: center;'>2025 Big Contest</p>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>AI DATA 활용분야</p>", unsafe_allow_html=True)
    st.write("")

    # 메뉴
    page = st.radio("메뉴", options=["Home", "Chatbot"], index=0 if st.session_state.current_page == "Home" else 1)
    st.session_state.current_page = page

    # Chatbot 전용: 새 대화 초기화
    if page == "Chatbot":
        st.button("🧹 새 대화 시작", help="챗봇 히스토리와 스레드를 초기화합니다.", on_click=clear_chat_history)

    with st.expander("🔧 디버그 정보"):
        st.write(f"현재 페이지: {st.session_state.current_page}")
        st.write(f"Thread ID: {st.session_state.get('thread_id', 'N/A')}")
        st.write(f"메시지 수: {len(st.session_state.get('messages', []))}")
        st.write(f"Web provider: {st.session_state.get('last_web_provider','N/A')}")

# ─────────────────────────────────────────
# 헤더 (공통)
# ─────────────────────────────────────────
st.title("신한카드 소상공인 🔑 비밀상담소")
st.subheader("#우리동네 #숨은맛집 #소상공인 #마케팅 #전략 .. 🤤")

hero_img = load_image("image_gen3.png")
if hero_img:
    st.image(hero_img, use_container_width=True, caption="🌀 머리아픈 마케팅 📊 어떻게 하면 좋을까?")

# ─────────────────────────────────────────
# Home 페이지
# ─────────────────────────────────────────
if st.session_state.current_page == "Home":

    st.markdown("### 🏠 Home · 가맹점 대시보드")

    dash_err_box = st.empty()
    try:
        # 데이터 로드
        fr, bz, ad = dash.load_all_data(FRANCHISE_CSV, BIZ_AREA_CSV, ADMIN_DONG_CSV)

        # 검색어 입력 + 결과 필터
        name_col = "가맹점명" if "가맹점명" in fr.columns else None
        c1, c2 = st.columns([3, 1])
        with c1:
            query = st.text_input("가맹점명 검색", placeholder="예: 본죽, 동대, 원조...", label_visibility="visible").strip()
        with c2:
            st.write("")  # spacing
            st.write("")

        # 옵션 구성 (검색어 필터 적용)
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

        # 컨텍스트 계산
        dfm, row_now, peers, tr_row, dn_row = dash.compute_context(fr, bz, ad, store_id)

        # KPI (2~6개)
        kpis = dash.build_kpi_figs(row_now, dfm, peers)
        if kpis:
            for i in range(0, len(kpis), 3):
                cols = st.columns(3)
                for fig, col in zip(kpis[i:i+3], cols):
                    with col:
                        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        # 상단 2열: 피라미드 / 레이더+미니바
        colL, colR = st.columns(2)
        with colL:
            st.markdown("##### 방문 고객 구조 (인구 피라미드)")
            st.plotly_chart(dash.build_pyramid(row_now, dn_row), use_container_width=True, config={"displayModeBar": False})

        with colR:
            st.markdown("##### 매장 vs 동종·동상권(동월 근사)")
            radar_fig, mini_bars_fig = dash.build_radar_and_minibars(row_now, peers)
            st.plotly_chart(radar_fig, use_container_width=True, config={"displayModeBar": False})
            st.plotly_chart(mini_bars_fig, use_container_width=True, config={"displayModeBar": False})

        # 하단 2열: 24개월 트렌드 / 격차 + 45° 편차
        colL2, colR2 = st.columns(2)
        with colL2:
            st.markdown("##### 24개월 트렌드 (매출·재방문·객단가)")
            st.plotly_chart(dash.build_trend_24m(dfm), use_container_width=True, config={"displayModeBar": False})

        with colR2:
            st.markdown("##### 격차(매장-피어평균) + 45° 편차(행정동 연령 vs 매장 방문연령)")
            st.plotly_chart(dash.build_gap_bar(row_now, peers), use_container_width=True, config={"displayModeBar": False})
            st.plotly_chart(dash.build_age_dev(row_now, dn_row), use_container_width=True, config={"displayModeBar": False})

        # 히트맵
        st.markdown("##### 요일 × 시간대 히트맵 (상권 기준, Z-정규화)")
        try:
            heatmap_fig = dash.build_heatmap(tr_row, kind="flow")
        except AttributeError:
            # 안전 폴백: dashboard에 build_heatmap 없을 때 (이전 버전 호환)
            import numpy as np  # noqa: F401
            st.write("히트맵은 대시보드 모듈 업데이트가 필요합니다.")
            heatmap_fig = go.Figure()

        st.plotly_chart(heatmap_fig, use_container_width=True, config={"displayModeBar": False})
        st.caption("© 상태만 보여주는 대시보드(데모) — 전략/추천 문구 없음")

    except Exception:
        dash_err_box.error("대시보드 렌더 중 오류가 발생했습니다. 콘솔 로그/트레이스를 확인하세요.")
        st.code("".join(traceback.format_exc()), language="python")

# ─────────────────────────────────────────
# Chatbot 페이지
# ─────────────────────────────────────────
else:
    st.markdown("### 🤖 Chatbot · 비밀상담")

    # Home에서 쓰이던 가맹점 컨텍스트는 여기서 사용하지 않음 (독립)
    # 메시지 히스토리 렌더
    for m in st.session_state.messages:
        role = "user" if isinstance(m, HumanMessage) else "assistant"
        render_chat_message(role, m.content)

    # 입력 & 처리
    if query := st.chat_input(CHAT_PLACEHOLDER):
        st.session_state.messages.append(HumanMessage(content=query))
        render_chat_message("user", query)

        with st.spinner("🔍 분석 중..."):
            try:
                # 가맹점 정보 없이 독립 동작 (store_name은 내부에서 처리)
                result = run_one_turn(
                    user_query=query,
                    store_name=query,
                    thread_id=st.session_state.thread_id,
                )
                status = result.get("status", "ok")

                if status == "need_clarify":
                    reply = result.get("final_response", "후보가 여러 개입니다.")
                    st.session_state.messages.append(AIMessage(content=reply))
                    render_chat_message("assistant", reply)

                    candidates = result.get("store_candidates", [])
                    if candidates:
                        with st.expander("가맹점 후보 목록"):
                            df = pd.DataFrame(candidates)
                            st.dataframe(df, use_container_width=True)

                elif status == "error":
                    error_msg = f"❌ {result.get('error', '알 수 없는 오류')}"
                    st.session_state.messages.append(AIMessage(content=error_msg))
                    render_chat_message("assistant", error_msg)

                else:
                    reply = result.get("final_response", "응답을 생성할 수 없습니다.")
                    st.session_state.messages.append(AIMessage(content=reply))
                    render_chat_message("assistant", reply)

                    # 웹 스니펫/출처 표시
                    web_snips = result.get("web_snippets") or result.get("state", {}).get("web_snippets")
                    web_meta  = result.get("web_meta") or result.get("state", {}).get("web_meta")
                    if web_snips:
                        st.session_state["last_web_provider"] = (web_meta or {}).get("provider_used", "auto")
                        render_sources(web_snips, web_meta, limit=3)

                    # 추천 액션
                    actions = result.get("actions", [])
                    if actions:
                        with st.expander("📋 추천 액션 플랜"):
                            for action in actions:
                                st.markdown(f"""
**{action.get('title', 'N/A')}** (우선순위 {action.get('priority', '-')})
- 카테고리: {action.get('category', '-')}
- 이유: {action.get('why', '-')}
""")
            except Exception as e:
                error_msg = f"⚠️ 처리 중 오류 발생: {str(e)}"
                st.session_state.messages.append(AIMessage(content=error_msg))
                render_chat_message("assistant", error_msg)
