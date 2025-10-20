# my_agent/metrics/general_metrics.py
# -*- coding: utf-8 -*-
"""
General Metrics Builder
- 목적: General 노드에서 사용할 폭넓은 상황 설명용 기본 지표 생성
- 데이터 출처: mcp.tools.load_store_and_area_data
"""

from typing import Dict, Any
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


def _format_percent(val):
    try:
        return f"{float(val) * 100:.1f}%"
    except:
        return None


def _top_demographics(store: Dict[str, Any]) -> str:
    """연령대 + 성별 통합한 주요 고객층 표현"""
    age_cols = [
        ("남성_20대이하_고객_비중", "남성 10~20대"),
        ("남성_30대_고객_비중", "남성 30대"),
        ("남성_40대_고객_비중", "남성 40대"),
        ("여성_20대이하_고객_비중", "여성 10~20대"),
        ("여성_30대_고객_비중", "여성 30대"),
        ("여성_40대_고객_비중", "여성 40대"),
    ]
    sorted_age = sorted(
        [(label, _safe(store.get(col), 0)) for col, label in age_cols],
        key=lambda x: x[1],
        reverse=True
    )
    if sorted_age:
        return f"{sorted_age[0][0]} 중심"
    return "정보 부족"


def build_general_metrics(store_num: str) -> Dict[str, Any]:
    """General 노드용 기본 설명형 지표 생성"""
    state = {"store_id": store_num}
    state = load_store_and_area_data(state, include_region=False, latest_only=True)

    store = state.get("store_data")
    biz = state.get("bizarea_data")
    if not store:
        raise ValueError("store_data not found. store_num을 확인하세요.")

    yyyymm = store.get("기준년월")

    general_metrics = {
        "가게_운영특성": {
            "운영기간": f"{_safe(store.get('영업_경과_개월'), 'N/A')}개월",
            "브랜드형태": "프랜차이즈" if _safe(store.get("브랜드구분코드")) == "F" else "개인점",
            "업종": _safe(store.get("업종"), "정보 없음"),
            "상권유형": _safe(store.get("상권유형_지리"), "정보 없음"),
        },
        "고객_구성": {
            "핵심고객특징": _top_demographics(store),
            "재방문고객비율": _format_percent(store.get("재방문_고객_비중")),
            "신규고객비율": _format_percent(store.get("신규_고객_비중")),
            "거주/직장고객비중": f"{_format_percent(store.get('거주_이용_고객_비중'))} / {_format_percent(store.get('직장_이용_고객_비중'))}",
        },
        "상권_특성": {
            "상권지리": _safe(store.get("상권_지리"), "정보 없음"),
            "접근성": f"{_safe(biz.get('접근성_점수'), 'N/A')}" if biz else "정보 없음",
            "활성도": f"유동인구 {_safe(biz.get('총_유동인구_수'), 'N/A'):,}명" if biz else "정보 없음",
            "경쟁강도": f"유사업종 {_safe(biz.get('유사_업종_점포_수'), 'N/A')}개" if biz else "정보 없음",
        }
    }

    return {"general_metrics": general_metrics, "yyyymm": yyyymm}

if __name__ == "__main__":
    import sys, json
    if len(sys.argv) < 2:
        print("사용법: python -m my_agent.metrics.general_metrics <STORE_ID>")
        # python -m my_agent.metrics.general_metrics 761947ABD9
        sys.exit(1)

    store_id = sys.argv[1]
    result = build_general_metrics(store_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))
