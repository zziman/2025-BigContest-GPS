# my_agent/metrics/general_metrics.py
# -*- coding: utf-8 -*-
"""
General Metrics Builder
- 목적: General 노드 전용 보조 지표 (경쟁력 비교 + 상권 환경)
- 특징: Main/Strategy/user_info와 중복 없음
"""

import numpy as np
import pandas as pd
from typing import Dict, Any
from my_agent.utils.tools import load_store_and_area_data


# ─────────────────────────
# Helpers
# ─────────────────────────
def _safe(x, default=None):
    """결측값 처리 (NaN, None 등) → default"""
    if x is None:
        return default
    try:
        if pd.isna(x) or (isinstance(x, str) and x.strip() in ["", "NaN", "nan", "None"]):
            return default
    except Exception:
        pass
    return x


def _safe_float(x, default=0.0) -> float:
    """안전한 float 변환"""
    try:
        if x is None or x == "":
            return default
        return float(x)
    except (ValueError, TypeError):
        return default


def _safe_int(x, default=0) -> int:
    """안전한 int 변환"""
    try:
        if x is None or x == "":
            return default
        return int(x)
    except (ValueError, TypeError):
        return default


def _drop_na_metrics(d: Dict[str, Any]) -> Dict[str, Any]:
    """NaN/None 값을 가진 항목은 제외"""
    return {
        k: v for k, v in d.items() 
        if v is not None and not (isinstance(v, float) and np.isnan(v))
    }


# ─────────────────────────
# Main Builder
# ─────────────────────────
def build_general_metrics(store_num: str) -> Dict[str, Any]:
    """
    General 노드용 보조 지표 (6개)
    - 경쟁력 비교: 업종/상권 내 순위, 편차, 리스크
    - 상권 환경: 경쟁 강도, 상권 폐업률
    
    Returns:
        {
            "general_metrics": {
                "업종매출지수_백분위": ...,
                "동일_상권_내_매출_순위_비율": ...,
                ...
            },
            "yyyymm": "202501"
        }
    """
    # 데이터 로드
    state = {"store_id": store_num}
    state = load_store_and_area_data(state, include_region=False, latest_only=True)
    
    store = state.get("store_data")
    biz = state.get("bizarea_data")
    
    if not store:
        raise ValueError(f"store_data not found for store_num={store_num}")
    
    yyyymm = _safe(store.get("기준년월"), "정보없음")
    
    # ═════════════════════════════════════════
    # 1. 경쟁력 비교 (4개)
    # ═════════════════════════════════════════
    general_metrics = {
        "업종매출지수_백분위": _safe_float(store.get("업종매출지수_백분위"), None),
        "동일_상권_내_매출_순위_비율": _safe_float(store.get("동일_상권_내_매출_순위_비율"), None),
        "업종매출_편차": _safe_float(store.get("업종매출_편차"), None),
        "동일_업종_내_해지_가맹점_비중": _safe_float(store.get("동일_업종_내_해지_가맹점_비중"), None),
    }
    
    # ═════════════════════════════════════════
    # 2. 상권 환경 (2개)
    # ═════════════════════════════════════════
    if biz and isinstance(biz, dict):
        general_metrics.update({
            "상권단위_유사_업종_점포_수": _safe_int(biz.get("유사_업종_점포_수"), None),
            "상권단위_폐업_률": _safe_float(biz.get("폐업_률"), None),
        })
    
    # NaN 제거
    general_metrics = _drop_na_metrics(general_metrics)
    
    return {
        "general_metrics": general_metrics,
        "yyyymm": yyyymm
    }


# ─────────────────────────
# CLI Test
# ─────────────────────────
if __name__ == "__main__":
    import sys, json
    
    if len(sys.argv) < 2:
        print("사용법: python -m my_agent.metrics.general_metrics <STORE_ID>")
        print("예시: python -m my_agent.metrics.general_metrics 761947ABD9")
        sys.exit(1)
    
    store_id = sys.argv[1]
    
    try:
        result = build_general_metrics(store_id)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"❌ 에러 발생: {e}")
        import traceback
        traceback.print_exc()