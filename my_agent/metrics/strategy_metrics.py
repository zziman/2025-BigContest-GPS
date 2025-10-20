# my_agent/metrics/strategy_metrics.py

# -*- coding: utf-8 -*-
"""
Strategy Metrics Builder 
입력: store_num (가맹점 구분 번호)
동작:
    - utils/tools.py → load_store_and_area_data 사용
    - store 데이터에서 전략 강도 지표 추출
출력:
    {
      "strategy_metrics": {...}
    }
"""
import numpy as np
from typing import Dict, Any, List
from my_agent.utils.tools import load_store_and_area_data

def _safe(x):
    """결측값 처리 (NaN, None, 빈 문자열 등) → None"""
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
    return {k: v for k, v in d.items() if v is not None and not (isinstance(v, float) and np.isnan(v))}


def build_strategy_metrics(store_num: str) -> Dict[str, Any]:
    """strategy 메트릭 생성"""
    state = {"store_id": store_num}
    state = load_store_and_area_data(state, include_region=False, latest_only=True)  
    ## latest_only False면 해당 가맹점 모든 행 불러오고 True면 최신만 불러오게 됨
    ## include_region은 행정동 데이터를 추가 하냐 마냐 (기본 False)

    store = state.get("store_data")

    if not store:
        raise ValueError("store_data not found. Check store_num.")

    # 전략 강도 지표 수집
    strategy_metrics = {
        "취소율_구간(6개구간)": _safe(store.get("취소율_구간")),
        "상권과_이동성_적합도": _safe(store.get("이동성_적합도")),
        "상권과_연령대_적합도": _safe(store.get("연령대_적합도"))}

    strategy_metrics = _drop_na_metrics(strategy_metrics)

    return {
        "strategy_metrics": strategy_metrics
    }

if __name__ == "__main__":
    import sys, json

    if len(sys.argv) < 2:
        print("사용법: python -m my_agent.metrics.strategy_metrics <STORE_ID>")
        # python -m my_agent.metrics.strategy_metrics 761947ABD9
        sys.exit(1)

    store_id = sys.argv[1]
    result = build_strategy_metrics(store_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))
