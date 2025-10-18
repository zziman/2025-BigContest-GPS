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
from streamlit_chat import message as chat_bubble

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
# Page Config & 스타일 (브랜딩 강화를 위한 커스텀)
# ─────────────────────────────────────────
st.set_page_config(
    page_title="2025 빅콘테스트 - AI 비밀상담소",
    layout="wide",
)

BRAND_CSS = """
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard-dynamic-subset.css');

:root{
  /* 🔶 오렌지 브랜드 팔레트 */
  --brand:#ff6a00;          /* 주황(메인) */
  --brand-600:#cc5600;      /* 진한 주황 */
  --ink:#0b1220;
  --muted:#6b7280;
  --line:#ffe5cc;           /* 라이트 오렌지 보더 */
  --surface:#fff8f1;        /* 배경 라이트 오렌지 */
  --card:#ffffff;
}

html, body, * { font-family:Pretendard, system-ui, -apple-system, Segoe UI, Roboto, Apple SD Gothic Neo, Noto Sans KR, sans-serif; }
.block-container{ max-width:1120px; }
main [data-testid="stAppViewContainer"]>.main{ background:var(--surface); }
[data-testid="stHeader"] { background:transparent; }

/* ─ Sidebar ─ */
section[data-testid="stSidebar"]{
  background:#fff; border-right:1px solid var(--line);
}
section[data-testid="stSidebar"] .sidebar-content{ padding:14px 12px 22px; }

/* 카드 느낌 유지, 컬러만 오렌지화 */
.sb-card{
  background:linear-gradient(180deg,#fff3e6 0%, #ffffff 100%);
  border:1px solid #ffe3c4; border-radius:18px; padding:12px; text-align:center;
  box-shadow: 0 6px 18px rgba(255,106,0,0.08);
}

/* 사이드바 메뉴: 필 네비게이션 */
div[role="radiogroup"] > label > div:first-child{ display:none !important; }
div[role="radiogroup"] > label{
  display:flex; align-items:center; gap:10px;
  background:#fff; border:1px solid var(--line)!important;
  border-radius:999px!important; padding:10px 14px!important; margin-bottom:8px;
  font-weight:700; letter-spacing:-.2px; color:#111827;
  transition:all .15s ease;
}
div[role="radiogroup"] > label:hover{
  border-color:#ffd6b0!important; background:#fff7ef;
}
div[role="radiogroup"] > label[data-checked="true"]{
  color:#fff; background:var(--brand); border-color:transparent!important;
  box-shadow:0 6px 16px rgba(255,106,0,0.22);
}

/* TopBar */
.topbar{ position:sticky; top:0; z-index:20; backdrop-filter:blur(8px);
  background:rgba(255,255,255,.85); border-bottom:1px solid var(--line); padding:10px 8px; }
.topbar-inner{ display:flex; align-items:center; gap:10px; }
.top-logo{ display:flex; align-items:center; gap:10px; font-weight:900; letter-spacing:-.3px; }
.top-tabs{ margin-left:auto; display:flex; gap:6px; }
.top-tab{ padding:8px 12px; border:1px solid var(--line); border-radius:12px; font-weight:800; color:#111827; }
.top-tab.active{ color:#fff; background:var(--brand); border-color:transparent; box-shadow:0 8px 18px rgba(255,106,0,0.25); }

/* Hero 제거 유지 */
.hero{ display:none; }

/* 카드 */
.ui-card{
  background:var(--card); border:1px solid var(--line); border-radius:18px; padding:18px;
  box-shadow:0 14px 30px rgba(255,106,0,0.07); margin-bottom:16px;
}
.ui-card h5{ margin:0 0 10px; letter-spacing:-.2px; font-weight:900; }

/* Plotly 모드바 숨김 */
.js-plotly-plot .modebar{ display:none !important; }

/* Footer/Menu 숨김 */
#MainMenu{visibility:hidden} footer {visibility:hidden}

/* 사이드바 캐릭터 이미지 크기 */
.sb-card img{ max-width:120px !important; margin:auto; display:block; }

/* 버튼 줄바꿈 방지 */
.stButton>button{ white-space:nowrap; }

/* 사용자 버블 (오렌지 톤) */
.user-bubble{
  margin:8px 0 8px auto; max-width:780px;
  background:#fff1e6; border:1px solid #ffe3c4;
  border-radius:14px 14px 4px 14px; padding:12px 14px;
  box-shadow:0 8px 18px rgba(255,106,0,.08);
  color:#0f172a; font-size:15px; line-height:1.45;
}

/* streamlit-chat: 사용자 아바타 숨김 */
.user-avatar, div[data-testid="stChatMessage"] .user-avatar { display:none !important; }
div[data-testid="stChatMessage"] img[alt="user"], 
div[data-testid="stChatMessage"] .stChatMessageAvatar:is(:has(img[alt="user"]), .user) { display:none !important; }
[data-testid="chatAvatarIcon-user"], .stChatMessageAvatar:has([data-testid="chatAvatarIcon-user"]) { display:none !important; }
</style>
"""



st.markdown(BRAND_CSS, unsafe_allow_html=True)


# ─────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────
@st.cache_data
def load_image(name: str):
    """assets/ 우선 → 첨부 경로 폴백"""
    try:
        p = ASSETS / name
        if p.exists():
            return Image.open(p)
    except Exception:
        pass
    # 폴백: 사용자가 올린 이미지(컨테이너 경로)
    try:
        return Image.open("/mnt/data/ba00f8a3-3cf3-4d91-80ef-cbd950591f45.png")
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


def render_chat_message(role: str, content: str, idx: int):
    if role == "user":
        # 사용자 아바타 제거
        with st.chat_message("user", avatar=None):  # or avatar="" 
            st.markdown(content, unsafe_allow_html=True)
    else:
        # 봇은 GPS.png 사용
        bee_path = str(ASSETS / "GPS.png")
        with st.chat_message("assistant", avatar=bee_path):
            st.markdown(content, unsafe_allow_html=True)
    

def render_sources(snips: list, meta: dict | None = None, limit: int = 3):
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
            if date: line += f" · {date}"
            st.markdown(f"{line}" + (f" — [열기]({url})" if url else ""))
            snip = (s.get("snippet") or "").strip()
            if snip: st.write(f"  └ {snip}")

def section(title: str, emoji: str="✨"):
    st.markdown(
        f"<div class='ui-card' style='padding:14px 16px; margin-top:6px; margin-bottom:10px;'>"
        f"<div style='display:flex;align-items:center;gap:10px;'>"
        f"<div style='width:10px;height:10px;border-radius:3px;background:var(--brand);box-shadow:0 6px 16px rgba(27,86,255,.4)'></div>"
        f"<div style='font-weight:900;letter-spacing:-.2px'>{emoji} {title}</div>"
        f"</div></div>",
        unsafe_allow_html=True,
    )

def badge(text: str, tone: str="brand"):
    colors = {
        "brand": "background:rgba(255,106,0,.08); color:#a34700; border:1px solid #ffe3c4;",
        "ok":    "background:#eafff0; color:#166534; border:1px solid #bbf7d0;",
        "warn":  "background:#fff7ed; color:#9a3412; border:1px solid #fed7aa;"
    }
    style = colors.get(tone, colors["brand"])
    st.markdown(
        f"<span style='font-weight:700;font-size:12px;padding:4px 8px;border-radius:999px;{style}'>"
        f"{text}</span>", unsafe_allow_html=True)


# ─────────────────────────────────────────
# 사이드바 (메뉴 & 공통)
# ─────────────────────────────────────────
ensure_session_keys()
with st.sidebar:
    # 🔹 캐릭터 카드(박스 제거: sb-card 래퍼 삭제)
    bee = load_image("GPS.png") 
    if bee:
        st.image(bee, width=120)  # ← 더 작게

    st.markdown(
        "<div style='font-weight:700;margin-top:8px'>2025 Big Contest · AI DATA</div>"
        "<div style='color:#6b7280;font-size:13px;margin-bottom:10px'>신한카드 소상공인 비밀상담소</div>",
        unsafe_allow_html=True,
    )

    # 🔹 메뉴 제목/줄 제거: option_menu 제목 None 처리
    from streamlit_option_menu import option_menu
    choice = option_menu(
        menu_title=None,                 # ← '메뉴' 제목 숨김
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
            "nav-link-selected": {"background-color": "#ff6a00", "color": "white"},
        },
    )
    st.session_state.current_page = choice

    # ✅ 디버그 정보는 기본 비표시 (원하면 환경변수로 켜기)
    if os.getenv("SHOW_DEBUG", "0") == "1":
        with st.expander("🔧 디버그 정보", expanded=False):
            st.write(f"현재 페이지: {st.session_state.current_page}")
            st.write(f"Thread ID: {st.session_state.get('thread_id', 'N/A')}")
            st.write(f"메시지 수: {len(st.session_state.get('messages', []))}")
            st.write(f"Web provider: {st.session_state.get('last_web_provider','N/A')}")

# ─────────────────────────────────────────
# Top Bar + 헤더
# ─────────────────────────────────────────
st.markdown(
    '<div class="topbar"><div class="topbar-inner">'
    '<div class="top-logo">Good Profit Strategy</div>'
    f'<div class="top-tabs"><div class="top-tab {"active" if st.session_state.current_page=="Home" else ""}">Home</div>'
    f'<div class="top-tab {"active" if st.session_state.current_page=="Chatbot" else ""}">Chatbot</div></div>'
    '</div></div>',
    unsafe_allow_html=True
)

# 제목 (심플)
st.markdown("## GPS")
st.caption("#당신의 비즈니스가 어디에 있든, GPS는 늘 올바른 방향을 찾아드립니다.")


# ── 공용 UI 카드 컴포넌트 ─────────────────
CARD_CSS = """
<style>
.ui-card { background:#fff; border:1px solid #eef2f7; border-radius:16px; padding:18px;
           box-shadow: 0 8px 22px rgba(13,69,255,0.05); margin-bottom:14px; }
.ui-card h5 { margin: 0 0 10px 0; }
.kpi { display:flex; align-items:baseline; gap:10px; }
.kpi .v { font-size:28px; font-weight:800; letter-spacing:-0.5px; }
.kpi .d { font-size:12px; color:#16a34a; background:#eafff0; border-radius:8px; padding:2px 8px; }
</style>
"""
st.markdown(CARD_CSS, unsafe_allow_html=True)

def ui_card(title: str, body_html: str) -> None:
    st.markdown(f"""<div class="ui-card">
        <h5>{title}</h5>
        {body_html}
    </div>""", unsafe_allow_html=True)

def kpi_html(label: str, value: str, delta: str|None=None) -> str:
    d = f'<span class="d">▲ {delta}</span>' if delta else ""
    return f'<div class="kpi"><span class="v">{value}</span>{d}</div><div style="color:#64748b">{label}</div>'


# ─────────────────────────────────────────
# Home 페이지
# ─────────────────────────────────────────
if st.session_state.current_page == "Home":
    section("Home · 가맹점 대시보드", "🏠")

    dash_err_box = st.empty()
    try:
        # 데이터 로드
        fr, bz, ad = dash.load_all_data(FRANCHISE_CSV, BIZ_AREA_CSV, ADMIN_DONG_CSV)

        # 검색어 입력 + 결과 필터
        name_col = "가맹점명" if "가맹점명" in fr.columns else None
        c1, _ = st.columns([3, 1])
        with c1:
            query = st.text_input("가맹점명 검색", placeholder="예: 본죽, 동대, 원조...", label_visibility="visible").strip()

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

        with st.container():
            colL, colR = st.columns(2)
            with colL:
                ui_card("방문 고객 구조 (인구 피라미드)",
                        st.plotly_chart(dash.build_pyramid(row_now, dn_row),
                                        use_container_width=True, config={"displayModeBar": False})._repr_html_() if False else "")
                st.plotly_chart(dash.build_pyramid(row_now, dn_row), use_container_width=True, config={"displayModeBar": False})
            with colR:
                ui_card("매장 vs 동종·동상권(동월 근사)", "")
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
# ─────────────────────────────────────────
# Chatbot 페이지
# ─────────────────────────────────────────
else:
    colL, colR = st.columns([6, 2])
    with colL:
        st.markdown("### 🤖 Chatbot · 비밀상담")
    with colR:
        st.button("🧹 새\u00A0대화\u00A0시작", use_container_width=True, on_click=clear_chat_history)

    # 대화 렌더 (streamlit-chat)
    for i, m in enumerate(st.session_state.messages):
        role = "user" if isinstance(m, HumanMessage) else "assistant"
        render_chat_message(role, m.content, i)

    # 입력 — st.chat_input 그대로 사용해도 OK
    if query := st.chat_input(CHAT_PLACEHOLDER):
        st.session_state.messages.append(HumanMessage(content=query))
        render_chat_message("user", query, len(st.session_state.messages)-1)

        with st.spinner("🔍 분석 중..."):
            try:
                result = run_one_turn(
                    user_query=query,
                    store_name=query,
                    thread_id=st.session_state.thread_id,
                )
                status = result.get("status", "ok")

                if status == "need_clarify":
                    reply = result.get("final_response", "후보가 여러 개입니다.")
                    st.session_state.messages.append(AIMessage(content=reply))
                    render_chat_message("assistant", reply, len(st.session_state.messages)-1)

                    candidates = result.get("store_candidates", [])
                    if candidates:
                        with st.expander("가맹점 후보 목록"):
                            st.dataframe(pd.DataFrame(candidates), use_container_width=True)

                elif status == "error":
                    err = f"❌ {result.get('error','알 수 없는 오류')}"
                    st.session_state.messages.append(AIMessage(content=err))
                    render_chat_message("assistant", err, len(st.session_state.messages)-1)

                else:
                    reply = result.get("final_response", "응답을 생성할 수 없습니다.")
                    st.session_state.messages.append(AIMessage(content=reply))
                    render_chat_message("assistant", reply, len(st.session_state.messages)-1)

                    # 출처/액션 렌더(버블 아래 보조영역)
                    web_snips = result.get("web_snippets") or result.get("state", {}).get("web_snippets")
                    web_meta  = result.get("web_meta") or result.get("state", {}).get("web_meta")
                    if web_snips:
                        render_sources(web_snips, web_meta, limit=3)

                    actions = result.get("actions", [])
                    if actions:
                        with st.expander("📋 추천 액션 플랜"):
                            for a in actions:
                                st.markdown(
                                    f"**{a.get('title','N/A')}** (우선순위 {a.get('priority','-')})\n"
                                    f"- 카테고리: {a.get('category','-')}\n"
                                    f"- 이유: {a.get('why','-')}\n"
                                )
            except Exception as e:
                err = f"⚠️ 처리 중 오류 발생: {e}"
                st.session_state.messages.append(AIMessage(content=err))
                render_chat_message("assistant", err, len(st.session_state.messages)-1)
