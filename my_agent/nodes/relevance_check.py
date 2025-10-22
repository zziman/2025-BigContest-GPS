# my_agent/nodes/relevance_check.py

import time
import re
from typing import Dict, Any, Tuple
from my_agent.utils.state import GraphState
from my_agent.utils.config import ENABLE_RELEVANCE_CHECK

def compute_keyword_score(response: str, keywords: list[str]) -> float:
    """키워드 매칭률 계산 (0~1 스코어)"""
    if not response:
        return 0.0
    response_lower = response.lower()
    matched = sum(1 for kw in keywords if kw.lower() in response_lower)
    return matched / max(len(keywords), 1)

def check_relevance(state: GraphState) -> GraphState:
    """빠른 휴리스틱 기반 관련성 체크"""
    start_time = time.perf_counter() ## 시
    if not ENABLE_RELEVANCE_CHECK:
        state["relevance_passed"] = True
        print("[Relevance] 체크 비활성화됨 → 자동 통과 ✅")
        return state

    response = (state.get("final_response") or "").strip()
    user_query = state.get("user_query") or ""
    user_info = state.get("user_info") or {}
    intent = (state.get("intent") or "GENERAL").upper()

    # 길이 검사
    if len(response) < 50:
        state["relevance_passed"] = False
        state["error"] = "[Relevance] 응답이 너무 짧습니다 (50자 미만)"
        print(f"[Relevance 통과 X / 응답 너무 짧음] — len={len(response)}")
        return state

    # 기본 데이터 관련 키워드 점수
    data_keywords = ["매출", "고객", "단골", "재방문", "신규", "비중", "비율", "순위", "방문", "리뷰", "배달", "데이터"]
    data_score = compute_keyword_score(response, data_keywords)

    # intent-specific 키워드 점수
    intent_keywords = {
        "SNS": ["sns", "인스타", "릴스", "틱톡", "채널", "콘텐츠", "해시태그", "포스팅", "네이버", "쇼츠"],
        "REVISIT": ["재방문", "단골", "리텐션", "쿠폰", "멤버십", "스탬프"],
        "ISSUE": ["문제", "이슈", "리스크", "원인", "분석", "하락"],
        "GENERAL": ["전략", "방향", "개선", "마케팅", "추천"]
    }
    intent_score = compute_keyword_score(response, intent_keywords.get(intent, []))

    # 점수 기반 판단
    # data_score: 0.0~1.0, intent_score: 0.0~1.0
    # 두 점수를 0.5:0.5 가중 평균 → threshold 0.25 기준
    relevance_score = (data_score * 0.5) + (intent_score * 0.5)

    # 가게명 포함 여부
    store_name = user_info.get("store_name")
    if store_name and len(store_name) > 1 and store_name not in response:
        relevance_score -= 0.1  # 패널티
        print(f"[Relevance] 가게명 '{store_name}' 미포함 → 점수 -0.2 패널티")

    # 최종 판단
    ## 시간
    elapsed = time.perf_counter() - start_time
    if relevance_score < 0.25:
        state["relevance_passed"] = False
        state["error"] = f"[Relevance] 관련성 낮음 (score={relevance_score:.2f})"
        print(f"[Relevance 통과 X / 관련성 낮음] — score={relevance_score:.2f}, intent={intent} | {elapsed:.3f}s 소요")

    else:
        state["relevance_passed"] = True
        print(f"[Relevance 통과] — score={relevance_score:.2f}, intent={intent} | {elapsed:.3f}s 소요")

    return state
