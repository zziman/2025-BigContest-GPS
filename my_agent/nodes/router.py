# my_agent/nodes/router.py

# -*- coding: utf-8 -*-
"""
Intent 라우팅: LLM 우선 분류 → 규칙 기반 보정(백업)
"""
from typing import Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from my_agent.utils.config import GOOGLE_API_KEY, LLM_MODEL, LLM_TEMPERATURE
from my_agent.utils.state import GraphState


INTENTS = ("SNS", "REVISIT", "ISSUE", "GENERAL")

# 규칙 기반 키워드(LLM 실패/애매할 때 보정)
RULES = {
    "SNS":     ["sns", "인스타", "instagram", "틱톡", "tiktok", "릴스", "홍보", "바이럴", "해시태그", "스폰", "협찬"],
    "REVISIT": ["재방문", "재내점", "단골", "리텐션", "리워드", "스탬프", "쿠폰", "멤버십"],
    "ISSUE":   ["문제", "이슈", "원인", "진단", "하락", "떨어졌", "왜", "원흉", "버그", "불만", "클레임", "불편"],
}

class RouterNode:
    def __init__(self):
        self.llm: Optional[ChatGoogleGenerativeAI] = None
        if GOOGLE_API_KEY:
            self.llm = ChatGoogleGenerativeAI(
                model=LLM_MODEL,
                google_api_key=GOOGLE_API_KEY,
                temperature=LLM_TEMPERATURE
            )

    def _rules_fallback(self, user_query: str) -> str:
        q = (user_query or "").lower()
        for intent, kws in RULES.items():
            if any(kw in q for kw in kws):
                return intent
        return "GENERAL"

    def _classify_with_llm(self, user_query: str) -> Optional[str]:
        if not (self.llm and user_query):
            return None

        system = (
            "너는 입력 질의를 다음 중 하나로 정확히 분류한다: "
            "SNS, REVISIT, ISSUE, GENERAL.\n"
            "- SNS: SNS 콘텐츠/바이럴/플랫폼 운영/해시태그/협찬 등 홍보 전략 중심\n"
            "- REVISIT: 재방문/단골/리텐션/쿠폰/멤버십/CRM 중심\n"
            "- ISSUE: 원인진단/문제분석/지표하락 원인/병목 파악 중심\n"
            "- GENERAL: 위에 딱 맞지 않으면 종합 전략\n"
            "출력은 반드시 네 가지 라벨 중 하나만, 추가 말 없이 단일 토큰으로 답해."
        )
        prompt = f"질문: ```{user_query}```\n답:"

        try:
            resp = self.llm.invoke([("system", system), ("human", prompt)])
            raw = (resp.content or "").strip().upper()
            # 관용 표현/동의어 정리
            alias = {
                "SNS홍보": "SNS",
                "SNS 마케팅": "SNS",
                "RETENTION": "REVISIT",
                "RE-VISIT": "REVISIT",
                "ISSUES": "ISSUE",
                "PROBLEM": "ISSUE",
                "DIAGNOSIS": "ISSUE",
                "GEN": "GENERAL",
                "DEFAULT": "GENERAL",
            }
            label = alias.get(raw, raw)
            return label if label in INTENTS else None
        except Exception:
            return None

    def __call__(self, state: GraphState) -> GraphState:
        user_query = state.get("user_query", "")

        # 1) LLM 우선
        intent = self._classify_with_llm(user_query)

        # 2) LLM 실패/애매 → 규칙 기반 보정
        if intent is None:
            intent = self._rules_fallback(user_query)

        state["intent"] = intent
        return state
