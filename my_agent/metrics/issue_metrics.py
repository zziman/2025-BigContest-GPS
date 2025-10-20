# my_agent/metrics/issue_metrics.py

# -*- coding: utf-8 -*-
from typing import Dict, Any
from my_agent.utils.tools import load_store_and_area_data
from my_agent.metrics.main_metrics import _safe, _drop_na_metrics


def add_metric_if(abnormal_dict, key, value, condition_fn, message_fn):
    """value가 None이 아니고 조건이 맞으면 메시지를 추가"""
    if value is None:
        return
    try:
        if condition_fn(value):
            abnormal_dict[key] = message_fn(value)
    except:
        pass


def build_issue_metrics(store_num: str) -> Dict[str, Any]:
    state = {"store_id": store_num}
    state = load_store_and_area_data(state, include_region=False, latest_only=True)

    store = state.get("store_data")
    area = state.get("area_data")
    if not store:
        raise ValueError("store_data not found. Check store_num.")

    yyyymm = store.get("기준년월")

    # ISSUE METRICS
    issue_metrics = {
        "동일_업종_매출금액_비율": _safe(store.get("동일_업종_매출금액_비율")),
        "동일_상권_내_매출_순위_비율": _safe(store.get("동일_상권_내_매출_순위_비율")),
        "배달매출_비중": _safe(store.get("배달매출_비중")),
    }

    abnormal_metrics = {}

    # 1. 시계열 이상치
    val = _safe(store.get("신규비중_YoY_pp"))
    add_metric_if(abnormal_metrics, "신규고객_이탈", val, lambda v: v < -22.45,
                  lambda v: f"신규비중 YoY {v:.1f}pp 감소")

    val = _safe(store.get("신규비중_3개월_추세_pp_per_m"))
    add_metric_if(abnormal_metrics, "신규고객_단기하락", val, lambda v: v < -7.81,
                  lambda v: f"최근 3개월 {v:.1f}pp 감소 추세")

    val = _safe(store.get("단골비중_YoY_pp"))
    add_metric_if(abnormal_metrics, "단골고객_이탈", val, lambda v: v < -3.68,
                  lambda v: f"단골비중 YoY {v:.1f}pp 감소")

    val = _safe(store.get("단골비중_3개월_추세_pp_per_m"))
    add_metric_if(abnormal_metrics, "단골고객_단기하락", val, lambda v: v < -1.75,
                  lambda v: f"최근 3개월 {v:.1f}pp 감소 추세")

    val = _safe(store.get("배달비중_YoY_pp"))
    add_metric_if(abnormal_metrics, "배달의존_증가", val, lambda v: v > 10.22,
                  lambda v: f"배달비중 YoY +{v:.1f}pp 증가")

    val = _safe(area.get("매출_YoY") if area else None)
    add_metric_if(abnormal_metrics, "상권_매출감소", val, lambda v: v < 0,
                  lambda v: f"상권 매출 YoY {v:.1f}% 감소")

    val = _safe(area.get("유동인구_YoY") if area else None)
    add_metric_if(abnormal_metrics, "유동인구_감소", val, lambda v: v < 0,
                  lambda v: f"유동인구 YoY {v:.1f}% 감소")

    # 2. 피어 비교 이상치
    val = _safe(store.get("배달매출비중_차이_pp"))
    add_metric_if(abnormal_metrics, "배달전략_편차", val, lambda v: abs(v) > 14.76,
                  lambda v: f"업종 대비 {v:+.1f}pp 차이")

    val = _safe(store.get("단골비중_차이_pp"))
    add_metric_if(abnormal_metrics, "단골비중_편차", val, lambda v: abs(v) > 8.69,
                  lambda v: f"업종 대비 {v:+.1f}pp 차이")

    val = _safe(store.get("배달비중_백분위"))
    add_metric_if(abnormal_metrics, "배달채널_불균형", val, lambda v: v < 35.66 or v > 89.51,
                  lambda v: f"배달비중 백분위 {v:.1f}% (극단값)")

    val = _safe(store.get("업종매출지수_백분위"))
    add_metric_if(abnormal_metrics, "업종매출경쟁력_낮음", val, lambda v: v < 67.32,
                  lambda v: f"업종 내 매출 하위 {v:.0f}%")

    val = _safe(store.get("업종건수지수_백분위"))
    add_metric_if(abnormal_metrics, "업종회전력_낮음", val, lambda v: v < 58.19,
                  lambda v: f"업종 내 건수 하위 {v:.0f}%")

    # 3. 논리 기반 이상치
    val = _safe(store.get("취소율_구간"))
    add_metric_if(abnormal_metrics, "취소율_높음", val, lambda v: v >= 5,
                  lambda v: f"취소율 구간 {v} (높음)")

    val = _safe(store.get("동일_업종_매출건수_비율"))
    add_metric_if(abnormal_metrics, "거래수_이상", val, lambda v: v < 6.85 or v > 679.75,
                  lambda v: f"동일업종 대비 거래수 비정상 ({v:.1f})")

    val = _safe(store.get("동일_업종_내_매출_순위_비율"))
    add_metric_if(abnormal_metrics, "매출순위_하위", val, lambda v: v > 17.29,
                  lambda v: f"업종 내 매출 하위 {v:.1f}%")

    val = _safe(store.get("동일_업종_내_해지_가맹점_비중"))
    add_metric_if(abnormal_metrics, "업종해지율_위험", val, lambda v: v > 20.11,
                  lambda v: f"동일 업종 내 해지 {v:.1f}%")

    val = _safe(store.get("동일_상권_내_해지_가맹점_비중"))
    add_metric_if(abnormal_metrics, "상권해지율_위험", val, lambda v: v > 9.88,
                  lambda v: f"상권 내 해지 {v:.1f}%")

    val = _safe(store.get("단골손님_비중"))
    add_metric_if(abnormal_metrics, "단골부족", val, lambda v: v < 0.089,
                  lambda v: f"단골 고객 비중 낮음 ({v:.2f})")

    val = _safe(store.get("배달매출_비중"))
    add_metric_if(abnormal_metrics, "배달의존위험", val, lambda v: v > 0.346,
                  lambda v: f"배달 매출 의존 높음 ({v:.2f})")

    # 결과 정리
    issue_metrics = _drop_na_metrics(issue_metrics)
    abnormal_metrics = _drop_na_metrics(abnormal_metrics)

    return {
        "issue_metrics": issue_metrics,
        "abnormal_metrics": abnormal_metrics,
        "yyyymm": yyyymm
    }


if __name__ == "__main__":
    import sys, json
    if len(sys.argv) < 2:
        print("사용법: python -m my_agent.metrics.issue_metrics <STORE_ID>")
        sys.exit(1)

    store_id = sys.argv[1]
    result = build_issue_metrics(store_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))
