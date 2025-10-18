# -*- coding: utf-8 -*-
"""
핵심 유틸리티
- helpers (정규화/포맷/검증)
- policies (재시도/금칙어/레이트리밋)
- relevance rules (응답 품질 규칙)
- data_collector / feature_builder / store_resolver
- relevance check 
"""
from typing import Dict, Any, Tuple, List, Optional
import re
import pandas as pd

from my_agent.utils.config import CONFIRM_ON_MULTI, ENABLE_RELEVANCE_CHECK
from my_agent.utils.state import GraphState
from mcp.adapter_client import call_mcp_tool

# =============================================================================
# helpers
# =============================================================================
def normalize_store_name(name: str) -> str:
    """가맹점명 정규화: 공백/특수문자 제거"""
    if not name:
        return ""
    return re.sub(r"\s+", "", name).strip()

def safe_float(value: Any, default: float = 0.0) -> float:
    """안전한 float 변환"""
    try:
        return float(value) if value is not None else default
    except (ValueError, TypeError):
        return default

def safe_int(value: Any, default: int = 0) -> int:
    """안전한 int 변환"""
    try:
        return int(value) if value is not None else default
    except (ValueError, TypeError):
        return default

def validate_card_data(card: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """카드 데이터 필수 필드 검증"""
    required = ["mct_id", "yyyymm", "mct_name"]
    for field in required:
        if field not in card or not card[field]:
            return False, f"필수 필드 누락: {field}"
    return True, None

# =============================================================================
# policies
# =============================================================================
MAX_RETRIES = 2
TIMEOUT_SECONDS = 30
FORBIDDEN_WORDS = ["비속어예시1", "비속어예시2"]

def should_retry(state: Dict[str, Any]) -> bool:
    """재시도 여부 판단"""
    return state.get("retry_count", 0) < MAX_RETRIES

def check_forbidden_words(text: str) -> Tuple[bool, List[str]]:
    """금칙어 검사"""
    found = [w for w in FORBIDDEN_WORDS if w in (text or "").lower()]
    return len(found) == 0, found

def apply_rate_limit(user_id: str) -> bool:
    """레이트리밋 체크 (더미)"""
    return True

# =============================================================================
# relevance rules
# =============================================================================
def check_base_relevance(user_query: str, response: str, card: Dict[str, Any]) -> Tuple[bool, str]:
    """기본 관련성 체크"""
    if len((response or "").strip()) < 50:
        return False, "응답이 너무 짧습니다 (최소 50자 필요)"
    mct_name = card.get("mct_name", "")
    if mct_name and len(mct_name) > 3 and mct_name not in response:
        return False, f"가맹점명 '{mct_name}'이 응답에 포함되지 않았습니다"

    data_keywords = [
        "재방문", "배달", "고객", "비중", "%", "매출", "순위", "신규", "단골", "방문",
        "리뷰", "블로그", "기사", "출처", "url"
    ]
    if not any(kw in response for kw in data_keywords):
        return False, "데이터 근거가 응답에 포함되지 않았습니다"

    has_numbers = bool(re.search(r"\d+", response))
    if not has_numbers:
        return False, "구체적인 수치가 응답에 포함되지 않았습니다"
    return True, "OK"

def check_intent_specific_relevance(intent: str, response: str) -> Tuple[bool, str]:
    """Intent별 추가 검증"""
    rules = {
        "SNS": {
            "keywords": ["sns", "인스타", "릴스", "틱톡", "채널", "콘텐츠", "해시태그", "포스팅", "네이버", "플레이스", "쇼츠"],
            "min": 2, "msg": "SNS 마케팅 관련 키워드가 부족합니다"
        },
        "REVISIT": {
            "keywords": ["재방문", "단골", "리텐션", "쿠폰", "멤버십", "스탬프", "포인트", "충성도"],
            "min": 2, "msg": "재방문 전략 관련 키워드가 부족합니다"
        },
        "ISSUE": {
            "keywords": ["문제", "이슈", "개선", "원인", "해결", "진단", "약점", "위험"],
            "min": 2, "msg": "문제 진단 관련 키워드가 부족합니다"
        },
        "GENERAL": {
            "keywords": ["전략", "마케팅", "방안", "제안", "추천"],
            "min": 1, "msg": "마케팅 전략 관련 키워드가 부족합니다"
        },
    }
    rule = rules.get((intent or "").upper())
    if not rule:
        return True, "OK"
    text = (response or "").lower()
    matched = [kw for kw in rule["keywords"] if kw in text]
    if len(matched) < rule["min"]:
        return False, f"{rule['msg']} (필요: {rule['min']}개, 발견: {len(matched)}개)"
    return True, "OK"

def check_forbidden_content(response: str) -> Tuple[bool, List[str]]:
    """금지 콘텐츠 체크"""
    forbidden_patterns = ["100% 보장", "무조건 성공", "확실한 효과", "절대", "반드시"]
    found = []
    low = (response or "").lower()
    for p in forbidden_patterns:
        if p.lower() in low:
            found.append(p)
    return len(found) == 0, found

# =============================================================================
# data collector
# =============================================================================
def load_card_and_region_data(state: GraphState) -> GraphState:
    """카드 + 지역 데이터 수집"""
    store_id = state.get("store_id")
    if not store_id:
        state["error"] = "store_id가 없습니다"
        return state
    try:
        card_result = call_mcp_tool("load_store_data", store_id=store_id)
        if not card_result.get("success"):
            state["error"] = card_result.get("error", "카드 조회 실패")
            return state
        state["card_data"] = card_result.get("data")
    except Exception as e:
        state["error"] = f"카드 조회 실패: {e}"
        return state

    district = state["card_data"].get("district", "")
    if district:
        try:
            region_result = call_mcp_tool("resolve_region", district=district)
            if region_result.get("success"):
                admin_code = region_result.get("admin_dong_code")
                area_result = call_mcp_tool("load_area_data", admin_dong_code=admin_code)
                if area_result.get("success"):
                    state["area_data"] = area_result.get("data")
                region_data_result = call_mcp_tool("load_region_data", admin_dong_code=admin_code)
                if region_data_result.get("success"):
                    state["region_data"] = region_data_result.get("data")
        except Exception:
            pass
    return state

# =============================================================================
# feature builder
# =============================================================================
def build_features(state: GraphState) -> GraphState:
    """시그널 + 페르소나 + 채널 힌트 생성"""
    card = state.get("card_data")
    if not card:
        state["error"] = "카드 데이터가 없습니다"
        return state
    
    signals: List[str] = []
    if card.get("repeat_rate", 0) < 0.2:
        signals.append("RETENTION_ALERT")
    if card.get("delivery_share", 0) >= 0.5:
        signals.append("CHANNEL_MIX_ALERT")
    if card.get("new_rate", 0) > 0.4:
        signals.append("NEW_CUSTOMER_FOCUS")
    state["signals"] = signals

    # 프롬프트 빌더에서 임포트
    from my_agent.utils.prompt_builder import extract_top_demographics, format_percentage
    top = extract_top_demographics(card)
    persona_parts = [f"{label} ({format_percentage(val)})" for label, val in top[:2]]
    state["persona"] = ", ".join(persona_parts) if persona_parts else "데이터 부족"

    hints: List[str] = []
    female_30_40 = (card.get("female_30", 0) + card.get("female_40", 0)) > 0.3
    if female_30_40:
        hints.extend(["인스타그램", "네이버 블로그"])
    if card.get("floating_share", 0) > 0.5:
        hints.append("배달앱 프로모션")
    state["channel_hints"] = hints
    
    return state

# =============================================================================
# store resolver
# =============================================================================
def resolve_store(state: GraphState) -> GraphState:
    """가맹점명 → store_id 해결"""
    store_name = (state.get("store_name_input") or "").strip()
    if not store_name:
        state["error"] = "가맹점명을 입력해주세요"
        state["need_clarify"] = True
        return state
    
    try:
        result = call_mcp_tool("search_merchant", merchant_name=store_name)
    except Exception as e:
        state["error"] = f"검색 실패: {e}"
        state["need_clarify"] = True
        return state
    
    if not result.get("found"):
            state["error"] = f"'{store_name}'에 해당하는 가맹점을 찾을 수 없습니다"
            state["need_clarify"] = True
            return state
        
    candidates = result.get("merchants", [])
    state["store_candidates"] = candidates
    ranked = _rank_candidates(candidates, store_name)

    if CONFIRM_ON_MULTI and len(ranked) > 1:
        state["need_clarify"] = True
        state["final_response"] = "후보가 여러 개입니다. 지점을 선택해주세요."
        return state

    best = ranked[0]
    state["store_id"] = str(best.get("가맹점구분번호") or best.get("가맹점_구분번호", ""))
    state["need_clarify"] = False
    return state


def _rank_candidates(candidates: List, query: str) -> List:
    """후보 랭킹"""
    if not candidates:
        return []
    
    df = pd.DataFrame(candidates)
    q = normalize_store_name(query)
    
    df["_norm_name"] = df["가맹점명"].apply(normalize_store_name)
    df["_exact"] = (df["_norm_name"] == q).astype(int)
    df["_prefix"] = df["_norm_name"].str.startswith(q).astype(int)
    df["_len"] = df["가맹점명"].str.len()
    
    df = df.sort_values(
        by=["_exact", "_prefix", "_len", "가맹점명"],
        ascending=[False, False, True, True]
    )
    
    return df.to_dict("records")

# =============================================================================
# relevance check (노드용)
# =============================================================================
def _check_web_citation_rule(state: GraphState) -> Tuple[bool, str]:
    """웹 스니펫 사용 시 출처 힌트 포함 여부 체크 (소프트 룰)"""
    snips = state.get("web_snippets") or []
    if not snips:
        return True, "no web snippets -> skip"

    raw = (state.get("raw_response") or "") + (state.get("final_response") or "")
    raw_low = raw.lower()

    has_anchor = ("참고 출처" in raw) or ("http://" in raw_low) or ("https://" in raw_low)
    has_domain = any(d in raw_low for d in [".co.kr", ".com", ".net", ".kr"])
    if has_anchor or has_domain:
        return True, "web citations present"
    return False, "web snippets used but no visible citation hint"


def check_relevance(state: GraphState) -> GraphState:
    """관련성 체크 파이프라인 (노드용)"""
    if not ENABLE_RELEVANCE_CHECK:
        state["relevance_passed"] = True
        return state

    raw = state.get("raw_response", "") or ""
    user_q = state.get("user_query", "") or ""
    card = state.get("card_data", {}) or {}
    intent = state.get("intent", "GENERAL") or "GENERAL"

    passed, msg = check_base_relevance(user_q, raw, card)
    if not passed:
        state["relevance_passed"] = False
        state["error"] = f"[Relevance] {msg}"
        state["retry_count"] = state.get("retry_count", 0) + 1
        return state

    passed, msg = check_intent_specific_relevance(intent, raw)
    if not passed:
        state["relevance_passed"] = False
        state["error"] = f"[Relevance] {msg}"
        state["retry_count"] = state.get("retry_count", 0) + 1
        return state

    # 소프트 웹 인용 규칙
    passed, msg = _check_web_citation_rule(state)
    if not passed:
        state["error"] = f"[Relevance][Soft] {msg}"
        # 하드 실패로 돌리고 싶다면 아래 두 줄 주석 해제
        # state["relevance_passed"] = False
        # return state

    state["relevance_passed"] = True
    return state