# -*- coding: utf-8 -*-
"""
문제 진단 노드
"""
from langchain_google_genai import ChatGoogleGenerativeAI
from my_agent.utils.config import GOOGLE_API_KEY, LLM_MODEL, LLM_TEMPERATURE
from my_agent.utils.state import GraphState
from my_agent.utils.tools import build_base_context, build_signals_context, postprocess_response

from .sns import build_web_context, append_sources  # 재사용

PROMPT = """당신은 비즈니스 문제 진단 전문가입니다.

아래 가맹점의 데이터를 분석하여 현재 가장 큰 문제점을 찾고, 원인을 분석하며, 구체적인 해결 방안을 제시하세요.

[INTERNAL DATA]
{base_context}
{signals_context}

[EXTERNAL (최근 리뷰/기사/블로그 스니펫 요약)]
{web_context}

[출력 형식]
1) 핵심 문제점 (1개, 가장 시급한 이슈)
   - 문제 설명 (2~3줄)
   - 데이터 근거 (수치 인용, (내부) / (외부) 표기)

2) 원인 분석 (3~5개 요인)
   - 각 원인별로 구체적 설명
   - 관련 근거와 연관성 명시(내부/외부 구분)

3) 해결 방안 (우선순위 순 3개)
   - 액션 항목 / 예상 효과 / 실행 난이도 (상/중/하)
   - 각 방안의 근거 출처(내부/외부) 명시

4) 단기 액션 플랜 (1개월 내 실행 가능)
   - 구체적 실행 단계 / 필요 리소스 / 성과 지표

주의:
- 외부 스니펫은 참고 수준으로 요약 인용(직접 인용 금지)
- 내부 지표를 우선, 외부는 최신성 보강용
"""

class IssueNode:
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
            raw = "(데모) 문제 진단 생성 중..."
        
        state["raw_response"] = raw
        final, actions = postprocess_response(
            raw, card, signals, intent=state.get("intent","GENERAL"),
            web_snippets=state.get("web_snippets"), web_meta=state.get("web_meta")
        )        
        final = append_sources(final, state)
        state["final_response"] = final
        state["actions"] = actions
        return state
