# my_agent/utils/tools.py
# -*- coding: utf-8 -*-
"""
ONE-STOP 통합 유틸리티
- helpers (정규화/포맷/검증)
- policies (재시도/금칙어/레이트리밋)
- relevance rules (응답 품질 규칙)
- prompt_builder / postprocess
- data_collector / feature_builder / store_resolver
- memory / relevance check (파이프라인용)
노드는 이 파일 하나만 임포트하면 됨.
"""
from typing import Dict, Any, Tuple, List, Optional
import re
import pandas as pd

from my_agent.utils.config import CONFIRM_ON_MULTI, ENABLE_RELEVANCE_CHECK
from my_agent.utils.state import GraphState
from mcp.adapter_client import call_mcp_tool
from langchain_core.messages import HumanMessage, AIMessage

# =============================================================================
# helpers  (기존 helpers.py)
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

def format_percentage(value: float, decimals: int = 0) -> str:
    """퍼센테이지 포맷팅"""
    return f"{value * 100:.{decimals}f}%"

def extract_top_demographics(card: Dict[str, Any]) -> list[tuple[str, float]]:
    """성별/연령대 비중 상위 3개 추출"""
    demo_keys = [
        ("남성_20대이하", "male_u20"),
        ("남성_30대", "male_30"),
        ("남성_40대", "male_40"),
        ("남성_50대", "male_50"),
        ("남성_60대이상", "male_60"),
        ("여성_20대이하", "female_u20"),
        ("여성_30대", "female_30"),
        ("여성_40대", "female_40"),
        ("여성_50대", "female_50"),
        ("여성_60대이상", "female_60"),
    ]
    demo_map = {}
    for label, key in demo_keys:
        val = card.get(key, 0) or 0
        demo_map[label] = safe_float(val)
    sorted_demo = sorted(demo_map.items(), key=lambda x: x[1], reverse=True)
    return sorted_demo[:3]

def validate_card_data(card: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """카드 데이터 필수 필드 검증"""
    required = ["mct_id", "yyyymm", "mct_name"]
    for field in required:
        if field not in card or not card[field]:
            return False, f"필수 필드 누락: {field}"
    return True, None

# =============================================================================
# policies  (기존 policies.py)
# =============================================================================
MAX_RETRIES = 2
TIMEOUT_SECONDS = 30
FORBIDDEN_WORDS = ["비속어예시1", "비속어예시2"]

def should_retry(state: Dict[str, Any]) -> bool:
    """재시도 여부 판단"""
    return state.get("retry_count", 0) < MAX_RETRIES

def check_forbidden_words(text: str) -> tuple[bool, list[str]]:
    """금칙어 검사"""
    found = [w for w in FORBIDDEN_WORDS if w in (text or "").lower()]
    return len(found) == 0, found

def apply_rate_limit(user_id: str) -> bool:
    """레이트리밋 체크 (더미)"""
    return True

# =============================================================================
# relevance rules  (기존 relevance_rules.py)
# =============================================================================
def check_base_relevance(user_query: str, response: str, card: Dict[str, Any]) -> Tuple[bool, str]:
    """기본 관련성 체크"""
    if len((response or "").strip()) < 50:
        return False, "응답이 너무 짧습니다 (최소 50자 필요)"
    mct_name = card.get("mct_name", "")
    if mct_name and len(mct_name) > 3 and mct_name not in response:
        return False, f"가맹점명 '{mct_name}'이 응답에 포함되지 않았습니다"
    data_keywords = ["재방문", "배달", "고객", "비중", "%", "매출", "순위", "신규", "단골", "방문"]
    if not any(kw in response for kw in data_keywords):
        return False, "데이터 근거가 응답에 포함되지 않았습니다"
    has_numbers = bool(re.search(r"\d+", response))
    if not has_numbers:
        return False, "구체적인 수치가 응답에 포함되지 않았습니다"
    return True, "OK"

def check_intent_specific_relevance(intent: str, response: str) -> Tuple[bool, str]:
    """Intent별 추가 검증"""
    rules = {
        "SNS":      {"keywords": ["sns", "인스타", "릴스", "틱톡", "채널", "콘텐츠", "해시태그", "포스팅"], "min": 2, "msg": "SNS 마케팅 관련 키워드가 부족합니다"},
        "REVISIT":  {"keywords": ["재방문", "단골", "리텐션", "쿠폰", "멤버십", "스탬프", "포인트", "충성도"], "min": 2, "msg": "재방문 전략 관련 키워드가 부족합니다"},
        "ISSUE":    {"keywords": ["문제", "이슈", "개선", "원인", "해결", "진단", "약점", "위험"], "min": 2, "msg": "문제 진단 관련 키워드가 부족합니다"},
        "GENERAL":  {"keywords": ["전략", "마케팅", "방안", "제안", "추천"], "min": 1, "msg": "마케팅 전략 관련 키워드가 부족합니다"},
    }
    rule = rules.get((intent or "").upper())
    if not rule:
        return True, "OK"
    text = (response or "").lower()
    matched = [kw for kw in rule["keywords"] if kw in text]
    if len(matched) < rule["min"]:
        return False, f"{rule['msg']} (필요: {rule['min']}개, 발견: {len(matched)}개)"
    return True, "OK"

def check_actionability(response: str) -> Tuple[bool, str]:
    """실행 가능성 체크"""
    indicators = ["추천", "제안", "방법", "전략", "실행", "진행", "도입", "활용", "개선", "강화", "운영", "적용"]
    if not any(ind in (response or "") for ind in indicators):
        return False, "실행 가능한 제안이 포함되지 않았습니다"
    return True, "OK"

def check_response_structure(response: str) -> Tuple[bool, str]:
    """응답 구조 체크"""
    lines = (response or "").strip().split("\n")
    non_empty = [l for l in lines if l.strip()]
    if len(non_empty) < 3:
        return False, "응답이 너무 단순합니다 (최소 3개 문단 필요)"
    from collections import Counter
    counts = Counter(non_empty)
    if counts and max(counts.values()) >= 3:
        return False, "응답에 과도한 반복이 있습니다"
    return True, "OK"

def check_forbidden_content(response: str) -> Tuple[bool, List[str]]:
    """금지 콘텐츠 체크"""
    forbidden_patterns = ["100% 보장", "무조건 성공", "확실한 효과", "절대", "반드시", "진단", "처방"]
    found = []
    low = (response or "").lower()
    for p in forbidden_patterns:
        if p.lower() in low:
            found.append(p)
    return len(found) == 0, found

def run_all_checks(user_query: str, response: str, card: Dict[str, Any], intent: str) -> Tuple[bool, List[str]]:
    """모든 검증 규칙 실행"""
    failures: List[str] = []
    ok, msg = check_base_relevance(user_query, response, card)
    if not ok: failures.append(f"[기본] {msg}")
    ok, msg = check_intent_specific_relevance(intent, response)
    if not ok: failures.append(f"[Intent] {msg}")
    ok, msg = check_actionability(response)
    if not ok: failures.append(f"[액션] {msg}")
    ok, msg = check_response_structure(response)
    if not ok: failures.append(f"[구조] {msg}")
    ok, found = check_forbidden_content(response)
    if not ok: failures.append(f"[금지어] 발견: {', '.join(found)}")
    return len(failures) == 0, failures

def calculate_relevance_score(user_query: str, response: str, card: Dict[str, Any], intent: str) -> float:
    """관련성 점수 (0.0~1.0)"""
    score, max_score = 0.0, 5.0
    if check_base_relevance(user_query, response, card)[0]: score += 1
    if check_intent_specific_relevance(intent, response)[0]: score += 1
    if check_actionability(response)[0]: score += 1
    if check_response_structure(response)[0]: score += 1
    if check_forbidden_content(response)[0]: score += 1
    return score / max_score

# =============================================================================
# prompt builder  (기존 prompt_builder.py)
# =============================================================================
def build_base_context(card: Dict[str, Any]) -> str:
    name = card.get("mct_name", "해당 가맹점")
    industry = card.get("industry", "업종 미상")
    district = card.get("district", "")
    yyyymm = card.get("yyyymm", "")
    repeat_rate   = format_percentage(card.get("repeat_rate", 0))
    delivery_share= format_percentage(card.get("delivery_share", 0))
    new_rate      = format_percentage(card.get("new_rate", 0))
    top_demos = extract_top_demographics(card)
    demo_str = ", ".join([f"{label} {format_percentage(val)}" for label, val in top_demos])
    return f"""
[가맹점 기본 정보 - {yyyymm}]
- 상호명: {name}
- 업종: {industry}
- 지역: {district}
- 재방문율: {repeat_rate}
- 배달 비중: {delivery_share}
- 신규 고객 비중: {new_rate}
- 주요 고객층: {demo_str}
- 거주 고객: {format_percentage(card.get("residential_share", 0))}
- 유동 고객: {format_percentage(card.get("floating_share", 0))}
""".strip()

def build_signals_context(signals: list[str]) -> str:
    if not signals: return ""
    desc = {
        "RETENTION_ALERT": "⚠️ 재방문율이 낮음 (20% 미만)",
        "CHANNEL_MIX_ALERT": "⚠️ 배달 의존도가 높음 (50% 이상)",
        "NEW_CUSTOMER_FOCUS": "✅ 신규 고객 유입이 활발함",
    }
    lines = [desc.get(s, s) for s in signals]
    return "\n[주요 이슈]\n" + "\n".join(lines)

def build_full_prompt(card: Dict[str, Any], user_query: str, signals: list[str], node_specific_instruction: str) -> str:
    base = build_base_context(card)
    sig = build_signals_context(signals)
    return f"""
당신은 친절한 마케팅 상담사입니다.

{base}

{sig}

[사용자 질문]
{user_query}

[출력 지침]
{node_specific_instruction}

결과는 자연스러운 문장으로 작성하고, 근거는 위 데이터를 활용하세요.
""".strip()

# =============================================================================
# data collector  (기존 data_collector.py)
# =============================================================================
def load_card_and_region_data(state: GraphState) -> GraphState:
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
# feature builder  (기존 feature_builder.py)
# =============================================================================
def build_features(state: GraphState) -> GraphState:
    card = state.get("card_data")
    if not card:
        state["error"] = "카드 데이터가 없습니다"
        return state
    signals: List[str] = []
    if card.get("repeat_rate", 0) < 0.2: signals.append("RETENTION_ALERT")
    if card.get("delivery_share", 0) >= 0.5: signals.append("CHANNEL_MIX_ALERT")
    if card.get("new_rate", 0) > 0.4: signals.append("NEW_CUSTOMER_FOCUS")
    state["signals"] = signals

    top = extract_top_demographics(card)
    persona_parts = [f"{label} ({format_percentage(val)})" for label, val in top[:2]]
    state["persona"] = ", ".join(persona_parts) if persona_parts else "데이터 부족"

    hints: List[str] = []
    female_30_40 = (card.get("female_30", 0) + card.get("female_40", 0)) > 0.3
    if female_30_40: hints.extend(["인스타그램", "네이버 블로그"])
    if card.get("floating_share", 0) > 0.5: hints.append("배달앱 프로모션")
    state["channel_hints"] = hints
    return state

# =============================================================================
# postprocess  (기존 postprocess.py)
# =============================================================================
def clean_response(response: str) -> str:
    response = re.sub(r"\n{3,}", "\n\n", response or "")
    response = response.strip()
    response = re.sub(r"#{4,}", "###", response)
    return response

def add_proxy_badge(response: str, is_proxy: bool) -> str:
    if is_proxy:
        return "📊 [프록시 기반 추정]\n이 분석은 동일 업종/지역의 평균 데이터를 기반으로 추정되었습니다.\n\n" + response
    return response

def add_data_quality_badge(response: str, card: Dict[str, Any]) -> str:
    yyyymm = card.get("yyyymm", "")
    if yyyymm:
        year, month = yyyymm[:4], yyyymm[4:6]
        response += f"\n\n📅 **기준 데이터**: {year}년 {month}월"
    return response

def add_disclaimer(response: str, card: Dict[str, Any]) -> str:
    disclaimer = """
---
💡 **안내사항**
- 본 분석은 신한카드 거래 데이터를 기반으로 한 통계적 추정입니다.
- 실제 실행 시 가맹점 상황에 맞게 조정이 필요합니다.
- 마케팅 효과는 실행 방법에 따라 달라질 수 있습니다.
"""
    return response + disclaimer

def generate_action_seed(card: Dict[str, Any], signals: List[str], intent: str) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []
    priority = 1
    if "RETENTION_ALERT" in signals:
        actions.append({
            "priority": priority, "category": "retention",
            "title": "재방문 고객 확보 프로그램",
            "description": "스탬프/쿠폰 프로그램 도입",
            "why": f"현재 재방문율 {format_percentage(card.get('repeat_rate', 0))}로 업종 평균 대비 낮음",
            "expected_impact": "재방문율 5~10%p 향상", "difficulty": "중",
        }); priority += 1
    if "CHANNEL_MIX_ALERT" in signals:
        actions.append({
            "priority": priority, "category": "channel",
            "title": "배달 의존도 감소 전략",
            "description": "매장 내 식사 프로모션 강화",
            "why": f"배달 비중 {format_percentage(card.get('delivery_share', 0))}로 높아 수익성 저하",
            "expected_impact": "마진율 3~5%p 개선", "difficulty": "중",
        }); priority += 1
    if not actions:
        actions.append({
            "priority": 1, "category": "general",
            "title": "종합 마케팅 진단",
            "description": "현황 분석 및 맞춤 전략 수립",
            "why": "체계적인 마케팅 전략 필요",
            "expected_impact": "매출 5~10% 향상", "difficulty": "중",
        })
    return actions[:5]

def postprocess_response(raw_response: str, card: Dict[str, Any],
                         signals: List[str], intent: str = "GENERAL") -> Tuple[str, List[Dict[str, Any]]]:
    text = clean_response(raw_response)
    text = add_proxy_badge(text, card.get("proxy", False))
    text = add_data_quality_badge(text, card)
    actions = generate_action_seed(card, signals, intent)
    text = add_disclaimer(text, card)
    return text, actions

# =============================================================================
# store resolver  (기존 store_resolver.py)
# =============================================================================
def resolve_store(state: GraphState) -> GraphState:
    store_name = (state.get("store_name_input") or "").strip()
    if not store_name:
        state["error"] = "가맹점명을 입력해주세요"; state["need_clarify"] = True; return state
    try:
        result = call_mcp_tool("search_merchant", merchant_name=store_name)
    except Exception as e:
        state["error"] = f"검색 실패: {e}"; state["need_clarify"] = True; return state
    if not result.get("found"):
        state["error"] = f"'{store_name}'에 해당하는 가맹점을 찾을 수 없습니다"; state["need_clarify"] = True; return state
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

def _rank_candidates(candidates: list, query: str) -> list:
    if not candidates: return []
    df = pd.DataFrame(candidates)
    q = normalize_store_name(query)
    df["_norm_name"] = df["가맹점명"].apply(normalize_store_name)
    df["_exact"] = (df["_norm_name"] == q).astype(int)
    df["_prefix"] = df["_norm_name"].str.startswith(q).astype(int)
    df["_len"] = df["가맹점명"].str.len()
    df = df.sort_values(by=["_exact", "_prefix", "_len", "가맹점명"],
                        ascending=[False, False, True, True])
    return df.to_dict("records")

# =============================================================================
# memory  (기존 memory.py)
# =============================================================================
def update_conversation_memory(state: GraphState) -> GraphState:
    user_query = state.get("user_query", "")
    final_response = state.get("final_response", "")
    if user_query:
        state["messages"].append(HumanMessage(content=user_query))
    if final_response:
        state["messages"].append(AIMessage(content=final_response))
    if len(state["messages"]) >= 10:
        state["conversation_summary"] = "최근 대화 요약..."
    return state

# =============================================================================
# relevance check stage  (기존 relevance_checker.py)
# =============================================================================
def check_relevance(state: GraphState) -> GraphState:
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

    state["relevance_passed"] = True
    return state
