# my_agent/metrics/main_metrics.py

# -*- coding: utf-8 -*-
"""
Main Metrics Builder 
입력: store_num (가맹점 구분 번호)
동작:
    - utils/tools.py → load_store_and_area_data 사용
    - store,bizarea 데이터에서 Main 핵심 지표 추출
출력:
    {
      "main_metrics": {...},
      "상권_단위_정보": {...},
      "yyyymm": str
    }
"""
import numpy as np 
from typing import Dict, Any, List
from my_agent.utils.tools import load_store_and_area_data


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
    return {k: v for k, v in d.items() if v is not None and not (isinstance(v, float) and np.isnan(v))}


def build_main_metrics(store_num: str) -> Dict[str, Any]:
    """Main 메트릭 생성"""
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

    # 핵심 MAIN 지표 수집
    main_metrics = {
        "핵심고객_1순위": _safe(store.get("핵심고객_1순위")),
        "핵심고객_2순위": _safe(store.get("핵심고객_2순위")),
        "거주고객_비중": _safe(store.get("거주고객_비중")),
        "직장고객_비중": _safe(store.get("직장고객_비중")),
        "유동인구고객_비중": _safe(store.get("유동인구고객_비중")),
        "배달매출_비중": _safe(store.get("배달매출_비중")),
        "신규손님_비중": _safe(store.get("신규손님_비중")),
        "단골손님_비중": _safe(store.get("단골손님_비중")),
        "매출금액_구간(6개구간)": _safe(store.get("매출금액_구간"))}

    main_metrics = _drop_na_metrics(main_metrics)

    bizarea_metrics = {
        "평균거래단가": _safe(bizarea.get("평균거래단가")),
        "총_유동인구_수": _safe(bizarea.get("총_유동인구_수")),
        "상권활력_지수": _safe(bizarea.get("상권활력_지수")),
        "유동인구_YoY": _safe(bizarea.get("유동인구_YoY")),
        "접근성_점수": _safe(bizarea.get("접근성_점수")),
        "피크_요일": _safe(bizarea.get("피크_요일")),
        "피크_시간대": _safe(bizarea.get("피크_시간대")),
        "유사_업종_점포_수": _safe(bizarea.get("유사_업종_점포_수"))
        }
    
    bizarea_metrics = _drop_na_metrics(bizarea_metrics)


    return {
        "main_metrics": main_metrics,
        "상권_단위_정보": bizarea_metrics
    }


if __name__ == "__main__":
    import sys, json

    if len(sys.argv) < 2:
        print("사용법: python -m my_agent.metrics.main_metrics <STORE_ID>")
        # python -m my_agent.metrics.main_metrics 761947ABD9
        sys.exit(1)

    store_id = sys.argv[1]
    result = build_main_metrics(store_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))
