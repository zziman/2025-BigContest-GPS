# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np
import logging
"""
SNS Metrics Builder 
 입력:
  - store_num (str): 가맹점 고유 식별 번호

 출력(JSON):
  {
    "sns_node_metrics": {       # SNS 관련 핵심 지표
      "총_상주인구_수": float,
      "총_직장_인구_수": float,
      "남성_유동인구_수": float,
      "여성_유동인구_수": float,
      "상권_지리": str,
      "주중_매출_금액": float,
      "주말_매출_금액": float,
      "주력_연령대": str
    }
  }

"""

from typing import Dict, Any
from my_agent.utils.tools import load_store_and_area_data
from my_agent.metrics.main_metrics import _safe, _drop_na_metrics


def build_sns_metrics(store_num: str) -> Dict[str, Any]:
    """SNSNode용 핵심 지표 생성"""
    state = {"store_id": store_num}
    state = load_store_and_area_data(state, include_region=False, latest_only=True)

    store = state.get("store_data", {})
    bizarea = state.get("bizarea_data", {})

    if not store:
        raise ValueError("store_data not found. Check store_num.")
    if not bizarea:
        raise ValueError("bizarea_data not found.")

    sns_node_metrics = {
        # 방문 고객 특성
        "총_상주인구_수": _safe(bizarea.get("총_상주인구_수")),
        "총_직장_인구_수": _safe(bizarea.get("총_직장_인구_수")),
        "남성_유동인구_수": _safe(bizarea.get("남성_유동인구_수")),
        "여성_유동인구_수": _safe(bizarea.get("여성_유동인구_수")),

        # 상권 및 피크 정보
        "상권_지리": _safe(bizarea.get("상권_지리")),

        # 매출·서비스 구조
        "주중_매출_금액": _safe(bizarea.get("주중_매출_금액")),
        "주말_매출_금액": _safe(bizarea.get("주말_매출_금액")),
        "주력_연령대": _safe(bizarea.get("주력_연령대"))
    }

    return {"sns_node_metrics": _drop_na_metrics(sns_node_metrics)}


if __name__ == "__main__":
    import sys, json

    if len(sys.argv) < 2:
        print("사용법: python -m my_agent.metrics.sns_metrics <STORE_ID>")
        # python -m my_agent.metrics.sns_metrics 761947ABD9
        sys.exit(1)

    store_id = sys.argv[1]
    result = build_sns_metrics(store_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))
