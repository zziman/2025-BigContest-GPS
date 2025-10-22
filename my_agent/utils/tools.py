# my_agent/utils/tools.py

# -*- coding: utf-8 -*-
"""
핵심 유틸리티
- helpers (정규화/검증/간단 변환)
- store_resolver (가맹점 후보 확정 + user_info 구성)
- data_loader (store/bizarea 데이터 조회)
"""

from typing import Dict, Any, Tuple, List, Optional
import os, re
import pandas as pd

from my_agent.utils import config as cfg
from my_agent.utils.state import GraphState
from mcp.adapter_client import call_mcp_tool

from langchain_google_genai import ChatGoogleGenerativeAI
from my_agent.utils.config import GOOGLE_API_KEY, LLM_MODEL, LLM_TEMPERATURE

# ─────────────────────────
# Helpers
# ─────────────────────────
def normalize_store_name(name: str) -> str:
    """가맹점명 정규화: 공백 제거"""
    if not name:
        return ""
    return re.sub(r"\s+", "", name).strip()

def safe_float(value: Any, default: float = 0.0) -> float:
    """안전한 float 변환"""
    try:
        return float(value) if value is not None else default
    except (ValueError, TypeError):
        return default

def safe_int(value: Any, default: int = 0) -> int:
    """안전한 int 변환"""
    try:
        return int(value) if value is not None else default
    except (ValueError, TypeError):
        return default

def check_forbidden_content(response: str) -> Tuple[bool, List[str]]:
    """금지 콘텐츠 체크"""
    forbidden_patterns = ["100% 보장", "무조건 성공", "확실한 효과", "절대", "반드시"]
    found = []
    low = (response or "").lower()
    for p in forbidden_patterns:
        if p.lower() in low:
            found.append(p)
    return len(found) == 0, found

# ─────────────────────────
# Store Resolver (LLM 기반)
# ─────────────────────────
class StoreResolver:
    """LLM 기반 가맹점 정보 추출기 (순수 추출만 담당)"""
    
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model=cfg.LLM_MODEL,
            google_api_key=cfg.GOOGLE_API_KEY,
            temperature=0.0  # 추출 작업은 온도 낮게
        )
    
    def extract_store_info(self, user_query: str) -> Optional[str]:
        """
        사용자 쿼리에서 가맹점 관련 텍스트 추출 (이름 or 번호)
        
        Returns:
            추출된 텍스트 또는 None
            - "본죽" (마스킹 제거된 앞 2글자)
            - "761947ABD9"
            - None (가맹점 정보 없음)
        """
        system = """당신은 사용자 질문에서 가맹점 관련 정보를 추출하는 전문가입니다.

⚠️ 중요: 가맹점명은 개인정보 보호를 위해 **앞 1~2글자만 공개**되고, 나머지는 `*`로 마스킹됩니다.
- 예: "본죽****", "스타*****", "동대***", **"호*"**(두 글자 상호가 한 글자만 공개되는 사례)
- 추출 규칙: **별표(`*`)를 모두 제거하고 , **보이는 접두부(1~2글자)**만 그대로 추출**
- 보이지 않는 글자는 절대 추측하거나 임의로 보완하지 마세요.

규칙:
1. **가맹점_구분번호가 있으면 최우선 추출** (10-11자리 영문+숫자)
   - 구분번호에는 마스킹 없음 (있는 그대로 추출)
   - 예: "761947ABD9", "AB12345678"

2. **마스킹된 가맹점명은 `*`를 모두 제거하고 보이는 접두부만 반환**
   - ✅ "본죽****" → "본죽"
   - ✅ "스타*****" → "스타"
   - ✅ "동대***" → "동대"
   - ✅ **"호*" → "호"**  (접두부가 1글자뿐이어도 그대로 반환)
   - ❌ "본죽****" → "본죽****" (별표 포함 금지)
   - 불필요한 공백/괄호/특수문자/접미어(예: "점")는 제거

3. **"우리 가게", "여기" 같은 모호한 표현은 무시**
   - 이런 경우 "NONE" 반환

4. **가맹점 정보가 없으면 "NONE" 반환**

우선순위:
- 구분번호 > 마스킹된 가맹점명 앞 2글자
- "761947ABD9 본죽****" → "761947ABD9" (구분번호만)
- "본죽**** 761947ABD9" → "761947ABD9" (구분번호만)

예시:
✅ "본죽**** 매출 분석해줘" → "본죽"
✅ "스타벅스***** 재방문율은?" → "스타벅스"
✅ "동대문*** 문제점 찾아줘" → "동대문"
✅ "761947ABD9 분석해줘" → "761947ABD9"
✅ "761947ABD9 본죽****" → "761947ABD9"  # (구분번호 우선)
✅ "본죽**** 761947ABD9 트렌드" → "761947ABD9"  # (구분번호 우선)
✅ "호* 트렌드 알려줘" → "호"  # (두 글자 상호인데 1글자만 공개된 마스킹 사례)
❌ "우리 가게 매출 올리는 법" → "NONE"
❌ "치킨집 마케팅 트렌드" → "NONE"

출력: 추출된 텍스트만 한 줄로 (**별표 제거**, 추가 설명 금지)"""

        prompt = f"질문: {user_query}\n추출:"
        
        try:
            response = self.llm.invoke([("system", system), ("human", prompt)])
            extracted = response.content.strip()
            
            # "NONE" 또는 빈 값 체크
            if extracted.upper() in ["NONE", "없음", "N/A", ""]:
                print("[RESOLVER] LLM 추출 결과: 가맹점 정보 없음")
                return None
            
            # ✅ 안전장치: 혹시 LLM이 *를 포함했다면 제거
            extracted = extracted.replace('*', '')
            
            print(f"[RESOLVER] LLM 추출 결과: '{extracted}'")
            return extracted
            
        except Exception as e:
            print(f"[RESOLVER] LLM 추출 실패: {e}")
            return None

# 싱글톤 인스턴스
_resolver = None

def get_resolver() -> StoreResolver:
    """StoreResolver 싱글톤"""
    global _resolver
    if _resolver is None:
        _resolver = StoreResolver()
    return _resolver


def resolve_store(state: GraphState) -> GraphState:
    """
    사용자 쿼리에서 가맹점 정보 추출 및 확정
    
    역할 분담:
    - LLM: 사용자 쿼리에서 텍스트 추출 (이름/번호 구분 안 함)
    - MCP: DB 조회 + 패턴 인식 + 매칭 로직
    """
    
    # ✅ 이미 store_id가 있으면 스킵
    if state.get("store_id"):
        print(f"[RESOLVER] store_id 이미 존재: {state['store_id']}")
        state["need_clarify"] = False
        return state
    
    user_query = state.get("user_query", "").strip()
    if not user_query:
        state["error"] = "질문을 입력해주세요"
        state["need_clarify"] = True
        return state
    
    print("\n" + "="*60)
    print("[RESOLVER] 가맹점 검색 시작")
    print(f"[RESOLVER] 사용자 질문: '{user_query}'")
    print("="*60)
    
    # ═════════════════════════════════════════
    # 1. LLM으로 가맹점 관련 텍스트 추출
    # ═════════════════════════════════════════
    resolver = get_resolver()
    search_query = resolver.extract_store_info(user_query)
    
    if not search_query:
        # 가맹점 정보 없음 → GENERAL 모드
        print("[RESOLVER] 가맹점 정보 없음 → GENERAL 모드")
        state["store_id"] = None
        state["user_info"] = None
        state["need_clarify"] = False
        state["status"] = "ok"
        return state
    
    # ═════════════════════════════════════════
    # 2. MCP search_merchant 호출
    #    (이름/번호 자동 구분 + DB 조회는 MCP가 담당)
    # ═════════════════════════════════════════
    print(f"[RESOLVER] 검색 쿼리: '{search_query}'")
    
    try:
        result = call_mcp_tool("search_merchant", merchant_name=search_query)
    except Exception as e:
        state["error"] = f"검색 실패: {e}"
        state["need_clarify"] = True
        return state
    
    search_type = result.get("search_type", "unknown")
    print(f"[RESOLVER] 검색 유형: {search_type}")
    
    # ═════════════════════════════════════════
    # 3. 결과 처리
    # ═════════════════════════════════════════
    if not result.get("found"):
        state["error"] = result.get("message", "검색 결과 없음")
        state["need_clarify"] = True
        return state
    
    candidates = result.get("merchants", [])
    state["store_candidates"] = candidates
    
    print(f"[RESOLVER] 검색 결과: {len(candidates)}개 후보")
    
    # 3-1) 구분번호 직접 조회
    if search_type == "id":
        if candidates:
            # ✅ 조회 성공 → store_id 확정
            best = candidates[0]
            store_id = str(best.get("가맹점_구분번호", ""))
            state["store_id"] = store_id
            
            print(f"[RESOLVER] 구분번호 조회 성공, load_store_data 호출 시작...")
            
            # ✅ 완전한 데이터 로드 (load_store_data)
            try:
                result = call_mcp_tool("load_store_data", store_id=store_id, latest_only=True)
                print(f"[RESOLVER] load_store_data 결과: success={result.get('success')}")
                
                if result.get("success") and result.get("data"):
                    print(f"[RESOLVER] store_data 키: {list(result['data'].keys())}")
                    state["user_info"] = _build_user_info_from_store_data(result["data"])
                else:
                    # 로드 실패 시 기본 정보만 사용
                    print("[RESOLVER] ⚠️ load_store_data 실패, 기본 정보만 사용")
                    state["user_info"] = _build_user_info(best)
            except Exception as e:
                print(f"[RESOLVER] ⚠️ load_store_data 예외 발생: {e}, 기본 정보 사용")
                state["user_info"] = _build_user_info(best)
            
            state["need_clarify"] = False
            state["status"] = "ok"
            print(f"[RESOLVER] ✅ 구분번호 조회 완료: {state['user_info'].get('store_name')}")
            return state
        else:
            # ❌ 조회 실패 → GENERAL 모드로 폴백
            print(f"[RESOLVER] ⚠️ 구분번호 '{search_query}' 조회 실패 → GENERAL 모드")
            state["store_id"] = None
            state["user_info"] = None
            state["need_clarify"] = False
            state["status"] = "ok"
            # 사용자에게 안내 메시지 (선택사항)
            state["info_message"] = f"가맹점_구분번호 '{search_query}'를 찾을 수 없어 일반 답변으로 진행합니다."
            return state
    
    # 3-2) 가맹점명 검색 → 후보 1개면 자동 확정
    if len(candidates) == 1:
        best = candidates[0]
        store_id = str(best.get("가맹점_구분번호", ""))
        state["store_id"] = store_id
        
        print(f"[RESOLVER] 가맹점명 1개 매칭, load_store_data 호출 시작...")
        
        # ✅ 완전한 데이터 로드 (load_store_data)
        try:
            result = call_mcp_tool("load_store_data", store_id=store_id, latest_only=True)
            print(f"[RESOLVER] load_store_data 결과: success={result.get('success')}")
            
            if result.get("success") and result.get("data"):
                print(f"[RESOLVER] store_data 키: {list(result['data'].keys())}")
                state["user_info"] = _build_user_info_from_store_data(result["data"])
            else:
                print("[RESOLVER] ⚠️ load_store_data 실패, 기본 정보만 사용")
                state["user_info"] = _build_user_info(best)
        except Exception as e:
            print(f"[RESOLVER] ⚠️ load_store_data 예외 발생: {e}, 기본 정보 사용")
            state["user_info"] = _build_user_info(best)
        
        state["need_clarify"] = False
        state["status"] = "ok"
        print(f"[RESOLVER] ✅ 가맹점 자동 확정: {state['user_info'].get('store_name')}")
        return state
    
    # 3-3) 후보 여러 개 → 사용자 선택 필요
    state["need_clarify"] = True
    state["final_response"] = f"'{search_query}' 후보가 {len(candidates)}개 있습니다. 지점을 선택해주세요."
    print(f"[RESOLVER] ⚠️ 후보 여러 개 → 사용자 선택 필요")
    return state


def _build_user_info(merchant: Dict[str, Any]) -> Dict[str, Any]:
    """
    search_merchant 결과로 user_info 생성
    Note: search_merchant는 기본 정보만 반환하므로 일부 필드는 None 또는 기본값
    """
    marketing_area = merchant.get("상권") or merchant.get("상권_지리")  # ✅ 상권 우선, 없으면 상권_지리

    user_info = {
        "store_name": merchant.get("가맹점명"),
        "store_num": str(merchant.get("가맹점_구분번호", "")),
        "location": merchant.get("가맹점_주소"),
        "marketing_area": marketing_area,
        "marketing_area_type_geo": merchant.get("상권유형_지리"),  # ✅ 단일 컬럼만 사용
        "industry": merchant.get("업종"),
        "months_operating": None,
        "is_individual": None,
    }
    
    print("\n" + "="*60)
    print("[DEBUG] _build_user_info 호출 (기본 정보만)")
    print("="*60)
    print(f"입력 merchant: {merchant}")
    print(f"생성된 user_info:")
    for key, value in user_info.items():
        print(f"  - {key}: {value}")
    print("="*60 + "\n")
    
    return user_info


def _build_user_info_from_store_data(store_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    load_store_data 결과로 user_info 생성 (완전한 정보)
    
    Note: store_data는 모든 필드를 포함
    """
    print("\n" + "="*60)
    print("[DEBUG] _build_user_info_from_store_data 호출 (완전한 정보)")
    print("="*60)
    
    # 개인사업자 여부 판단 및 텍스트 변환
    biz_flag = store_data.get("개인사업자여부")
    print(f"[DEBUG] 개인사업자여부 원본 값: {biz_flag} (타입: {type(biz_flag)})")
    
    if biz_flag == 1:
        business_type = "개인사업자"
    elif biz_flag == 0:
        business_type = "프랜차이즈"
    else:
        business_type = None
    
    print(f"[DEBUG] 변환된 business_type: {business_type}")
    marketing_area = store_data.get("상권") or store_data.get("상권_지리")
    
    user_info = {
        "store_name": store_data.get("가맹점명"),
        "store_num": str(store_data.get("가맹점_구분번호", "")),
        "location": store_data.get("가맹점_주소"),
        "marketing_area": marketing_area,
        "marketing_area_type_geo": store_data.get("상권유형_지리"),  # ✅ 단일 컬럼만 사용
        "industry": store_data.get("업종"),
        "months_operating": safe_int(store_data.get("영업_경과_개월")),
        "is_individual": business_type,
    }
    
    print(f"\n생성된 user_info (완전한 정보):")
    for key, value in user_info.items():
        print(f"  - {key}: {value}")
    print("="*60 + "\n")
    
    return user_info

# 77F596FCF5 본죽 트렌드 예측해줘
# 77F596FCF5 트렌드 예측해줘
# 본죽 트렌드 예측해줘

# ─────────────────────────
# Data Loader (store + bizarea)  ← region 제거 버전
# ─────────────────────────
def load_store_and_area_data(state: GraphState, include_region: bool = False, latest_only: bool = True) -> GraphState:
    """
    store_id 기준으로 store_data + bizarea_data 조회
    ⚠️ 행정동(region) 로딩은 제거되었습니다. include_region 인자는 더 이상 사용되지 않습니다.
    """
    store_id = state.get("store_id")
    if not store_id:
        state["error"] = "store_id가 없습니다. 먼저 가맹점을 선택하세요."
        return state

    # 1) store_data (최신 1건)
    res_store = call_mcp_tool("load_store_data", store_id=store_id, latest_only=latest_only)
    if not res_store.get("success"):
        state["error"] = res_store.get("error", "가맹점 데이터 조회 실패")
        return state
    state["store_data"] = res_store["data"]

    # 2) bizarea_data (상권)
    try:
        res_biz = call_mcp_tool("load_bizarea_data", store_row=state["store_data"])
        state["bizarea_data"] = res_biz["data"] if res_biz.get("success") else None
    except Exception:
        state["bizarea_data"] = None

    # ✅ region 완전 제거 (혹시 기존 state에 남아있다면 정리)
    if "region_data" in state:
        del state["region_data"]

    return state


def find_cooperation_candidates_by_store(store_id: str, top_k: int = 5):
    """
    MCP 래퍼: store_id만 받아서 내부적으로 협업 후보 조회
    - 내부에서 load_store_data, load_bizarea_data 호출
    - 실제 DuckDB 쿼리는 mcp/tools.py의 find_cooperation_candidates 실행
    """
    print(f"[DEBUG] find_cooperation_candidates_by_store called (store_id={store_id}, top_k={top_k})")

    # 1. 가맹점 기본 데이터 조회
    store_res = call_mcp_tool("load_store_data", store_id=store_id, latest_only=True)
    if not store_res.get("success"):
        return {"success": False, "count": 0, "candidates": [], "error": f"store not found ({store_id})"}

    store = store_res["data"]
    area_geo = store.get("상권_지리")
    industry = store.get("업종")
    main_customers = [
        x for x in [
            store.get("핵심고객_1순위"),
            store.get("핵심고객_2순위"),
            store.get("핵심고객_3순위"),
        ] if x
    ]

    if not area_geo or not industry or not main_customers:
        return {
            "success": False,
            "count": 0,
            "candidates": [],
            "error": f"필수 데이터 누락 (area_geo={area_geo}, industry={industry}, main_customers={main_customers})",
        }

    # 2. 실제 협업 후보 조회 (mcp/tools.py의 find_cooperation_candidates 호출)
    result = call_mcp_tool(
        "find_cooperation_candidates",
        area_geo=area_geo,
        industry=industry,
        main_customers=main_customers,
        limit=top_k,
    )
    print(f"[DEBUG] MCP result from find_cooperation_candidates: {result}")
    return result



def get_weather_forecast_data(lat: float, lon: float, days: int = 3) -> Dict[str, Any]:
    """
    MCP weather_forecast 툴 호출 래퍼
    - 입력: 위도(lat), 경도(lon), 조회 일수(days)
    - 출력: 기상청 단기예보 (기온/강수 형태 포함)
    """
    print(f"[DEBUG] get_weather_forecast_data 호출 (lat={lat}, lon={lon}, days={days})")

    try:
        result = call_mcp_tool("get_weather_forecast", lat=lat, lon=lon, days=days)

        if not result.get("success"):
            print(f"[ERROR] 날씨 데이터 조회 실패: {result.get('message')}")
            return {
                "success": False,
                "data": [],
                "message": result.get("message", "날씨 데이터 조회 실패"),
            }

        return result

    except Exception as e:
        print(f"[EXCEPTION] get_weather_forecast_data 오류: {e}")
        return {"success": False, "data": [], "message": str(e)}