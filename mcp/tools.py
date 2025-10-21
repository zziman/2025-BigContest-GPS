# mcp/tools.py (최종 정리 버전)
# -*- coding: utf-8 -*-
"""
MCP 툴 함수 (DuckDB 기반)

공통 매핑 컬럼: 기준년월, 업종, 상권_지리

함수:
- search_merchant(merchant_name): 가맹점명/ID 검색
- load_store_data(store_id, latest_only): 가맹점 데이터 조회
- load_bizarea_data(store_row, all_matches): 상권 데이터 조회
"""

from __future__ import annotations
import re
from pathlib import Path
from typing import Dict, Any, Optional, List, Union

import pandas as pd
import duckdb

from my_agent.utils.config import (
    FRANCHISE_CSV, BIZ_AREA_CSV,
    DUCKDB_PATH, USE_DUCKDB
)

# ═══════════════════════════════════════════
# DuckDB 연결 (싱글턴)
# ═══════════════════════════════════════════
_DB_CONNECTION: Optional[duckdb.DuckDBPyConnection] = None


def _get_db_connection():
    """DuckDB 연결 획득 (재사용)"""
    global _DB_CONNECTION
    if _DB_CONNECTION is None:
        db_path = Path(DUCKDB_PATH).expanduser()
        if not db_path.exists():
            raise FileNotFoundError(
                f"❌ DuckDB 파일이 없습니다: {db_path}\n"
                f"💡 먼저 실행하세요: python scripts/build_duckdb.py"
            )
        _DB_CONNECTION = duckdb.connect(str(db_path), read_only=True)
    return _DB_CONNECTION


# ═══════════════════════════════════════════
# CSV 기반 로딩 (레거시 - USE_DUCKDB=False일 때만)
# ═══════════════════════════════════════════
_FRANCHISE_DF: Optional[pd.DataFrame] = None
_BIZAREA_DF: Optional[pd.DataFrame] = None


def _file_exists(path: str) -> bool:
    return Path(path).exists() and Path(path).is_file()


def _load_franchise_df() -> pd.DataFrame:
    """가맹점 CSV 로드 (싱글턴 캐시)"""
    global _FRANCHISE_DF
    if _FRANCHISE_DF is None:
        if not _file_exists(FRANCHISE_CSV):
            raise FileNotFoundError(f"franchise CSV not found: {FRANCHISE_CSV}")
        df = pd.read_csv(FRANCHISE_CSV)
        for col in ["가맹점_구분번호", "가맹점명", "기준년월", "업종", "상권_지리"]:
            if col in df.columns:
                df[col] = df[col].astype(str)
        _FRANCHISE_DF = df
    return _FRANCHISE_DF


def _load_bizarea_df() -> pd.DataFrame:
    """상권 CSV 로드 (싱글턴 캐시)"""
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


def _to_serializable_row(row: Union[pd.Series, Dict[str, Any]]) -> Dict[str, Any]:
    """pandas Series/Dict → JSON 직렬화"""
    if isinstance(row, dict):
        return {k: (None if pd.isna(v) else v) for k, v in row.items()}
    return {k: (None if pd.isna(v) else v) for k, v in row.to_dict().items()}


def _to_serializable_records(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """DataFrame → List[dict] 직렬화"""
    if df.empty:
        return []
    df2 = df.where(pd.notna(df), None)
    return df2.to_dict(orient="records")


# ═══════════════════════════════════════════
# 가맹점 검색
# ═══════════════════════════════════════════
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
            "search_type": "id" | "name" | None
        }
    """
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
    # DuckDB 사용
    # ─────────────────────────────────────────
    if USE_DUCKDB:
        con = _get_db_connection()
        
        # 1) 가맹점_구분번호 패턴 감지 (10-11자리 영숫자)
        store_id_pattern = r'^[A-Z0-9]{10,11}$'
        
        if re.match(store_id_pattern, q.upper()):
            result = con.execute("""
                SELECT DISTINCT 
                    가맹점_구분번호, 가맹점명, 가맹점_주소, 업종, 상권_지리
                FROM franchise
                WHERE 가맹점_구분번호 = ?
                ORDER BY 기준년월 DESC
                LIMIT 1
            """, [q.upper()]).fetchdf()
            
            if not result.empty:
                merchants = result.to_dict(orient="records")
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
        
        # 2) 가맹점명 부분 검색 (최신 데이터만, 중복 제거)
        result = con.execute("""
            SELECT DISTINCT 
                가맹점_구분번호, 가맹점명, 가맹점_주소, 업종, 상권_지리
            FROM (
                SELECT *, 
                       ROW_NUMBER() OVER (PARTITION BY 가맹점_구분번호 ORDER BY 기준년월 DESC) as rn
                FROM franchise
                WHERE 가맹점명 LIKE ?
            ) sub
            WHERE rn = 1
            ORDER BY 가맹점명
            LIMIT 50
        """, [f"%{q}%"]).fetchdf()
        
        if result.empty:
            return {
                "found": False,
                "message": f"'{q}'와 일치하는 가맹점이 없습니다.",
                "count": 0,
                "merchants": [],
                "search_type": "name"
            }
        
        merchants = result.to_dict(orient="records")
        return {
            "found": True,
            "message": f"'{q}' 검색 결과 {len(merchants)}개",
            "count": len(merchants),
            "merchants": merchants,
            "search_type": "name"
        }
    
    # ─────────────────────────────────────────
    # CSV 사용 (레거시)
    # ─────────────────────────────────────────
    else:
        df = _load_franchise_df()
        store_id_pattern = r'^[A-Z0-9]{10,11}$'
        
        # ID 검색
        if re.match(store_id_pattern, q.upper()):
            result = df[df["가맹점_구분번호"] == q.upper()].copy()
            
            if not result.empty:
                result = result.sort_values("기준년월", ascending=False)
                result = result.drop_duplicates(subset=["가맹점_구분번호"], keep="first")
                merchants = result[["가맹점_구분번호", "가맹점명", "가맹점_주소", "업종", "상권_지리"]].to_dict(orient="records")
                
                return {
                    "found": True,
                    "message": f"가맹점_구분번호 '{q}' 조회 성공",
                    "count": 1,
                    "merchants": merchants,
                    "search_type": "id"
                }
        
        # 가맹점명 검색
        mask = df["가맹점명"].str.contains(q, case=False, na=False)
        result = df[mask].copy()
        
        if result.empty:
            return {
                "found": False,
                "message": f"'{q}'와 일치하는 가맹점이 없습니다.",
                "count": 0,
                "merchants": [],
                "search_type": "name"
            }
        
        result = result.sort_values("기준년월", ascending=False)
        result = result.drop_duplicates(subset=["가맹점_구분번호"], keep="first")
        merchants = result.head(50)[["가맹점_구분번호", "가맹점명", "가맹점_주소", "업종", "상권_지리"]].to_dict(orient="records")
        
        return {
            "found": True,
            "message": f"'{q}' 검색 결과 {len(merchants)}개",
            "count": len(merchants),
            "merchants": merchants,
            "search_type": "name"
        }


# ═══════════════════════════════════════════
# 가맹점 데이터 조회
# ═══════════════════════════════════════════
def load_store_data(store_id: str, latest_only: bool = True) -> Dict[str, Any]:
    """
    store_id 기준으로 가맹점 데이터 조회
    
    Args:
        store_id: 가맹점_구분번호
        latest_only: True → 최신 1건(dict), False → 전체 이력(list[dict])
    
    Returns:
        {"success": bool, "data": dict or list, "error": str or None}
    """
    sid = str(store_id)
    
    # ─────────────────────────────────────────
    # DuckDB 사용
    # ─────────────────────────────────────────
    if USE_DUCKDB:
        con = _get_db_connection()
        
        if latest_only:
            query = """
            SELECT * FROM franchise
            WHERE 가맹점_구분번호 = ?
            ORDER BY 기준년월 DESC
            LIMIT 1
            """
            result = con.execute(query, [sid]).fetchdf()
            
            if result.empty:
                return {"success": False, "data": None, "error": f"가맹점 {sid} 없음"}
            
            return {
                "success": True,
                "data": result.iloc[0].to_dict(),
                "error": None
            }
        else:
            query = """
            SELECT * FROM franchise
            WHERE 가맹점_구분번호 = ?
            ORDER BY 기준년월 ASC
            """
            result = con.execute(query, [sid]).fetchdf()
            
            if result.empty:
                return {"success": False, "data": None, "error": f"가맹점 {sid} 없음"}
            
            return {
                "success": True,
                "data": result.to_dict("records"),
                "error": None
            }
    
    # ─────────────────────────────────────────
    # CSV 사용 (레거시)
    # ─────────────────────────────────────────
    else:
        df = _load_franchise_df()
        
        if "가맹점_구분번호" not in df.columns:
            return {"success": False, "data": None, "error": "컬럼 '가맹점_구분번호' 없음"}
        
        store_df = df[df["가맹점_구분번호"] == sid].copy()
        if store_df.empty:
            return {"success": False, "data": None, "error": f"store_id {sid} not found"}
        
        if "기준년월" in store_df.columns:
            store_df = store_df.sort_values("기준년월")
        
        if latest_only:
            return {
                "success": True,
                "data": _to_serializable_row(store_df.iloc[-1]),
                "error": None
            }
        else:
            return {
                "success": True,
                "data": _to_serializable_records(store_df),
                "error": None
            }


# ═══════════════════════════════════════════
# 상권 데이터 조회
# ═══════════════════════════════════════════
def load_bizarea_data(store_row: Dict[str, Any], all_matches: bool = False) -> Dict[str, Any]:
    """상권 데이터 조회
    - DuckDB: 조건 일치 행 전부(or 1건) 반환. (상권_코드 컬럼 의존 제거)
    - CSV  : 정확 매칭 실패 확률 0 → 항상 단건 반환 (all_matches 무시)
    """
    required = ["기준년월", "업종", "상권_지리"]
    missing = [k for k in required if k not in store_row or not store_row.get(k)]
    if missing:
        return {"success": False, "data": None, "error": f"필수 키 누락: {', '.join(missing)}"}

    yyyymm = str(store_row["기준년월"])
    area_geo = str(store_row["상권_지리"])
    industry = str(store_row["업종"])

    if USE_DUCKDB:
        con = _get_db_connection()
        if all_matches:
            # 전체 매칭 행 반환 (정렬/상권_코드 의존 제거)
            query = """
            SELECT *
            FROM biz_area
            WHERE 기준년월 = ? AND 상권_지리 = ? AND 업종 = ?
            """
            params = [yyyymm, area_geo, industry]
            df = con.execute(query, params).fetchdf()
            if df.empty:
                return {"success": False, "data": None, "error": "상권 데이터 없음"}
            return {"success": True, "data": df.to_dict("records"), "error": None}
        else:
            # 단건만 필요 → LIMIT 1 (중복 제거/정렬 불필요)
            query = """
            SELECT *
            FROM biz_area
            WHERE 기준년월 = ? AND 상권_지리 = ? AND 업종 = ?
            LIMIT 1
            """
            params = [yyyymm, area_geo, industry]
            df = con.execute(query, params).fetchdf()
            if df.empty:
                return {"success": False, "data": None, "error": "상권 데이터 없음"}
            return {"success": True, "data": df.iloc[0].to_dict(), "error": None}

    # ─────────────────────────────────────────
    # CSV 분기: 정확 매칭 실패 확률 0 → 항상 단건 반환
    # all_matches 인자는 무시(하위호환 위해 유지)
    # ─────────────────────────────────────────
    df_biz = _load_bizarea_df()
    hit = df_biz[
        (df_biz["기준년월"] == yyyymm) &
        (df_biz["상권_지리"] == area_geo) &
        (df_biz["업종"] == industry)
    ].copy()

    if hit.empty:
        return {"success": False, "data": None, "error": "bizarea not found"}

    # 정렬 불필요, 상권_코드도 없음 → 첫 행만 직 반환
    return {"success": True, "data": _to_serializable_row(hit.iloc[0]), "error": None}
