# -*- coding: utf-8 -*-
"""
종합 전략 노드
"""
from langchain_google_genai import ChatGoogleGenerativeAI
from my_agent.utils.config import GOOGLE_API_KEY, LLM_MODEL, LLM_TEMPERATURE
from my_agent.utils.state import GraphState
from my_agent.utils.prompt_builder import build_base_context, build_signals_context
from my_agent.utils.postprocess import postprocess_response

from .sns import build_web_context, append_sources  # 재사용

PROMPT = """[SYSTEM]
너는 소상공인 '종합 전략' 코파일럿이다. 입력으로 주어지는 매장 카드, 시그널, 사용자 질문, 그리고 최근 외부 문맥을 바탕으로
핵심 진단과 실행 전략을 간결하게 제시한다. 숫자는 %/원 단위를 명확히 표기하고 과장 없이 현실적인 범위로 제안하라.

[INTERNAL DATA]
{base_context}

[CONTEXT-SIGNALS]
{signals_context}

[EXTERNAL (최근 리뷰/기사/블로그 스니펫 요약)]
{web_context}

[USER-QUERY]
{user_query}

[OUTPUT-FORMAT]
- 핵심 진단(3개 내외): bullet
- 실행 전략(3~5개): bullet, 각 항목에 근거/예상효과 1줄 포함(내부/외부 표기)
- 예상 효과(1~2개): bullet, 지표명과 대략적 수치 범위 기재
- 주의/가정(있다면): bullet
"""

class GeneralNode:
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model=LLM_MODEL,
            google_api_key=GOOGLE_API_KEY,
            temperature=LLM_TEMPERATURE
        ) if GOOGLE_API_KEY else None
        self.prompt_template = PROMPT
    
    def __call__(self, state: GraphState) -> GraphState:
        card = state.get("card_data", {})
        user_query = state.get("user_query", "")
        signals = state.get("signals", "")
        persona = state.get("persona", "")

        base_ctx = build_base_context(card)
        sig_ctx  = build_signals_context(signals)
        web_ctx  = build_web_context(state)

        prompt = self.prompt_template.format(
            base_context=base_ctx,
            signals_context=sig_ctx,
            web_context=web_ctx,
            user_query=user_query
        )
        
        if self.llm:
            try:
                response = self.llm.invoke(prompt)
                raw = response.content
            except Exception as e:
                raw = f"LLM 호출 실패: {e}"
        else:
            raw = "(데모) 종합 전략 생성 중..."
        
        state["raw_response"] = raw
        final, actions = postprocess_response(
            raw, card, signals, intent=state.get("intent","GENERAL"),
            web_snippets=state.get("web_snippets"), web_meta=state.get("web_meta")
        )
        final = append_sources(final, state)
        state["final_response"] = final
        state["actions"] = actions
        return state
