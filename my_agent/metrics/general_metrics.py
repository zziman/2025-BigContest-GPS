# my_agent/metrics/general_metrics.py
# -*- coding: utf-8 -*-
"""
General Metrics Builder
- 목적: General 노드 전용 보조 지표 (main_metrics 보완용)
- 특징: main_metrics와 중복 없이 맥락/상권 정보만 제공
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


def _safe_float(x, default=0.0) -> float:
    """안전한 float 변환"""
    try:
        if x is None or x == "":
            return default
        return float(x)
    except (ValueError, TypeError):
        return default


def _safe_int(x, default=0) -> int:
    """안전한 int 변환"""
    try:
        if x is None or x == "":
            return default
        return int(x)
    except (ValueError, TypeError):
        return default


def build_general_metrics(store_num: str) -> Dict[str, Any]:
    """
    General 노드용 보조 지표 (main_metrics 보완)
    
    Returns:
        {
            "general_metrics": {
                "가게_기본정보": {...},    # main에 없는 기본 정보
                "상권_환경": {...},        # 입지/경쟁 환경
                "고객_세부분포": {...}      # 연령대별 세부 정보
            },
            "yyyymm": "202501"
        }
    """
    # 데이터 로드
    state = {"store_id": store_num}
    state = load_store_and_area_data(state, include_region=False, latest_only=True)
    
    store = state.get("store_data")
    biz = state.get("bizarea_data")
    
    if not store:
        raise ValueError(f"store_data not found for store_num={store_num}")
    
    yyyymm = _safe(store.get("기준년월"), "정보없음")
    
    # ═════════════════════════════════════════
    # 1. 가게_기본정보 (main에 없는 것만)
    # ═════════════════════════════════════════
    brand_code = _safe(store.get("브랜드구분코드"), "정보없음")
    
    if brand_code == "F":
        brand_type = "프랜차이즈"
    elif brand_code == "I":
        brand_type = "개인점"
    else:
        brand_type = str(brand_code) if brand_code != "정보없음" else "정보없음"
    
    가게_기본정보 = {
        "상권유형": _safe(store.get("상권유형_지리"), "정보없음"),
        "브랜드형태": brand_type,
        "운영기간_개월": _safe_int(store.get("영업_경과_개월"), 0),
        "개인사업자여부": _safe(store.get("개인사업자여부"), "정보없음"),
        "폐업여부": _safe(store.get("폐업여부"), "정보없음"),
    }
    
    # ═════════════════════════════════════════
    # 2. 상권_환경 (입지/경쟁 환경)
    # ═════════════════════════════════════════
    상권_환경 = {}
    if biz and isinstance(biz, dict):
        상권_환경 = {
            # 인구 (활성도)
            "유동인구수": _safe_int(biz.get("총_유동인구_수"), 0),
            "상주인구수": _safe_int(biz.get("총_상주인구_수"), 0),
            "직장인구수": _safe_int(biz.get("총_직장_인구_수"), 0),
            
            # 접근성
            "접근성점수": _safe_float(biz.get("접근성_점수"), 0.0),
            "지하철역수": _safe_int(biz.get("지하철_역_수"), 0),
            "버스정거장수": _safe_int(biz.get("버스_정거장_수"), 0),
            
            # 경쟁 강도
            "전체점포수": _safe_int(biz.get("점포_수"), 0),
            "유사업종점포수": _safe_int(biz.get("유사_업종_점포_수"), 0),
            "프랜차이즈점포수": _safe_int(biz.get("프랜차이즈_점포_수"), 0),
            
            # 개업/폐업 동향
            "개업율": _safe_float(biz.get("개업_율"), 0.0),
            "폐업률": _safe_float(biz.get("폐업_률"), 0.0),
        }
    
    # ═════════════════════════════════════════
    # 3. 고객_세부분포 (main의 핵심고객 보완용)
    # ═════════════════════════════════════════
    고객_세부분포 = {
        "남성_20대이하": _safe_float(store.get("남성_20대이하_고객_비중"), 0.0),
        "남성_30대": _safe_float(store.get("남성_30대_고객_비중"), 0.0),
        "남성_40대": _safe_float(store.get("남성_40대_고객_비중"), 0.0),
        "남성_50대": _safe_float(store.get("남성_50대_고객_비중"), 0.0),
        "남성_60대이상": _safe_float(store.get("남성_60대이상_고객_비중"), 0.0),
        "여성_20대이하": _safe_float(store.get("여성_20대이하_고객_비중"), 0.0),
        "여성_30대": _safe_float(store.get("여성_30대_고객_비중"), 0.0),
        "여성_40대": _safe_float(store.get("여성_40대_고객_비중"), 0.0),
        "여성_50대": _safe_float(store.get("여성_50대_고객_비중"), 0.0),
        "여성_60대이상": _safe_float(store.get("여성_60대이상_고객_비중"), 0.0),
    }
    
    # ─────────────────────────
    # 최종 반환
    # ─────────────────────────
    return {
        "general_metrics": {
            "가게_기본정보": 가게_기본정보,
            "상권_환경": 상권_환경,
            "고객_세부분포": 고객_세부분포,
        },
        "yyyymm": yyyymm
    }


# ─────────────────────────
# CLI Test
# ─────────────────────────
if __name__ == "__main__":
    import sys, json
    
    if len(sys.argv) < 2:
        print("사용법: python -m my_agent.metrics.general_metrics <STORE_ID>")
        print("예시: python -m my_agent.metrics.general_metrics 761947ABD9")
        sys.exit(1)
    
    store_id = sys.argv[1]
    
    try:
        result = build_general_metrics(store_id)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"❌ 에러 발생: {e}")
        import traceback
        traceback.print_exc()
