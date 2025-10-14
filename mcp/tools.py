# -*- coding: utf-8 -*-
"""
MCP 툴 함수 구현: DB 조회 로직 (비율 보정 포함)
"""
import os
import pandas as pd
from pathlib import Path
from typing import Dict, Any, Optional, List

# 데이터 경로
FRANCHISE_CSV = os.environ.get("FRANCHISE_CSV", "./data/franchise_data.csv")
BIZ_AREA_CSV = os.environ.get("BIZ_AREA_CSV", "./data/biz_area.csv")
ADMIN_DONG_CSV = os.environ.get("ADMIN_DONG_CSV", "./data/admin_dong.csv")

# 전역 DataFrame 캐시
_FRANCHISE_DF: Optional[pd.DataFrame] = None


def safe_percentage_to_ratio(val, default=0.0):
    """
    퍼센트를 비율로 안전하게 변환
    
    변환 규칙:
    - None/NaN → 0.0
    - 0~1 → 그대로 (이미 비율)
    - 1~100 → /100 (퍼센트 → 비율)
    - 100 초과 → 1.0 (캡핑)
    - 음수 → 0.0
    """
    try:
        if pd.isna(val) or val is None:
            return default
        
        result = float(val)
        
        if result < 0:
            return 0.0
        
        if 0 <= result <= 1:
            return result
        
        if 1 < result <= 100:
            return result / 100.0
        
        if result > 100:
            return 1.0
        
        return default
    
    except (ValueError, TypeError):
        return default


def _load_franchise_df() -> pd.DataFrame:
    """가맹점 데이터 로드 (싱글턴)"""
    global _FRANCHISE_DF
    if _FRANCHISE_DF is None:
        _FRANCHISE_DF = pd.read_csv(FRANCHISE_CSV)
        for col in ["가맹점_구분번호", "가맹점명", "가맹점_지역", "업종", "기준년월"]:
            if col in _FRANCHISE_DF.columns:
                _FRANCHISE_DF[col] = _FRANCHISE_DF[col].fillna("").astype(str)
    return _FRANCHISE_DF


def search_merchant(merchant_name: str) -> Dict[str, Any]:
    """가맹점명으로 후보 검색"""
    df = _load_franchise_df()
    q = (merchant_name or "").strip()
    q_clean = q.replace("*", "")
    
    if not q_clean:
        return {
            "found": False,
            "message": "검색어가 비어있습니다.",
            "count": 0,
            "merchants": []
        }
    
    # 정확 일치
    exact_match = df[df["가맹점명"] == q]
    
    # 부분 일치
    if exact_match.empty:
        mask = df["가맹점명"].str.replace("*", "", regex=False).str.contains(q_clean, case=False, na=False)
        result = df[mask].copy()
    else:
        result = exact_match.copy()
    
    # 완화된 검색: 첫 2글자
    if result.empty and len(q_clean) >= 2:
        prefix = q_clean[:2]
        mask = df["가맹점명"].str.startswith(prefix, na=False)
        result = df[mask].copy()
    
    if result.empty:
        return {
            "found": False,
            "message": f"'{merchant_name}'에 해당하는 가맹점이 없습니다.",
            "count": 0,
            "merchants": []
        }
    
    # 정렬
    result["_name_len"] = result["가맹점명"].str.len()
    result["_star_count"] = result["가맹점명"].str.count("\*")
    result = result.sort_values(
        by=["_star_count", "_name_len", "가맹점명"],
        ascending=[True, True, True]
    ).drop(columns=["_name_len", "_star_count"])
    
    cols = ["가맹점_구분번호", "가맹점명", "가맹점_지역", "업종"]
    merchants = result[cols].drop_duplicates(subset=["가맹점_구분번호"]).head(20).to_dict(orient="records")
    
    return {
        "found": True,
        "message": f"'{merchant_name}' 후보 {len(merchants)}개",
        "count": len(merchants),
        "merchants": merchants
    }


def load_store_data(store_id: str) -> Dict[str, Any]:
    """가맹점 ID로 최신 월 데이터 조회 (비율 보정)"""
    df = _load_franchise_df()
    store_id = str(store_id)
    
    store_df = df[df["가맹점_구분번호"] == store_id]
    if store_df.empty:
        return {
            "success": False,
            "data": None,
            "error": f"store_id {store_id} not found"
        }
    
    latest_yyyymm = store_df["기준년월"].max()
    latest_row = store_df[store_df["기준년월"] == latest_yyyymm].iloc[0]
    
    card = {
        "mct_id": store_id,
        "yyyymm": str(latest_yyyymm),
        "mct_name": str(latest_row.get("가맹점명", "")),
        "district": str(latest_row.get("가맹점_지역", "")),
        "industry": str(latest_row.get("업종", "")),
        "rank_in_industry_pct": safe_percentage_to_ratio(latest_row.get("동일_업종_내_매출_순위_비율")),
        "rank_in_area_pct": safe_percentage_to_ratio(latest_row.get("동일_상권_내_매출_순위_비율")),
        "delivery_share": safe_percentage_to_ratio(latest_row.get("배달매출금액_비율")),
        "repeat_rate": safe_percentage_to_ratio(latest_row.get("재방문_고객_비중")),
        "new_rate": safe_percentage_to_ratio(latest_row.get("신규_고객_비중")),
        "residential_share": safe_percentage_to_ratio(latest_row.get("거주_이용_고객_비중")),
        "worker_share": safe_percentage_to_ratio(latest_row.get("직장_이용_고객_비중")),
        "floating_share": safe_percentage_to_ratio(latest_row.get("유동인구_이용_고객_비중")),
        "male_u20": safe_percentage_to_ratio(latest_row.get("남성_20대이하_고객_비중")),
        "male_30": safe_percentage_to_ratio(latest_row.get("남성_30대_고객_비중")),
        "male_40": safe_percentage_to_ratio(latest_row.get("남성_40대_고객_비중")),
        "male_50": safe_percentage_to_ratio(latest_row.get("남성_50대_고객_비중")),
        "male_60": safe_percentage_to_ratio(latest_row.get("남성_60대이상_고객_비중")),
        "female_u20": safe_percentage_to_ratio(latest_row.get("여성_20대이하_고객_비중")),
        "female_30": safe_percentage_to_ratio(latest_row.get("여성_30대_고객_비중")),
        "female_40": safe_percentage_to_ratio(latest_row.get("여성_40대_고객_비중")),
        "female_50": safe_percentage_to_ratio(latest_row.get("여성_50대_고객_비중")),
        "female_60": safe_percentage_to_ratio(latest_row.get("여성_60대이상_고객_비중")),
        "address": str(latest_row.get("가맹점_주소", "")),
        "sangwon": str(latest_row.get("상권", "")),
        "admin_dong": str(latest_row.get("행정동", "")),
        "latitude": float(latest_row.get("위도", 0) or 0),
        "longitude": float(latest_row.get("경도", 0) or 0),
    }
    
    return {
        "success": True,
        "data": card,
        "error": None
    }


def resolve_region(district: str) -> Dict[str, Any]:
    """가맹점_지역 → 행정동 코드 매핑"""
    df = _load_franchise_df()
    matched = df[df["가맹점_지역"] == district]["행정동"].dropna().unique()
    
    if len(matched) == 0:
        return {
            "success": False,
            "admin_dong_code": None,
            "error": f"district {district} not found"
        }
    
    return {
        "success": True,
        "admin_dong_code": str(matched[0]),
        "error": None
    }


def load_area_data(admin_dong_code: str) -> Dict[str, Any]:
    """상권 데이터 조회 (더미)"""
    return {
        "success": True,
        "data": {
            "admin_dong_code": admin_dong_code,
            "total_sales": 0,
            "store_count": 0,
            "floating_population": 0
        },
        "error": None
    }


def load_region_data(admin_dong_code: str) -> Dict[str, Any]:
    """행정동 인구 데이터 조회 (더미)"""
    return {
        "success": True,
        "data": {
            "admin_dong_code": admin_dong_code,
            "population": 0,
            "households": 0
        },
        "error": None
    }