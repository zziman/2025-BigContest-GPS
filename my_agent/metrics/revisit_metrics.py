# my_agent/metrics/revisit_metrics.py

# -*- coding: utf-8 -*-
"""
Revisit Metrics Builder
입력: store_num (가맹점 구분 번호)
동작:
    - utils/tools.py → load_store_and_area_data 사용
    - 재방문 관련 핵심 지표와 이상치 탐지 결과 생성
출력:
    {
      "revisit_metrics": {...},     # (이상치가 아니어도) 내려줄 지표
      "abnormal_metrics": {...},    # 이상치로 감지된 항목만 메시지 포함
      "yyyymm": "YYYYMM"
    }
"""

from typing import Dict, Any
import numpy as np
import pandas as pd
from my_agent.utils.tools import load_store_and_area_data

# ───────── 유틸: 이 파일에 직접 정의 ─────────
def _safe(x):
    """결측값 처리 (NaN, None 등) → None"""
    if x is None:
        return None
    try:
        if pd.isna(x) or (isinstance(x, str) and x.strip() in ["", "NaN", "nan", "None"]):
            return None
    except Exception:
        pass
    return x

def _drop_na_metrics(d: Dict[str, Any]) -> Dict[str, Any]:
    """NaN/None 값을 가진 항목은 제외"""
    return {k: v for k, v in d.items()
            if v is not None and not (isinstance(v, float) and np.isnan(v))}

# ───────── 임계값(튜닝 지점) ─────────
LOYAL_YOY_DROP_PP_THRESH = -3.68                 # 단골비중 YoY 하락(pp)
LOYAL_3M_DELTA_PP_THRESH = -5.25                 # 단골비중 3개월 순증감(pp)
NEW_DIFF_PEER_ABS_THRESH = 8.0                   # 신규비중_차이_pp |x|>8.0pp
DELIV_DIFF_PEER_ABS_THRESH = 14.76               # 배달매출비중_차이_pp |x|>14.76pp
SALES_DEV_ABS_THRESH = 12.0                      # 업종매출_편차 |x|>12.0
COUNT_DEV_ABS_THRESH = 10.0                      # 업종건수_편차 |x|>10.0

def add_metric_if(abnormal_dict, key, value, condition_fn, message_fn):
    """value가 None이 아니고 조건이 맞으면 메시지를 추가"""
    if value is None:
        return
    try:
        if condition_fn(value):
            abnormal_dict[key] = message_fn(value)
    except Exception:
        pass

def build_revisit_metrics(store_num: str) -> Dict[str, Any]:
    """revisit 메트릭 생성"""
    state = {"store_id": store_num}
    state = load_store_and_area_data(state, include_region=False, latest_only=True)

    store = state.get("store_data")
    if not store:
        raise ValueError("store_data not found. Check store_num.")

    yyyymm = store.get("기준년월")

    # ───────── (이상치 X 어도) 항상 내려줄 지표 ─────────
    revisit_metrics = {
        "단골비중_차이_pp": _safe(store.get("단골비중_차이_pp")),
    }

    # ───────── 이상치 탐지 ─────────
    abnormal_metrics: Dict[str, Any] = {}

    # 1) 단골비중_YoY_pp
    val = _safe(store.get("단골비중_YoY_pp"))
    add_metric_if(
        abnormal_metrics,
        "단골고객_이탈",
        val,
        lambda v: v < LOYAL_YOY_DROP_PP_THRESH,
        lambda v: f"단골비중 YoY {v:.1f}pp 감소"
    )

    # 2) 단골비중_3개월_순증감_pp
    val = _safe(store.get("단골비중_3개월_순증감_pp"))
    add_metric_if(
        abnormal_metrics,
        "단골고객_단기하락",
        val,
        lambda v: v < LOYAL_3M_DELTA_PP_THRESH,
        lambda v: f"최근 3개월 {v:.1f}pp 감소"
    )

    # 3) 신규비중_차이_pp
    val = _safe(store.get("신규비중_차이_pp"))
    add_metric_if(
        abnormal_metrics,
        "신규비중_편차",
        val,
        lambda v: abs(v) > NEW_DIFF_PEER_ABS_THRESH,
        lambda v: f"업종 대비 신규비중 {v:+.1f}pp 편차"
    )

    # 4) 배달매출비중_차이_pp
    val = _safe(store.get("배달매출비중_차이_pp"))
    add_metric_if(
        abnormal_metrics,
        "배달전략_편차",
        val,
        lambda v: abs(v) > DELIV_DIFF_PEER_ABS_THRESH,
        lambda v: f"업종 대비 배달비중 {v:+.1f}pp 편차"
    )

    # 5) 업종매출_편차
    val = _safe(store.get("업종매출_편차"))
    add_metric_if(
        abnormal_metrics,
        "업종매출_편차_높음",
        val,
        lambda v: abs(v) > SALES_DEV_ABS_THRESH,
        lambda v: f"업종 매출 편차 {v:+.1f} (높음)"
    )

    # 6) 업종건수_편차
    val = _safe(store.get("업종건수_편차"))
    add_metric_if(
        abnormal_metrics,
        "업종건수_편차_높음",
        val,
        lambda v: abs(v) > COUNT_DEV_ABS_THRESH,
        lambda v: f"업종 건수 편차 {v:+.1f} (높음)"
    )

    # 결과 정리
    revisit_metrics = _drop_na_metrics(revisit_metrics)
    abnormal_metrics = _drop_na_metrics(abnormal_metrics)

    return {
        "revisit_metrics": revisit_metrics,
        "abnormal_metrics": abnormal_metrics,
        "yyyymm": yyyymm,
    }

if __name__ == "__main__":
    import sys, json
    if len(sys.argv) < 2:
        print("사용법: python -m my_agent.metrics.revisit_metrics <STORE_ID>")
        # 예: python -m my_agent.metrics.revisit_metrics 761947ABD9
        sys.exit(1)

    store_id = sys.argv[1]
    result = build_revisit_metrics(store_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))