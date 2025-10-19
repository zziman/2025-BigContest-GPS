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
import re
import pandas as pd

from my_agent.utils.config import CONFIRM_ON_MULTI
from my_agent.utils.state import GraphState
from mcp.adapter_client import call_mcp_tool


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
# Store Resolver (가맹점 확정 + user_info 구성)
# ─────────────────────────
def resolve_store(state: GraphState) -> GraphState:
    """
    state["user_query"] 안에서 가맹점명 추출 → 검색 → store_id + user_info 생성
    """
    store_name = (state.get("store_name_input") or "").strip()
    if not store_name:
        state["error"] = "가맹점명을 입력해주세요."
        state["need_clarify"] = True
        return state

    try:
        result = call_mcp_tool("search_merchant", merchant_name=store_name)
    except Exception as e:
        state["error"] = f"검색 실패: {e}"
        state["need_clarify"] = True
        return state

    if not result.get("found"):
        state["error"] = f"'{store_name}'에 해당하는 가맹점을 찾을 수 없습니다."
        state["need_clarify"] = True
        return state

    candidates = result.get("merchants", [])
    state["store_candidates"] = candidates
    ranked = _rank_candidates(candidates, store_name)

    # 여러 후보가 있으면 확인 요청 (환경설정에 따라)
    if CONFIRM_ON_MULTI and len(ranked) > 1:
        state["need_clarify"] = True
        state["final_response"] = "여러 가맹점이 검색되었습니다. 어느 지점을 말씀하시나요?"
        return state

    # 최적 후보 선택
    best = ranked[0]
    store_num = str(best.get("가맹점_구분번호", ""))  # 반드시 문자열화
    state["store_id"] = store_num

    # LLM 입력용 컨텍스트(user_info) 구성
    state["user_info"] = {
        "store_name": best.get("가맹점명"),
        "store_num": store_num,
        "location": best.get("가맹점_주소"),
        "marketing_area": best.get("상권_지리") or best.get("상권"),
        "industry": best.get("업종"),
    }

    state["need_clarify"] = False
    return state

def _rank_candidates(candidates: List[dict], query: str) -> List[dict]:
    """가맹점 후보 정렬 (정규화된 정확/접두 매칭 우선, 짧은 이름 우선)"""
    if not candidates:
        return []
    df = pd.DataFrame(candidates)
    q = normalize_store_name(query)
    df["_norm"] = df["가맹점명"].apply(normalize_store_name)
    df["_exact"] = (df["_norm"] == q).astype(int)
    df["_prefix"] = df["_norm"].str.startswith(q).astype(int)
    df["_len"] = df["가맹점명"].str.len()
    df = df.sort_values(by=["_exact", "_prefix", "_len", "가맹점명"], ascending=[False, False, True, True])
    return df.to_dict("records")


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