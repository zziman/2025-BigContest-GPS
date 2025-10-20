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

from typing import Dict, Any, List
from my_agent.utils.tools import load_store_and_area_data

def _safe(x, default=0.0):
    # 빈 문자열 또는 None 처리
    if x in [None, ""]:
        return default
    # 숫자 타입일 경우 float 변환
    if isinstance(x, (int, float)):
        return float(x)
    # 문자열이나 기타 타입은 그대로 반환
    return x


def build_strategy_metrics(store_num: str) -> Dict[str, Any]:
    """strategy 메트릭 생성"""
    state = {"store_id": store_num}
    state = load_store_and_area_data(state, include_region=False, latest_only=True)  
    ## latest_only False면 해당 가맹점 모든 행 불러오고 True면 최신만 불러오게 됨
    ## include_region은 행정동 데이터를 추가 하냐 마냐 (기본 False)

    store = state.get("store_data")
    bizarea = state.get("bizarea_data")
    if not store:
        raise ValueError("store_data not found. Check store_num.")
    if not bizarea:
        raise ValueError("bizarea_data not found.")

    # 전략 강도 지표 수집
    strategy_metrics = {
        "취소율_구간": _safe(store.get("취소율_구간")),
        "상권과_이동성_적합도": _safe(store.get("이동성_적합도")),
        "상권과_연령대_적합도": _safe(store.get("연령대_적합도"))}


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