# -*- coding: utf-8 -*-
"""
재방문 전략 노드
"""
from langchain_google_genai import ChatGoogleGenerativeAI
from my_agent.utils.config import GOOGLE_API_KEY, LLM_MODEL, LLM_TEMPERATURE
from my_agent.utils.state import GraphState
from my_agent.utils.prompt_builder import build_base_context, build_signals_context
from my_agent.utils.postprocess import postprocess_response

from .sns import build_web_context, append_sources  # 재사용

PROMPT = """당신은 고객 충성도 전문가입니다.

아래 가맹점의 재방문율을 높일 수 있는 구체적인 마케팅 아이디어를 제시하세요.

[INTERNAL DATA]
{base_context}
{signals_context}

[EXTERNAL (최근 리뷰/기사/블로그 스니펫 요약)]
{web_context}

[출력 형식]
1) 현황 진단 (2~3줄)
2) 재방문 촉진 아이디어 (5개, 각 근거 포함)
3) 우선순위 1순위 액션플랜 (구체적 실행 방법)

주의:
- 각 아이디어 끝에 근거 출처 표기: (내부) / (외부)
- 실행 가능성과 우선순위를 고려
"""

class RevisitNode:
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model=LLM_MODEL,
            google_api_key=GOOGLE_API_KEY,
            temperature=LLM_TEMPERATURE
        ) if GOOGLE_API_KEY else None
        self.prompt_template = PROMPT
    
    def __call__(self, state: GraphState) -> GraphState:
        card = state.get("card_data", {})
        signals = state.get("signals", [])

        base_ctx = build_base_context(card)
        sig_ctx  = build_signals_context(signals)
        web_ctx  = build_web_context(state)

        prompt = self.prompt_template.format(
            base_context=base_ctx,
            signals_context=sig_ctx,
            web_context=web_ctx
        )
        
        if self.llm:
            try:
                response = self.llm.invoke(prompt)
                raw = response.content
            except Exception as e:
                raw = f"LLM 호출 실패: {e}"
        else:
            raw = "(데모) 재방문 전략 생성 중..."
        
        state["raw_response"] = raw
        final, actions = postprocess_response(
            raw, card, signals, intent=state.get("intent","GENERAL"),
            web_snippets=state.get("web_snippets"), web_meta=state.get("web_meta")
        )
        final = append_sources(final, state)
        state["final_response"] = final
        state["actions"] = actions
        return state
