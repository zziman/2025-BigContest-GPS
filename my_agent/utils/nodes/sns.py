# -*- coding: utf-8 -*-
"""
SNS 추천 노드
"""
from langchain_google_genai import ChatGoogleGenerativeAI
from my_agent.utils.config import GOOGLE_API_KEY, LLM_MODEL, LLM_TEMPERATURE
from my_agent.utils.state import GraphState
from my_agent.utils.tools import build_base_context, build_signals_context, postprocess_response
from pathlib import Path

PROMPT = """당신은 SNS 마케팅 전문가입니다.

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

class SNSNode:
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model=LLM_MODEL,
            google_api_key=GOOGLE_API_KEY,
            temperature=LLM_TEMPERATURE
        ) if GOOGLE_API_KEY else None
        
        self.prompt_template = PROMPT
    
    def __call__(self, state: GraphState) -> GraphState:
        """
        SNS 마케팅 전략 생성
        """
        card = state.get("card_data", {})
        user_query = state.get("user_query", "")
        signals = state.get("signals", [])
        persona = state.get("persona", "")
        channel_hints = state.get("channel_hints", [])
        
        # 프롬프트 조립
        base_ctx = build_base_context(card)
        sig_ctx = build_signals_context(signals)
        
        prompt = self.prompt_template.format(
            base_context=base_ctx,
            signals_context=sig_ctx,
            persona=persona,
            channel_hints=", ".join(channel_hints) if channel_hints else "데이터 기반 추천"
        )
        
        # LLM 호출
        if self.llm:
            try:
                response = self.llm.invoke(prompt)
                raw = response.content
            except Exception as e:
                raw = f"LLM 호출 실패: {e}"
        else:
            raw = "(데모) SNS 마케팅 전략 생성 중..."
        
        state["raw_response"] = raw
        
        # 후처리
        final, actions = postprocess_response(raw, card, signals)
        state["final_response"] = final
        state["actions"] = actions
        
        return state