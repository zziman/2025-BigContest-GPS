# mcp/tools_weather.py
# -*- coding: utf-8 -*-
"""
기상청 단기예보 API MCP 툴 (APIHub 버전)
- 입력: 위도(lat), 경도(lon)
- 출력: 향후 n일간의 기온/강수 데이터 (사람이 읽기 좋은 형식)
"""
import requests
import pandas as pd
from datetime import datetime, timedelta
from my_agent.utils.config import WEATHER_API_KEY  # APIHub 발급키 사용

URL = "https://apihub.kma.go.kr/api/typ02/openApi/VilageFcstInfoService_2.0/getVilageFcst"


# ---------------------------------------------
# 내부 유틸
# ---------------------------------------------
def _convert_latlon_to_grid(lat: float, lon: float):
    """위도·경도 → 기상청 격자 좌표 변환"""
    import math
    RE = 6371.00877
    GRID = 5.0
    SLAT1 = 30.0
    SLAT2 = 60.0
    OLON = 126.0
    OLAT = 38.0
    XO = 43
    YO = 136

    DEGRAD = math.pi / 180.0
    re = RE / GRID
    slat1 = SLAT1 * DEGRAD
    slat2 = SLAT2 * DEGRAD
    olon = OLON * DEGRAD
    olat = OLAT * DEGRAD

    sn = math.log(math.cos(slat1) / math.cos(slat2)) / math.log(
        math.tan(math.pi / 4.0 + slat2 / 2.0) / math.tan(math.pi / 4.0 + slat1 / 2.0)
    )
    sf = math.tan(math.pi / 4.0 + slat1 / 2.0) ** sn * math.cos(slat1) / sn
    ro = re * sf / (math.tan(math.pi / 4.0 + olat / 2.0) ** sn)

    ra = re * sf / (math.tan(math.pi / 4.0 + lat * DEGRAD / 2.0) ** sn)
    theta = lon * DEGRAD - olon
    if theta > math.pi:
        theta -= 2.0 * math.pi
    if theta < -math.pi:
        theta += 2.0 * math.pi
    theta *= sn

    x = int(ra * math.sin(theta) + XO + 0.5)
    y = int(ro - ra * math.cos(theta) + YO + 0.5)
    return x, y


# ---------------------------------------------
# 메인 함수
# ---------------------------------------------
def get_weather_forecast(lat: float, lon: float, days: int = 3):
    """기상청 APIHub 단기예보 조회"""
    try:
        nx, ny = _convert_latlon_to_grid(lat, lon)
        base_date = datetime.today().strftime("%Y%m%d")
        base_time = "0500"

        params = {
            "authKey": WEATHER_API_KEY,
            "numOfRows": "300",
            "pageNo": "1",
            "dataType": "JSON",
            "base_date": base_date,
            "base_time": base_time,
            "nx": nx,
            "ny": ny,
        }

        res = requests.get(URL, params=params, timeout=10)
        res.raise_for_status()

        items = res.json()["response"]["body"]["items"]["item"]
        df = pd.DataFrame(items)

        # 관심 category만 필터
        df = df[df["category"].isin(["TMP", "TMN", "TMX", "PTY"])]
        df["fcstDateTime"] = pd.to_datetime(df["fcstDate"] + df["fcstTime"], format="%Y%m%d%H%M")

        # 피벗으로 구조 변환
        df_pivot = df.pivot_table(index="fcstDateTime", columns="category", values="fcstValue", aggfunc="first")
        df_pivot.reset_index(inplace=True)

        # 사람이 읽기 좋은 이름으로 컬럼 변경
        df_pivot.rename(
            columns={
                "TMP": "기온(℃)",
                "TMN": "최저기온(℃)",
                "TMX": "최고기온(℃)",
                "PTY": "강수형태코드",
            },
            inplace=True,
        )

        # 강수형태 코드 → 텍스트 변환
        pty_map = {
            "0": "없음",
            "1": "비",
            "2": "비/눈",
            "3": "눈",
            "5": "빗방울",
            "6": "빗방울/눈날림",
            "7": "눈날림",
        }
        df_pivot["강수형태"] = df_pivot["강수형태코드"].map(pty_map).fillna("정보없음")

        df_pivot = df_pivot[df_pivot["fcstDateTime"] < (datetime.now() + timedelta(days=days))]
        df_pivot.sort_values("fcstDateTime", inplace=True)

        return {
            "success": True,
            "count": len(df_pivot),
            "data": df_pivot.to_dict(orient="records"),
            "message": f"{len(df_pivot)} forecast entries retrieved",
        }

    except Exception as e:
        return {"success": False, "count": 0, "data": [], "message": str(e)}


# ---------------------------------------------
# 실행 테스트 (__main__)
# ---------------------------------------------
if __name__ == "__main__":
    lat, lon = 37.57, 126.98  # 서울 종로구 기준
    print("🌤 MCP Weather Tool Test Start")
    print(f"▶ 위도: {lat}, 경도: {lon}\n")

    result = get_weather_forecast(lat, lon, days=3)
    print("🧾 결과 요약")
    print(f" - 성공 여부: {result['success']}")
    print(f" - 데이터 개수: {result['count']}")
    print(f" - 메시지: {result['message']}\n")

    if result["success"]:
        df = pd.DataFrame(result["data"])
        print("📈 예보 데이터 (상위 10행)")
        print(df.head(10).to_string(index=False))
    else:
        print(f"❌ 오류: {result['message']}")
