# -*- coding: utf-8 -*-
"""
재방문 전략 노드
"""
from langchain_google_genai import ChatGoogleGenerativeAI
from my_agent.utils.config import GOOGLE_API_KEY, LLM_MODEL, LLM_TEMPERATURE
from my_agent.utils.state import GraphState
from my_agent.utils.tools import build_base_context, build_signals_context, postprocess_response
from pathlib import Path

PROMPT = """당신은 고객 충성도 전문가입니다.

아래 가맹점의 재방문율을 높일 수 있는 구체적인 마케팅 아이디어를 제시하세요.

{base_context}
{signals_context}

[출력 형식]
1) 현황 진단 (2~3줄)
2) 재방문 촉진 아이디어 (5개, 각 근거 포함)
3) 우선순위 1순위 액션플랜 (구체적 실행 방법)

데이터를 근거로 설득력 있게 작성하세요.
"""

# SNS 마케팅(SNS) 노드용
SNS_PROMPT = """당신은 SNS 마케팅 전문가입니다.

아래 가맹점 데이터를 기반으로 SNS 채널 추천 및 콘텐츠 전략을 작성하세요.

{base_context}
{signals_context}

[주요 고객층]
{persona}

[추천 채널]
{channel_hints}

[출력 형식]
1) 추천 SNS 채널 (2~3개, 각 채널별 이유)
2) 타겟별 콘텐츠 아이디어 (3~5개)
3) 홍보 메시지 예시 (3개)

구체적이고 실행 가능한 전략을 제시하세요.
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
        sig_ctx = build_signals_context(signals)
        
        prompt = self.prompt_template.format(
            base_context=base_ctx,
            signals_context=sig_ctx
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
        final, actions = postprocess_response(raw, card, signals)
        state["final_response"] = final
        state["actions"] = actions
        
        return state