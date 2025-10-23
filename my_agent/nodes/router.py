# my_agent/nodes/router.py

# -*- coding: utf-8 -*-
"""
Intent 라우팅: LLM 우선 분류 → 규칙 기반 보정(백업) → 가맹점 검색
"""
from typing import Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from my_agent.utils.config import GOOGLE_API_KEY, LLM_MODEL, LLM_TEMPERATURE
from my_agent.utils.state import GraphState
from my_agent.utils.tools import resolve_store  

INTENTS = ("SNS", "REVISIT", "ISSUE", "COOPERATION", "SEASON", "GENERAL")

# 규칙 기반 키워드(LLM 실패/애매할 때 보정)
RULES = {
    "SNS":     ["sns", "인스타", "instagram", "틱톡", "tiktok", "릴스", "홍보", "바이럴", "해시태그", "스폰", "협찬"],
    "REVISIT": ["재방문", "재내점", "단골", "리텐션", "리워드", "스탬프", "쿠폰", "멤버십"],
    "ISSUE":   ["문제", "이슈", "원인", "진단", "하락", "떨어졌", "왜", "원흉", "버그", "불만", "클레임", "불편"],
    "COOPERATION": ["협업", "파트너", "제휴", "상생", "공동", "콜라보"],
    "SEASON": ["계절", "여름", "겨울", "봄", "가을", "날씨", "기온", "더위", "추위", "비", "눈"]
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
            "SNS, REVISIT, ISSUE, COOPERATION, SEASON, GENERAL.\n"
            "- SNS: SNS 콘텐츠/바이럴/플랫폼 운영/해시태그/협찬 등 홍보 전략 중심\n"
            "- REVISIT: 재방문/단골/리텐션/쿠폰/멤버십/CRM 중심\n"
            "- ISSUE: 원인진단/문제분석/지표하락 원인/병목 파악 중심\n"
            "- COOPERATION: 상권 내 다른 매장과의 협업, 제휴, 공동 마케팅, 상생 아이디어 관련\n"
            "- SEASON: 계절/날씨/기온 변화에 따른 소비 패턴, 마케팅 전략, 시기별 프로모션 관련\n"
            "- GENERAL: 위에 딱 맞지 않으면 종합 전략\n"
            "출력은 반드시 여섯 가지 라벨 중 하나만, 추가 말 없이 단일 토큰으로 답해."
        )
        prompt = f"질문: ```{user_query}```\n답:"

        try:
            resp = self.llm.invoke([("system", system), ("human", prompt)])
            raw = (resp.content or "").strip().upper()
            # 관용 표현/동의어 정리
            alias = {
                # SNS 관련
                "SNS홍보": "SNS",
                "SNS 마케팅": "SNS",
                "SOCIAL": "SNS",
                "INSTAGRAM": "SNS",
                "TIKTOK": "SNS",

                # REVISIT 관련
                "RETENTION": "REVISIT",
                "RE-VISIT": "REVISIT",
                "REVISITING": "REVISIT",

                # ISSUE 관련
                "ISSUES": "ISSUE",
                "PROBLEM": "ISSUE",
                "DIAGNOSIS": "ISSUE",
                "BUG": "ISSUE",
                "ERROR": "ISSUE",

                # COOPERATION 관련
                "COOP": "COOPERATION",
                "COOPERATE": "COOPERATION",
                "COLLAB": "COOPERATION",
                "COLLABORATION": "COOPERATION",
                "PARTNERSHIP": "COOPERATION",
                "ALLY": "COOPERATION",
                "협업": "COOPERATION",
                "제휴": "COOPERATION",
                "상생": "COOPERATION",
                "공동": "COOPERATION",

                # SEASON 관련
                "SEASONAL": "SEASON",
                "WEATHER": "SEASON",
                "CLIMATE": "SEASON",
                "TEMP": "SEASON",
                "TEMPERATURE": "SEASON",
                "계절": "SEASON",
                "날씨": "SEASON",
                "여름": "SEASON",
                "겨울": "SEASON",
                "봄": "SEASON",
                "가을": "SEASON",

                # GENERAL 관련
                "GEN": "GENERAL",
                "DEFAULT": "GENERAL",
            }
            label = alias.get(raw, raw)
            return label if label in INTENTS else None
        except Exception:
            return None

    def __call__(self, state: GraphState) -> GraphState:
        user_query = state.get("user_query", "")

        # 1) Intent 분류
        # 1-1) LLM 우선
        intent = self._classify_with_llm(user_query)

        # 1-2) LLM 실패/애매 → 규칙 기반 보정
        if intent is None:
            intent = self._rules_fallback(user_query)

        state["intent"] = intent
        print(f"[ROUTER] Intent 분류 완료: {intent}")

        # 2) 가맹점 검색 (store_id 없을 때만)
        if not state.get("store_id"):
            print("[ROUTER] resolve_store 실행 중...")
            state = resolve_store(state)
            
            # need_clarify가 True면 바로 리턴 (후보 선택 필요)
            if state.get("need_clarify"):
                print("[ROUTER] ⚠️ 가맹점 후보 여러 개 → 사용자 선택 필요")
                print(f"[ROUTER] 후보 수: {len(state.get('store_candidates', []))}")
                return state
            
            # 가맹점 확정됨
            if state.get("store_id"):
                user_info = state.get("user_info", {})
                print(f"[ROUTER] 가맹점 확정: {user_info.get('store_name')} (id={state.get('store_id')})")
            else:
                print("[ROUTER] 가맹점명 없음 → GENERAL fallback 모드")
        else:
            print(f"[ROUTER] store_id 이미 존재: {state.get('store_id')}")

        return state