# my_agent/metrics/cooperation_metrics.py
# -*- coding: utf-8 -*-
"""
Cooperation Metrics Builder (길동무 전용)
- 동일 상권 내 비경쟁 업종과 협업 가능성을 평가하는 지표 생성
- main_metrics / strategy_metrics 에 없는 store 중심 고객 유사도 지표 추가
"""

import pandas as pd
import numpy as np
from typing import Dict, Any
from my_agent.utils.tools import load_store_and_area_data
from my_agent.metrics.main_metrics import _safe, _drop_na_metrics


def build_cooperation_metrics(store_num: str) -> Dict[str, Any]:
    """협업 가능성 평가용 메트릭 (고객 유사도 + 상권 안정성)"""
    state = {"store_id": store_num}
    state = load_store_and_area_data(state, include_region=False, latest_only=True)

    store = state.get("store_data", {})
    bizarea = state.get("bizarea_data", {})
    if not store or not bizarea:
        raise ValueError("store_data or bizarea_data not found.")

    coop_metrics = {
        # ---- 고객층 유사도 기반 ----
        "핵심고객_1순위": _safe(store.get("핵심고객_1순위")),
        "핵심고객_2순위": _safe(store.get("핵심고객_2순위")),
        "핵심고객_3순위": _safe(store.get("핵심고객_3순위")),
        "거주고객_비중": _safe(store.get("거주고객_비중")),
        "직장고객_비중": _safe(store.get("직장고객_비중")),
        "유동인구고객_비중": _safe(store.get("유동인구고객_비중")),
        "배달매출_비중": _safe(store.get("배달매출_비중")),

        # ---- 상권 안정성 및 소비 여력 ----
        "상권 단위 점포_수": _safe(bizarea.get("점포_수")),
        "상권 단위 상권활력_지수": _safe(bizarea.get("상권활력_지수")),
        "상권 단위 총_직장_인구_수": _safe(bizarea.get("총_직장_인구_수")),
        "상권 단위 총_상주인구_수": _safe(bizarea.get("총_상주인구_수")),
        "상권 단위 월_평균_소득_금액": _safe(bizarea.get("월_평균_소득_금액")),
        "상권 단위 폐업률": _safe(bizarea.get("폐업_률")),
    }

    coop_metrics = _drop_na_metrics(coop_metrics)

    # ---- 파생 지표 계산 ----
    try:
        # 고객군 균형도 (거주/직장/유동이 비슷할수록 +)
        flow_mix = np.std([
            coop_metrics.get("거주고객_비중", 0),
            coop_metrics.get("직장고객_비중", 0),
            coop_metrics.get("유동인구고객_비중", 0)
        ])
        customer_balance = max(0, 1 - flow_mix)  # 0~1 범위

        # 상권 안정성 (활력/폐업률 기반)
        vitality = (coop_metrics.get("상권 단위 상권활력_지수", 0) / 100)
        close_rate = coop_metrics.get("상권 단위 폐업률", 0) or 0
        stability = max(0, vitality - close_rate * 0.5)

        # 최종 협업 잠재 점수 (고객 + 상권)
        coop_score = round(
            (customer_balance * 0.5 + stability * 0.3), 2
        )
        coop_metrics["협업_잠재_점수"] = min(1.0, max(0.0, coop_score))
    except Exception as e:
        coop_metrics["협업_잠재_점수"] = None

    return {"coop_metrics": coop_metrics}

if __name__ == "__main__":
    import sys, json
    if len(sys.argv) < 2:
        print("사용법: python -m my_agent.metrics.cooperation_metrics <STORE_ID>")
        # python -m my_agent.metrics.cooperation_metrics 761947ABD9
        sys.exit(1)

    store_id = sys.argv[1]
    result = build_cooperation_metrics(store_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))
