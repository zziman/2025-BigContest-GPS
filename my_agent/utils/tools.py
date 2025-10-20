# my_agent/utils/tools.py

# -*- coding: utf-8 -*-
"""
핵심 유틸리티
- helpers (정규화/검증/간단 변환)
- store_resolver (가맹점 후보 확정 + user_info 구성)
- data_loader (store/bizarea/region 데이터 조회)
- feature_builder (간단 시그널/힌트 생성; 내부 계산만 비율 보정, 원본 데이터는 변환하지 않음)
"""

from typing import Dict, Any, Tuple, List, Optional
import os, re
import pandas as pd

from my_agent.utils import config as cfg
from my_agent.utils.state import GraphState
from mcp.adapter_client import call_mcp_tool

from langchain_google_genai import ChatGoogleGenerativeAI
from my_agent.utils.config import GOOGLE_API_KEY, LLM_MODEL, LLM_TEMPERATURE

# ─────────────────────────
# Helpers
# ─────────────────────────
def normalize_store_name(name: str) -> str:
    """가맹점명 정규화: 공백 제거"""
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

def check_forbidden_content(response: str) -> Tuple[bool, List[str]]:
    """금지 콘텐츠 체크"""
    forbidden_patterns = ["100% 보장", "무조건 성공", "확실한 효과", "절대", "반드시"]
    found = []
    low = (response or "").lower()
    for p in forbidden_patterns:
        if p.lower() in low:
            found.append(p)
    return len(found) == 0, found

# ─────────────────────────
# Store Name Extraction
# ─────────────────────────
def _extract_store_name_from_query(query: str) -> str:
    """
    사용자 쿼리에서 가맹점명 추출 (LLM 기반)
    """
    if not query:
        return ""
    
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from my_agent.utils.config import GOOGLE_API_KEY, LLM_MODEL
        
        llm = ChatGoogleGenerativeAI(
            model=LLM_MODEL,
            google_api_key=GOOGLE_API_KEY,
            temperature=0.0
        )
        
        prompt = f"""다음 질문에서 **가맹점명만** 정확히 추출하세요.
가맹점명이 없거나 불분명하면 "NONE"을 반환하세요.

규칙:
- 지점명 포함 가능 (예: "본죽 강남점" → "본죽 강남점")
- 시간 표현 제거 (예: "최근", "요즘", "이번 달")
- 수식어 제거 (예: "우리 동네", "근처")
- 순수 가맹점명만 반환

예시:
- "본죽 매출 어때?" → "본죽"
- "최근 본죽 마케팅 트렌드는?" → "본죽"
- "본죽 강남점 분석해줘" → "본죽 강남점"
- "우리 동네 카페 추천" → "NONE"
- "마케팅 전략 알려줘" → "NONE"

질문: {query}

가맹점명:"""
        
        response = llm.invoke(prompt).content.strip()
        result = "" if response.upper() == "NONE" else response
        
        print(f"[EXTRACT_STORE] LLM 추출 결과: '{query}' → '{result}'")
        return result
        
    except Exception as e:
        print(f"[EXTRACT_STORE] LLM 추출 실패: {e}")
        # 폴백: 간단한 휴리스틱
        return _extract_store_name_fallback(query)


def _extract_store_name_fallback(query: str) -> str:
    """
    폴백: 간단한 휴리스틱 방식
    """
    if not query:
        return ""
    
    # 노이즈 키워드 확장
    noise_keywords = {
        "매출", "분석", "어때", "알려줘", "보여줘", "추천", "전략",
        "마케팅", "현황", "상황", "문제", "이슈", "재방문", "sns",
        "어떻게", "왜", "뭐", "무엇", "우리", "동네", "근처",
        "최근", "요즘", "이번", "지난", "다음",  # ✅ 시간 표현 추가
        "트렌드", "사례", "방법"
    }
    
    words = query.split()
    clean_words = []
    
    for w in words:
        if not any(kw in w.lower() for kw in noise_keywords):
            clean_words.append(w)
        else:
            break
    
    result = " ".join(clean_words[:3]).strip()
    print(f"[EXTRACT_STORE] Fallback 추출 결과: '{query}' → '{result}'")
    return result

# ─────────────────────────
# Candidate Ranking
# ─────────────────────────
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

# ─────────────────────────
# User Info Builder
# ─────────────────────────
def _build_user_info(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """후보 데이터 → user_info 구조 변환"""
    return {
        "store_name": candidate.get("가맹점명", ""),
        "store_num": candidate.get("가맹점_구분번호", ""),
        "location": candidate.get("가맹점_주소", ""),
        "marketing_area": candidate.get("상권_지리", ""),
        "industry": candidate.get("업종", ""),
    }

# ─────────────────────────
# Store Resolver (가맹점 확정 + user_info 구성)
# ─────────────────────────
def resolve_store(state: GraphState) -> GraphState:
    """가맹점명 → store_id 해결"""
    
    if state.get("store_id"):
        print(f"[RESOLVER] ✅ store_id 이미 존재: {state.get('store_id')}")
        state["need_clarify"] = False
        return state
    
    store_name = (state.get("store_name_input") or "").strip()
    
    if not store_name:
        user_query = (state.get("user_query") or "").strip()
        store_name = _extract_store_name_from_query(user_query)
    
    print(f"[RESOLVER DEBUG] 가맹점 검색 시작")
    print(f"[RESOLVER DEBUG] 입력된 가맹점명: '{store_name}'")
    print("="*60)

    if not store_name:
        state["error"] = "가맹점명을 찾을 수 없습니다. 가맹점명을 명확히 말씀해주세요."
        state["need_clarify"] = False  # ✅ True → False (에러는 clarify가 아님)
        return state
    
    try:
        result = call_mcp_tool("search_merchant", merchant_name=store_name)
        print(f"[RESOLVER] 검색 결과: found={result.get('found')}, count={result.get('count')}")
    except Exception as e:
        state["error"] = f"검색 실패: {e}"
        state["need_clarify"] = False  # ✅ True → False
        return state
    
    if not result.get("found"):
        state["error"] = f"'{store_name}'에 해당하는 가맹점을 찾을 수 없습니다"
        state["need_clarify"] = False  # ✅ True → False
        return state
        
    candidates = result.get("merchants", [])
    state["store_candidates"] = candidates
    ranked = _rank_candidates(candidates, store_name)
    
    print(f"[RESOLVER] 후보 수: {len(ranked)}, CONFIRM_ON_MULTI: {cfg.CONFIRM_ON_MULTI}")

    # ✅ 후보가 없거나 1개면 clarify 불필요
    if len(ranked) == 0:
        state["error"] = f"'{store_name}'에 해당하는 가맹점을 찾을 수 없습니다"
        state["need_clarify"] = False
        return state
    
    if len(ranked) == 1:
        # 후보 1개 → 자동 확정
        best = ranked[0]
        state["store_id"] = str(best.get("가맹점_구분번호", ""))
        state["user_info"] = _build_user_info(best)
        state["need_clarify"] = False
        print(f"[RESOLVER] ✅ 가맹점 자동 확정: {state['user_info']['store_name']}")
        return state

    # ✅ 후보 2개 이상 → clarify
    if cfg.CONFIRM_ON_MULTI and len(ranked) > 1:
        print(f"[RESOLVER] ⚠️ 다중 후보 감지 → need_clarify=True")
        state["need_clarify"] = True
        state["final_response"] = "후보가 여러 개입니다. 지점을 선택해주세요."
        return state

    # CONFIRM_ON_MULTI=False면 첫 번째 후보 자동 선택
    best = ranked[0]
    state["store_id"] = str(best.get("가맹점_구분번호", ""))
    state["user_info"] = _build_user_info(best)
    state["need_clarify"] = False
    print(f"[RESOLVER] ✅ 가맹점 확정: {state['user_info']['store_name']}")
    
    return state

# ─────────────────────────
# Data Loader (store + bizarea [+ region 옵션])
# ─────────────────────────
def load_store_and_area_data(state: GraphState, include_region: bool = False, latest_only: bool = True) -> GraphState:
    """
    store_id 기준으로 store_data + bizarea_data 조회
    include_region=True 로 지정한 경우 region_data도 조회
    (기본값 False → 의도적으로 조회하지 않음)
    """
    store_id = state.get("store_id")
    if not store_id:
        state["error"] = "store_id가 없습니다. 먼저 가맹점을 선택하세요."
        return state

    # 1) store_data (최신 1건)
    res_store = call_mcp_tool("load_store_data", store_id=store_id, latest_only=latest_only)
    if not res_store.get("success"):
        state["error"] = res_store.get("error", "가맹점 데이터 조회 실패")
        return state
    state["store_data"] = res_store["data"]

    # 2) bizarea_data (상권)
    try:
        res_biz = call_mcp_tool("load_bizarea_data", store_row=state["store_data"])
        state["bizarea_data"] = res_biz["data"] if res_biz.get("success") else None
    except Exception:
        state["bizarea_data"] = None

    # 3) region_data (옵션)
    if include_region:
        try:
            res_region = call_mcp_tool("load_region_data", store_row=state["store_data"])
            state["region_data"] = res_region["data"] if res_region.get("success") else None
        except Exception:
            state["region_data"] = None

    return state

# ─────────────────────────
# Data Loader (store + bizarea [+ region 옵션])
# ─────────────────────────
def load_store_and_area_data(state: GraphState, include_region: bool = False, latest_only: bool = True) -> GraphState:
    """
    store_id 기준으로 store_data + bizarea_data 조회
    include_region=True 로 지정한 경우 region_data도 조회
    (기본값 False → 의도적으로 조회하지 않음)
    """
    store_id = state.get("store_id")
    if not store_id:
        state["error"] = "store_id가 없습니다. 먼저 가맹점을 선택하세요."
        return state

    # 1) store_data (최신 1건)
    res_store = call_mcp_tool("load_store_data", store_id=store_id, latest_only=latest_only)
    if not res_store.get("success"):
        state["error"] = res_store.get("error", "가맹점 데이터 조회 실패")
        return state
    state["store_data"] = res_store["data"]

    # 2) bizarea_data (상권)
    try:
        res_biz = call_mcp_tool("load_bizarea_data", store_row=state["store_data"])
        state["bizarea_data"] = res_biz["data"] if res_biz.get("success") else None
    except Exception:
        state["bizarea_data"] = None

    # 3) region_data (옵션) -> False로 하면 아예 안 불러와짐 (기본이 False)
    if include_region:
        try:
            res_region = call_mcp_tool("load_region_data", store_row=state["store_data"])
            state["region_data"] = res_region["data"] if res_region.get("success") else None
        except Exception:
            state["region_data"] = None

    return state