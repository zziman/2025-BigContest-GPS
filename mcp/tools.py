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


# 데이터 경로
FRANCHISE_CSV = os.environ.get("FRANCHISE_CSV", "./data/franchise_data.csv")
BIZ_AREA_CSV  = os.environ.get("BIZ_AREA_CSV",  "./data/biz_area.csv")
ADMIN_DONG_CSV = os.environ.get("ADMIN_DONG_CSV", "./data/admin_dong.csv")

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
def search_merchant(merchant_name: str, top_k: int = 20) -> Dict[str, Any]:
    """
    가맹점명으로 후보 검색 (부분일치)
    반환 컬럼은 원본 일부 노출 (가맹점_구분번호, 가맹점명, 주소/상권/업종 등)
    """
    df = _load_franchise_df()
    q = (merchant_name or "").strip()
    if not q:
        return {
            "found": False,
            "message": "검색어가 비어있습니다.",
            "count": 0,
            "merchants": []
        }

    # 부분 일치
    mask = df["가맹점명"].str.contains(q, case=False, na=False)
    result = df[mask].copy()

    if result.empty:
        return {
            "found": False,
            "message": f"'{merchant_name}'에 해당하는 가맹점이 없습니다.",
            "count": 0,
            "merchants": []
        }

    # 간단 정렬: 이름 길이, 사전순
    result["_len"] = result["가맹점명"].str.len()
    result = result.sort_values(by=["_len", "가맹점명"], ascending=[True, True]).drop(columns=["_len"])

    # 노출 컬럼 구성 (존재하는 컬럼만)
    base_cols = [
        "가맹점_구분번호", "가맹점명", "가맹점_지역", "업종",
        "상권", "상권_지리", "가맹점_주소"
    ]
    cols = [c for c in base_cols if c in result.columns]
    merchants = (
        result[cols]
        .drop_duplicates(subset=["가맹점_구분번호"] if "가맹점_구분번호" in result.columns else None)
        .head(max(1, int(top_k)))
    )
    merchants = _to_serializable_records(merchants)

    # user_info 키를 함께 달고 싶을 때를 대비하여 생성 가능 -> 참고하세요!
    # for m in merchants:
    #     m["user_info"] = {
    #         "store_name": m.get("가맹점명"),
    #         "store_num": m.get("가맹점_구분번호"),
    #         "location": m.get("가맹점_주소"),
    #         "marketing_area": m.get("상권") or m.get("상권_지리"),
    #         "industry": m.get("업종"),
    #     }

    return {
        "found": True,
        "message": f"'{merchant_name}' 후보 {len(merchants)}개",
        "count": len(merchants),
        "merchants": merchants
    }



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