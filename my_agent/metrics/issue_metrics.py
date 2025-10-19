# my_agent/metrics/issue_metrics.py

# -*- coding: utf-8 -*-
"""
Issue Metrics Builder (peer-free version using store data)
입력: store_num (가맹점 구분 번호)
동작:
    - utils/tools.py → load_store_and_area_data 사용
    - 최신 store 데이터에서 ISSUE 핵심 지표 추출
    - 이상지표 탐지 (템플릿 기반, 간결 출력)
출력:
    {
      "issue_metrics": {...},
      "abnormal_metrics": {...},
      "issue_risk_score": int,
      "yyyymm": str
    }
"""

from typing import Dict, Any, List
from my_agent.utils.tools import load_store_and_area_data

# 피어 비교 지표 목록 (노드별로 공통 사용 -> 이상치 피어 비교에서 사용할 지표 목록)
PEER_COMPARE_FEATURES = [
    "배달매출비중_차이_pp",
    "단골비중_차이_pp",
    "신규비중_차이_pp",
    "배달비중_백분위",
    "단골비중_백분위",
    "신규비중_백분위",
    "업종매출지수_백분위",
    "업종건수지수_백분위",
    "업종매출_편차",
    "업종건수_편차"
]


def _safe(x, default=0.0):
    try:
        return float(x) if x not in [None, ""] else default
    except:
        return default


def build_issue_metrics(store_num: str) -> Dict[str, Any]:
    """ISSUE 핵심 메트릭 생성"""
    state = {"store_id": store_num}
    state = load_store_and_area_data(state, include_region=False, latest_only=True)  
    ## latest_only False면 해당 가맹점 모든 행 불러오고 True면 최신만 불러오게 됨
    ## include_region은 행정동 데이터를 추가 하냐 마냐 (기본 False)

    store = state.get("store_data")
    if not store:
        raise ValueError("store_data not found. Check store_num.")

    yyyymm = store.get("기준년월")

    # 핵심 ISSUE 지표 수집
    issue_metrics = {
        "단골손님_비중": _safe(store.get("단골손님_비중")),
        "신규손님_비중": _safe(store.get("신규손님_비중")),
        "배달매출_비중": _safe(store.get("배달매출_비중")),
        "거주고객_비중": _safe(store.get("거주고객_비중")),
        "직장고객_비중": _safe(store.get("직장고객_비중")),
        "유동인구고객_비중": _safe(store.get("유동인구고객_비중")),
        "단골비중_3개월_순증감_pp": _safe(store.get("단골비중_3개월_순증감_pp")),
        "배달비중_3개월_순증감_pp": _safe(store.get("배달비중_3개월_순증감_pp")),
        "신규비중_3개월_순증감_pp": _safe(store.get("신규비중_3개월_순증감_pp")),
        "단골비중_YoY_pp": _safe(store.get("단골비중_YoY_pp")),
        "배달비중_YoY_pp": _safe(store.get("배달비중_YoY_pp")),
        "신규비중_YoY_pp": _safe(store.get("신규비중_YoY_pp"))
    }

    # 이상치 탐지 (간결한 지표 기반 템플릿)
    abnormal = {}

    # 1) 시계열 이상치
    if issue_metrics["단골비중_3개월_순증감_pp"] <= -5:
        abnormal["단골손님"] = f"최근 3개월 {-issue_metrics['단골비중_3개월_순증감_pp']:.1f}pp 감소"
    if issue_metrics["배달비중_3개월_순증감_pp"] >= 5:
        abnormal["배달비중"] = f"최근 3개월 +{issue_metrics['배달비중_3개월_순증감_pp']:.1f}pp 증가"
    if issue_metrics["신규비중_3개월_순증감_pp"] <= -5:
        abnormal["신규고객"] = f"최근 3개월 {-issue_metrics['신규비중_3개월_순증감_pp']:.1f}pp 감소"

    # 2) 피어 비교 이상치
    for key in PEER_COMPARE_FEATURES:
        if key in store and abs(_safe(store.get(key))) >= 10:
            abnormal[key] = f"동일 상권·업종 대비 {store.get(key):+.1f}"

    # 3) 데이터 논리 기반 이상치
    if issue_metrics["배달매출_비중"] >= 0.65:
        abnormal["배달 의존"] = "배달 비중 과도"
    if issue_metrics["단골손님_비중"] < 0.18:
        abnormal["단골 부족"] = "단골 비중 낮음"

    # 위험 점수 (이상 지표 개수 기반 단순 계산)
    risk_score = min(100, 50 + len(abnormal) * 5)

    return {
        "issue_metrics": issue_metrics,
        "abnormal_metrics": abnormal,
        "issue_risk_score": risk_score,
        "yyyymm": yyyymm
    }


if __name__ == "__main__":
    import sys, json

    if len(sys.argv) < 2:
        print("사용법: python -m my_agent.metrics.issue_metrics <STORE_ID>")
        # python -m my_agent.metrics.issue_metrics 761947ABD9
        sys.exit(1)

    store_id = sys.argv[1]
    result = build_issue_metrics(store_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))