# my_agent/metrics/season_metrics.py

# -*- coding: utf-8 -*-
"""
Season Metrics
- 날씨 + 계절 + 상권 시간대별 고객 패턴 분석
"""

from typing import Dict, Any
import pandas as pd
from datetime import datetime
from my_agent.utils.tools import load_store_and_area_data, get_weather_forecast_data


def build_season_metrics(store_id: str) -> Dict[str, Any]:
    """
    날씨 및 상권 기반 계절 지표 생성

    Returns
    -------
    {
        success: bool,
        season_metrics: {
            계절, 평균기온, 강수시간수, 날씨추세,
            상권_주요활성시간대, 고객패턴_요약, 업종, 메시지
        }
    }
    """
    print(f"[SEASON_METRICS] Build start for store_id={store_id}")

    # 매장 + 상권 데이터 로드
    state = {"store_id": store_id}
    state = load_store_and_area_data(state, include_region=False, latest_only=True)
    store = state.get("store_data", {})
    area = state.get("bizarea_data", {})

    if not store:
        return {"success": False, "error": "store_data not found"}

    lat = store.get("위도", 37.57)
    lon = store.get("경도", 126.98)

    # 날씨 데이터 불러오기
    weather = get_weather_forecast_data(lat, lon, days=3)
    if not weather.get("success"):
        return {
            "success": False,
            "error": f"날씨 조회 실패: {weather.get('message')}",
            "season_metrics": None
        }

    df = pd.DataFrame(weather["data"])
    df["기온(℃)"] = pd.to_numeric(df["기온(℃)"], errors="coerce")
    df["fcstDateTime"] = pd.to_datetime(df["fcstDateTime"])
    temp_avg = df["기온(℃)"].mean()
    rain_hours = (df["강수형태"] != "없음").sum()

    # 계절 판정
    m = datetime.now().month
    if m in [12, 1, 2]:
        season = "겨울"
    elif m in [3, 4, 5]:
        season = "봄"
    elif m in [6, 7, 8]:
        season = "여름"
    else:
        season = "가을"

    weather_trend = (
        "맑음 유지" if rain_hours == 0 else
        "간헐적 비" if rain_hours < 4 else
        "비 많음"
    )

    # 상권 시간대별 고객 흐름 분석
    time_keys = [
        "시간대_건수~06_매출_건수",
        "시간대_건수~11_매출_건수",
        "시간대_건수~14_매출_건수",
        "시간대_건수~17_매출_건수",
        "시간대_건수~21_매출_건수",
        "시간대_건수~24_매출_건수",
    ]

    time_data = {k: area.get(k) for k in time_keys if area.get(k) is not None}
    active_period = None
    if time_data:
        active_period = max(time_data, key=time_data.get).replace("시간대_건수~", "").replace("_매출_건수", "")
    else:
        active_period = "정보 없음"


    # 결과 종합
    industry = store.get("업종") or "알 수 없음"
    area_name = store.get("상권") or store.get("상권_지리") or "상권 정보 없음"

    season_metrics = {
        "계절": season,
        "평균기온": round(temp_avg, 1),
        "강수시간수": int(rain_hours),
        "날씨추세": weather_trend,
        "업종": industry,
        "상권명": area_name,
        "상권_주요활성시간대": active_period,
        "메시지": (
            f"{season} 평균기온 {temp_avg:.1f}℃, 날씨 '{weather_trend}' 예상. "
            f"상권 '{area_name}'은 {active_period}시간대에 가장 활발"
        ),
    }

    return {"success": True, "season_metrics": season_metrics}


if __name__ == "__main__":
    import sys, json

    if len(sys.argv) < 2:
        print("사용법: python -m my_agent.metrics.season_metrics <STORE_ID>")
        # python -m my_agent.metrics.season_metrics 761947ABD9
        sys.exit(1)

    store_id = sys.argv[1]
    result = build_season_metrics(store_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))