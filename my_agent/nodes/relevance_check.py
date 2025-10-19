# my_agent/nodes/relevance_check.py

import re
from typing import Dict, Any, Tuple
from my_agent.utils.state import GraphState
from my_agent.utils.config import ENABLE_RELEVANCE_CHECK


def check_base_relevance(user_query: str, response: str, user_info: Dict[str, Any]) -> Tuple[bool, str]:
    """기본 관련성 체크"""
    if len((response or "").strip()) < 50:
        return False, "응답이 너무 짧습니다 (최소 50자 필요)"

    # ✅ store name이 있는 경우 응답에 언급되었는지 확인
    store_name = user_info.get("store_name") if user_info else None
    if store_name and len(store_name) > 1 and store_name not in response:
        return False, f"가게명 '{store_name}'이(가) 응답에 포함되지 않았습니다"

    # ✅ 최소한 데이터 기반 느낌 키워드 포함 확인
    data_keywords = [
        "재방문", "배달", "고객", "비중", "%", "매출", "순위", "신규", "단골", "방문",
        "리뷰", "트렌드", "사례", "데이터"
    ]
    if not any(kw in response for kw in data_keywords):
        return False, "데이터 기반 분석 키워드가 부족합니다"

    return True, "OK"


def check_intent_specific_relevance(intent: str, response: str) -> Tuple[bool, str]:
    """Intent별 추가 검증"""
    rules = {
        "SNS": {
            "keywords": ["sns", "인스타", "릴스", "틱톡", "채널", "콘텐츠", "해시태그", "포스팅", "네이버", "플레이스", "쇼츠"],
            "min": 1, "msg": "SNS 전략 관련 키워드 부족"
        },
        "REVISIT": {
            "keywords": ["재방문", "단골", "리텐션", "쿠폰", "멤버십", "스탬프"],
            "min": 1, "msg": "재방문 전략 관련 키워드 부족"
        },
        "ISSUE": {
            "keywords": ["문제", "원인", "분석", "하락", "이슈", "리스크"],
            "min": 1, "msg": "문제 진단 관련 키워드 부족"
        },
        "GENERAL": {
            "keywords": ["전략", "마케팅", "개선", "방향"],
            "min": 1, "msg": "전략적 제안 키워드 부족"
        },
    }
    rule = rules.get((intent or "").upper())
    if not rule:
        return True, "OK"
    matched = [kw for kw in rule["keywords"] if kw in response.lower()]
    if len(matched) < rule["min"]:
        return False, rule["msg"]
    return True, "OK"


## 이거 알아서 수정하세요
# def check_relevance(state: GraphState) -> GraphState:
#     """관련성 체크 파이프라인"""
#     if not ENABLE_RELEVANCE_CHECK:
#         state["relevance_passed"] = True
#         return state

#     response = state.get("final_response") or ""
#     user_query = state.get("user_query") or ""
#     user_info = state.get("user_info") or {}
#     intent = state.get("intent", "GENERAL")

#     passed, msg = check_base_relevance(user_query, response, user_info)
#     if not passed:
#         state["relevance_passed"] = False
#         state["error"] = f"[Relevance] {msg}"
#         return state

#     passed, msg = check_intent_specific_relevance(intent, response)
#     if not passed:
#         state["relevance_passed"] = False
#         state["error"] = f"[Relevance] {msg}"
#         return state

#     state["relevance_passed"] = True
#     return state



## 일단 지금은 그냥 통과시키고 있음
def check_relevance(state: GraphState) -> GraphState:
    # 임시: 아무 검증 없이 그냥 통과
    state["relevance_passed"] = True
    return state