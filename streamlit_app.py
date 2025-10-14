# -*- coding: utf-8 -*-
"""
Streamlit UI
"""
import os
from pathlib import Path
from PIL import Image
import streamlit as st
import pandas as pd
from langchain_core.messages import HumanMessage, AIMessage

from my_agent.utils.adapters import run_one_turn

# ═══════════════════════════════════════════════════════════
# 설정
# ═══════════════════════════════════════════════════════════
ASSETS = Path("assets")
CHAT_PLACEHOLDER = (
    "마케팅이 필요한 가맹점을 알려주세요\n"
    "(조회가능 예시: 동대*, 유유*, 똥파*, 본죽*, 본*, 원조*, 희망*, 혁이*, H커*, 케키*)"
)

# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════
@st.cache_data
def load_image(name: str):
    try:
        return Image.open(ASSETS / name)
    except Exception:
        return None


def clear_chat_history():
    st.session_state.messages = []
    st.session_state.thread_id = f"thread_{os.urandom(8).hex()}"


def render_chat_message(role: str, content: str):
    with st.chat_message(role):
        st.markdown(content.replace("<br>", " \n"))


# ═══════════════════════════════════════════════════════════
# Page Config
# ═══════════════════════════════════════════════════════════
st.set_page_config(
    page_title="2025 빅콘테스트 - AI 비밀상담사",
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

# ═══════════════════════════════════════════════════════════
# Sidebar
# ═══════════════════════════════════════════════════════════
with st.sidebar:
    logo = load_image("shc_ci_basic_00.png")
    if logo:
        st.image(logo, use_container_width=True)
    
    st.markdown("<p style='text-align: center;'>2025 Big Contest</p>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>AI DATA 활용분야</p>", unsafe_allow_html=True)
    st.write("")
    
    st.button("Clear Chat History", on_click=clear_chat_history)
    
    # 디버그 정보
    with st.expander("🔧 디버그 정보"):
        st.write(f"Thread ID: {st.session_state.get('thread_id', 'N/A')}")
        st.write(f"메시지 수: {len(st.session_state.get('messages', []))}")

# ═══════════════════════════════════════════════════════════
# Header
# ═══════════════════════════════════════════════════════════
st.title("신한카드 소상공인 🔑 비밀상담소")
st.subheader("#우리동네 #숨은맛집 #소상공인 #마케팅 #전략 .. 🤤")

hero_img = load_image("image_gen3.png")
if hero_img:
    st.image(hero_img, use_container_width=True, caption="🌀 머리아픈 마케팅 📊 어떻게 하면 좋을까?")

# ═══════════════════════════════════════════════════════════
# Session Init
# ═══════════════════════════════════════════════════════════
if "messages" not in st.session_state:
    st.session_state.messages = []

if "thread_id" not in st.session_state:
    st.session_state.thread_id = f"thread_{os.urandom(8).hex()}"

# 기존 히스토리 렌더
for m in st.session_state.messages:
    role = "user" if isinstance(m, HumanMessage) else "assistant"
    render_chat_message(role, m.content)

# ═══════════════════════════════════════════════════════════
# Chat Input & Processing
# ═══════════════════════════════════════════════════════════
if query := st.chat_input(CHAT_PLACEHOLDER):
    # 사용자 메시지 추가
    st.session_state.messages.append(HumanMessage(content=query))
    render_chat_message("user", query)
    
    # 파이프라인 실행
    with st.spinner("🔍 분석 중..."):
        try:
            result = run_one_turn(
                user_query=query,
                store_name=query,  # 간소화: query에서 가게명 추출
                thread_id=st.session_state.thread_id
            )
            
            if result["status"] == "need_clarify":
                # 후보 확정 필요
                reply = result.get("final_response", "후보가 여러 개입니다.")
                st.session_state.messages.append(AIMessage(content=reply))
                render_chat_message("assistant", reply)
                
                # 후보 테이블 표시
                candidates = result.get("store_candidates", [])
                if candidates:
                    df = pd.DataFrame(candidates)
                    st.dataframe(df, use_container_width=True)
            
            elif result["status"] == "error":
                # 에러
                error_msg = f"❌ {result.get('error', '알 수 없는 오류')}"
                st.session_state.messages.append(AIMessage(content=error_msg))
                render_chat_message("assistant", error_msg)
            
            else:
                # 정상 응답
                reply = result.get("final_response", "응답을 생성할 수 없습니다.")
                st.session_state.messages.append(AIMessage(content=reply))
                render_chat_message("assistant", reply)
                
                # 액션 표시 (옵션)
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