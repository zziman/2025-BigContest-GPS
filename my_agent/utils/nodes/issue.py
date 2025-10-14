# -*- coding: utf-8 -*-
"""
문제 진단 노드
"""
from langchain_google_genai import ChatGoogleGenerativeAI
from my_agent.utils.config import GOOGLE_API_KEY, LLM_MODEL, LLM_TEMPERATURE
from my_agent.utils.state import GraphState
from my_agent.utils.tools import build_base_context, build_signals_context, postprocess_response
from pathlib import Path

PROMPT = """당신은 비즈니스 문제 진단 전문가입니다.

아래 가맹점의 데이터를 분석하여 현재 가장 큰 문제점을 찾고, 원인을 분석하며, 구체적인 해결 방안을 제시하세요.

{base_context}
{signals_context}

[출력 형식]
1) 핵심 문제점 (1개, 가장 시급한 이슈)
   - 문제 설명 (2~3줄)
   - 데이터 근거 (수치 인용)

2) 원인 분석 (3~5개 요인)
   - 각 원인별로 구체적 설명
   - 데이터 연관성 명시

3) 해결 방안 (우선순위 순 3개)
   - 액션 항목
   - 예상 효과
   - 실행 난이도 (상/중/하)

4) 단기 액션 플랜 (1개월 내 실행 가능)
   - 구체적 실행 단계
   - 필요 리소스
   - 성과 측정 지표

데이터를 근거로 논리적이고 실행 가능한 진단을 제공하세요.
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
        """
        문제점 진단 및 해결 방안 생성
        """
        card = state.get("card_data", {})
        user_query = state.get("user_query", "")
        signals = state.get("signals", [])
        
        # 프롬프트 조립
        base_ctx = build_base_context(card)
        sig_ctx = build_signals_context(signals)
        
        prompt = self.prompt_template.format(
            base_context=base_ctx,
            signals_context=sig_ctx
        )
        
        # LLM 호출
        if self.llm:
            try:
                response = self.llm.invoke(prompt)
                raw = response.content
            except Exception as e:
                raw = f"LLM 호출 실패: {e}"
        else:
            raw = "(데모) 문제 진단 생성 중..."
        
        state["raw_response"] = raw
        
        # 후처리
        final, actions = postprocess_response(raw, card, signals)
        state["final_response"] = final
        state["actions"] = actions
        
        return state