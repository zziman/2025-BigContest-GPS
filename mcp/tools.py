# mcp/tools.py

# -*- coding: utf-8 -*-
"""
MCP 툴 함수 
- _file_exists(path): 파일 경로가 존재하는지 확인
- _load_franchise_df(): 가맹점 CSV 로드 및 캐싱
- _load_bizarea_df(): 상권 CSV 로드 및 캐싱
- _load_region_df(): 행정동 CSV 로드 및 캐싱
- _to_serializable_row(row): Series/Dict → JSON 직렬화 가능한 dict 변환
- _to_serializable_records(df): DataFrame → JSON 직렬화 가능한 list 변환

- search_merchant(merchant_name, top_k=20): 가맹점명 부분검색으로 후보 목록 조회
- load_store_data(store_id, latest_only=True): 가맹점 ID 기준 데이터 조회 (최신 1건 또는 전체 이력)
- load_bizarea_data(store_row, all_matches=False): 가맹점 데이터 기준 상권(biz area) 데이터 조회
- load_region_data(store_row, all_matches=False): 가맹점 데이터 기준 행정동(region) 데이터 조회
"""

from __future__ import annotations
import os
from pathlib import Path
from typing import Dict, Any, Optional, List, Union

import pandas as pd
import re 


# config에서 그대로 가져오기 (Streamlit secrets/env/기본값 우선순위 유지)
from my_agent.utils.config import (
    FRANCHISE_CSV as _FRANCHISE,
    BIZ_AREA_CSV  as _BIZAREA,
    ADMIN_DONG_CSV as _ADMIN,
)


# 경로만 절대경로화
FRANCHISE_CSV  = Path(_FRANCHISE).expanduser()
BIZ_AREA_CSV   = Path(_BIZAREA).expanduser()
ADMIN_DONG_CSV = Path(_ADMIN).expanduser()


# 전역 DataFrame 캐시
_FRANCHISE_DF: Optional[pd.DataFrame] = None
_BIZAREA_DF: Optional[pd.DataFrame] = None
_REGION_DF: Optional[pd.DataFrame] = None


# 내부 유틸
def _file_exists(path: str) -> bool:
    return Path(path).exists() and Path(path).is_file()


def _load_franchise_df() -> pd.DataFrame:
    """가맹점(franchise) CSV 로드 (싱글턴 캐시)"""
    global _FRANCHISE_DF
    if _FRANCHISE_DF is None:
        if not _file_exists(FRANCHISE_CSV):
            raise FileNotFoundError(f"franchise CSV not found: {FRANCHISE_CSV}")
        df = pd.read_csv(FRANCHISE_CSV)
        # 문자열 기본 정리 (필드가 존재할 때만)
        for col in ["가맹점_구분번호", "가맹점명", "기준년월", "업종", "상권_지리", "매핑용_행정동"]:
            if col in df.columns:
                df[col] = df[col].astype(str)
        _FRANCHISE_DF = df
    return _FRANCHISE_DF


def _load_bizarea_df() -> pd.DataFrame:
    """상권(biz_area) CSV 로드 (싱글턴 캐시)"""
    global _BIZAREA_DF
    if _BIZAREA_DF is None:
        if not _file_exists(BIZ_AREA_CSV):
            raise FileNotFoundError(f"biz area CSV not found: {BIZ_AREA_CSV}")
        df = pd.read_csv(BIZ_AREA_CSV)
        for col in ["기준년월", "상권_지리", "업종"]:
            if col in df.columns:
                df[col] = df[col].astype(str)
        _BIZAREA_DF = df
    return _BIZAREA_DF


def _load_region_df() -> pd.DataFrame:
    """행정동(admin_dong) CSV 로드 (싱글턴 캐시)"""
    global _REGION_DF
    if _REGION_DF is None:
        if not _file_exists(ADMIN_DONG_CSV):
            raise FileNotFoundError(f"admin dong CSV not found: {ADMIN_DONG_CSV}")
        df = pd.read_csv(ADMIN_DONG_CSV)
        for col in ["기준년월", "행정동_코드_명", "업종"]:
            if col in df.columns:
                df[col] = df[col].astype(str)
        _REGION_DF = df
    return _REGION_DF


def _to_serializable_row(row: Union[pd.Series, Dict[str, Any]]) -> Dict[str, Any]:
    """
    pandas Series/Dict 를 JSON 직렬화 가능한 dict 로 변환
    NaN → None, 나머지는 그대로 유지 (원본 컬럼명 보존)
    """
    if isinstance(row, dict):
        return {k: (None if pd.isna(v) else v) for k, v in row.items()}
    return {k: (None if pd.isna(v) else v) for k, v in row.to_dict().items()}


def _to_serializable_records(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """DataFrame → List[dict] 직렬화 (NaN → None)"""
    if df.empty:
        return []
    # where 로 NaN 마스킹 후 dict 변환
    df2 = df.where(pd.notna(df), None)
    return df2.to_dict(orient="records")


# 가맹점명 검색
def search_merchant(merchant_name: str) -> Dict[str, Any]:
    """
    가맹점명 또는 가맹점_구분번호로 검색
    
    Args:
        merchant_name: 가맹점명 또는 가맹점_구분번호
    
    Returns:
        {
            "found": bool,
            "message": str,
            "count": int,
            "merchants": List[dict],
            "search_type": "id" | "name" | None  # 검색 유형
        }
    """
    df = _load_franchise_df()
    q = (merchant_name or "").strip()
    
    if not q:
        return {
            "found": False,
            "message": "검색어가 비어있습니다.",
            "count": 0,
            "merchants": [],
            "search_type": None
        }
    
    # ─────────────────────────────────────────
    # 1. 가맹점_구분번호 패턴 감지 (우선순위 높음)
    # ─────────────────────────────────────────
    store_id_pattern = r'^[A-Z0-9]{10,11}$'
    
    if re.match(store_id_pattern, q.upper()):
        print(f"[MCP] 가맹점_구분번호로 인식: {q}")
        result = df[df["가맹점_구분번호"] == q.upper()].copy()
        
        if not result.empty:
            # 최신 데이터만 (중복 제거)
            result = result.sort_values("기준년월", ascending=False)
            result = result.drop_duplicates(subset=["가맹점_구분번호"], keep="first")
            
            cols = ["가맹점_구분번호", "가맹점명", "가맹점_주소", "업종"]
            merchants = result[cols].to_dict(orient="records")
            
            return {
                "found": True,
                "message": f"가맹점_구분번호 '{q}' 조회 성공",
                "count": 1,
                "merchants": merchants,
                "search_type": "id"
            }
        else:
            return {
                "found": False,
                "message": f"가맹점_구분번호 '{q}'를 찾을 수 없습니다.",
                "count": 0,
                "merchants": [],
                "search_type": "id"
            }
    
    # ─────────────────────────────────────────
    # 2. 가맹점명으로 검색 (기존 로직)
    # ─────────────────────────────────────────
    print(f"[MCP] 가맹점명으로 검색: '{q}'")
    q_clean = q.replace("*", "")
    
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
            "merchants": [],
            "search_type": "name"
        }
    
    # 정렬 (기존 로직)
    result["_name_len"] = result["가맹점명"].str.len()
    result["_star_count"] = result["가맹점명"].str.count("\*")
    result = result.sort_values(
        by=["_star_count", "_name_len", "가맹점명"],
        ascending=[True, True, True]
    ).drop(columns=["_name_len", "_star_count"])
    
    # 중복 제거 (같은 가맹점의 여러 시점 데이터)
    cols = ["가맹점_구분번호", "가맹점명", "가맹점_주소", "업종"]
    merchants = result[cols].drop_duplicates(subset=["가맹점_구분번호"]).head(20).to_dict(orient="records")
    
    return {
        "found": True,
        "message": f"'{merchant_name}' 후보 {len(merchants)}개",
        "count": len(merchants),
        "merchants": merchants,
        "search_type": "name"
    }

    # user_info 키를 함께 달고 싶을 때를 대비하여 생성 가능 -> 참고하세요!
    # for m in merchants:
    #     m["user_info"] = {
    #         "store_name": m.get("가맹점명"),
    #         "store_num": m.get("가맹점_구분번호"),
    #         "location": m.get("가맹점_주소"),
    #         "marketing_area": m.get("상권") or m.get("상권_지리"),
    #         "industry": m.get("업종"),
    #     }


def load_store_data(store_id: str, latest_only: bool = True) -> Dict[str, Any]:
    """
    store_id 기준으로 가맹점 데이터 조회
    Args:
        store_id: 가맹점_구분번호
        latest_only: True → 최신 1건(dict), False → 전체 기간(list[dict]], 기준년월 오름차순)
    """
    df = _load_franchise_df()
    sid = str(store_id)

    if "가맹점_구분번호" not in df.columns:
        return {"success": False, "data": None, "error": "컬럼 '가맹점_구분번호' 없음"}

    store_df = df[df["가맹점_구분번호"] == sid].copy()
    if store_df.empty:
        return {"success": False, "data": None, "error": f"store_id {sid} not found"}

    if "기준년월" in store_df.columns:
        store_df = store_df.sort_values("기준년월")

    if latest_only:
        latest_row = store_df.iloc[-1]
        return {
            "success": True,
            "data": _to_serializable_row(latest_row),
            "error": None
        }
    else:
        return {
            "success": True,
            "data": _to_serializable_records(store_df),
            "error": None
        }


def load_bizarea_data(store_row: Dict[str, Any], all_matches: bool = False) -> Dict[str, Any]:
    """
    상권(biz_area) 데이터 조회
    Args:
        store_row: load_store_data(..., latest_only=True/False) 결과 중 1행(dict)
        all_matches: True → 매칭되는 모든 행 반환(list), False → 첫 1행만 반환(dict)
    매핑 키:
        기준년월 = store_row['기준년월']
        상권_지리 = store_row['상권_지리']
        업종     = store_row['업종']
    * 사용 패턴: store = load_store_data(...)[\"data\"] → load_bizarea_data(store)
    """
    df_biz = _load_bizarea_df()

    # 필수 키 확인
    required = ["기준년월", "상권_지리", "업종"]
    missing = [k for k in required if k not in store_row or store_row.get(k) in (None, "", float("nan"))]
    if missing:
        return {
            "success": False,
            "data": None,
            "error": f"store_row lacks keys: {', '.join(missing)}"
        }

    yyyymm = str(store_row["기준년월"])
    area_geo = str(store_row["상권_지리"])
    industry = str(store_row["업종"])

    # 필터
    mask = (
        (df_biz["기준년월"] == yyyymm) &
        (df_biz["상권_지리"] == area_geo) &
        (df_biz["업종"] == industry)
    )
    hit = df_biz[mask].copy()

    if hit.empty:
        return {"success": False, "data": None, "error": "bizarea not found"}

    if all_matches:
        return {"success": True, "data": _to_serializable_records(hit), "error": None}
    else:
        return {"success": True, "data": _to_serializable_row(hit.iloc[0]), "error": None}


def load_region_data(store_row: Dict[str, Any], all_matches: bool = False) -> Dict[str, Any]:
    """
    행정동(admin_dong) 데이터 조회 (원본 컬럼 그대로)
    Args:
        store_row: load_store_data(..., latest_only=True/False) 결과 중 1행(dict)
        all_matches: True → 매칭되는 모든 행 반환(list), False → 첫 1행만 반환(dict)
    매핑 키:
        기준년월       = store_row['기준년월']
        행정동_코드_명 = store_row['매핑용_행정동']
        업종           = store_row['업종']
    * 사용 패턴: store = load_store_data(...)[\"data\"] → load_region_data(store)
    """
    df_region = _load_region_df()

    required = ["기준년월", "매핑용_행정동", "업종"]
    missing = [k for k in required if k not in store_row or store_row.get(k) in (None, "", float("nan"))]
    if missing:
        return {
            "success": False,
            "data": None,
            "error": f"store_row lacks keys: {', '.join(missing)}"
        }

    yyyymm = str(store_row["기준년월"])
    admin_code = str(store_row["매핑용_행정동"])
    industry = str(store_row["업종"])

    mask = (
        (df_region["기준년월"] == yyyymm) &
        (df_region["행정동_코드_명"] == admin_code) &
        (df_region["업종"] == industry)
    )
    hit = df_region[mask].copy()

    if hit.empty:
        return {"success": False, "data": None, "error": "region not found"}

    if all_matches:
        return {"success": True, "data": _to_serializable_records(hit), "error": None}
    else:
        return {"success": True, "data": _to_serializable_row(hit.iloc[0]), "error": None}
