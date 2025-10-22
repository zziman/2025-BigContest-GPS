# my_agent/nodes/cooperation.py
# -*- coding: utf-8 -*-
"""
CooperationNode - 협업 후보 추천 노드
- 동일 상권 내 비경쟁 업종을 탐색하고 협업 잠재력이 높은 점포를 추천
- find_cooperation_candidates MCP 툴 호출 기반
"""

from typing import Dict, Any, List
from langchain_google_genai import ChatGoogleGenerativeAI

from my_agent.utils.config import GOOGLE_API_KEY, LLM_MODEL, LLM_TEMPERATURE
from my_agent.utils.tools import resolve_store, load_store_and_area_data, find_cooperation_candidates_by_store
from my_agent.utils.postprocess import postprocess_response, format_web_snippets
from my_agent.metrics.cooperation_metrics import build_cooperation_metrics
from mcp.adapter_client import call_mcp_tool


class CooperationNode:
    """협업 후보 탐색 및 추천 노드"""

    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model=LLM_MODEL,
            google_api_key=GOOGLE_API_KEY,
            temperature=LLM_TEMPERATURE
        )

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        user_query = state.get("user_query", "").strip()
        web_snippets = state.get("web_snippets", [])

        # 1. 항상 store 탐지 시도
        if not state.get("store_id"):
            state = resolve_store(state)
            
        store_id = state["store_id"]

        metrics: Dict[str, Any] = {}
        errors: Dict[str, str] = {}

        # 2. 가맹점 및 상권 데이터 로드
        if store_id:
            try:
                state = load_store_and_area_data(state, latest_only=True)
            except Exception as e:
                errors["load_store_and_area_data"] = str(e)

            ## 메인 지표
            try:
                res_main = build_main_metrics(store_id)  # {"main_metrics": {...}, "상권_단위_정보": {...}} 권장
                if isinstance(res_main, dict):
                    if res_main.get("main_metrics"):
                        metrics["main_metrics"] = res_main["main_metrics"]
                    if res_main.get("상권_단위_정보"):
                        metrics["상권_단위_정보"] = res_main["상권_단위_정보"]
            except Exception as e:
                errors["build_main_metrics"] = str(e)

            ## 전략 강도 지표
            try:
                res_strategy = build_strategy_metrics(store_id)  # 보통 {"strategy_metrics": {...}}
                if isinstance(res_strategy, dict) and res_strategy.get("strategy_metrics"):
                    metrics["strategy_metrics"] = res_strategy["strategy_metrics"]
                else:
                    metrics["strategy_metrics"] = res_strategy
            except Exception as e:
                errors["build_strategy_metrics"] = str(e)

            ## 협업 메트릭 계산
            try:
                metrics['협업_metrics'] = build_cooperation_metrics(store_id)
            except Exception as e:
                state["error"] = f"협업 메트릭 계산 실패: {e}"

            # 협업 후보 조회
            try:
                result = find_cooperation_candidates_by_store(store_id=store_id, top_k=5)
            except Exception as e:
                state["error"] = f"MCP 호출 실패: {e}"
                result = {"success": False, "candidates": []}

        candidates: List[Dict[str, Any]] = result.get("candidates", [])
        state["metrics"] = metrics if metrics else None

        # 5. LLM 프롬프트 구성
        prompt = f"""
# 당신은 소상공인 마케팅 전문가입니다.  
주어진 데이터와 후보 점포 리스트를 바탕으로 **협업 가능한 매장 조합과 시너지 아이디어**를 제시하세요.

---

## 사용자 질문
{user_query}

## 가게 정보
{state.get("user_info")}

## 데이터 지표
{state.get("metrics")}

## 협업 후보 점포 (상위 {len(candidates)}개)
{candidates}

## 웹 참고 정보
{format_web_snippets(web_snippets)}

---

## 출력 형식
### 1. **현재 매장 분석**  
   - 고객층 및 상권 특성 요약  
   - 협업이 필요한 이유 (데이터 기반)
### 2. **추천 협업 파트너**  
   - 후보 점포 리스트 중 상위 2~3곳을 선택  
   - 각 점포별 협업 포인트 제시  
     - 고객층 겹침 (예: 직장인 중심 / 20~30대 여성 등)  
     - 업종 차이에서 오는 시너지 (예: 카페 ↔ 꽃집, 학원 ↔ 간식가게)
### 3. **공동 마케팅 아이디어**  
   - SNS 공동 이벤트 / 쿠폰 교차제공 / 배달 패키지 등  
   - 각 아이디어에 대한 기대효과를 데이터 기반으로 설명
### 4. **기대효과 요약**  
   - 고객 재방문률 상승, 신규 유입률 개선 등

---

## 작성 규칙
1. metrics와 candidates에 기반한 사실만 언급 (추측 금지)
2. 업종/상권 데이터를 해석적으로 요약
3. 불필요한 일반론 금지
4. 문단별 제목 유지
"""

        # 6. LLM 호출 및 후처리
        raw_response = self.llm.invoke(prompt).content
        final_response = postprocess_response(
            raw_response=raw_response,
            web_snippets=web_snippets
        )

        # 7. 상태 갱신
        state["final_response"] = final_response
        state["need_clarify"] = False
        state["error"] = None

        return state


if __name__ == "__main__":
    import sys, json

    args = sys.argv[1:]
    query = None
    store_id = None

    for i, a in enumerate(args):
        if a == "--query":
            query = args[i + 1]
        elif a == "--store":
            store_id = args[i + 1]

    if not query:
        print("❗ 사용법: python -m my_agent.nodes.cooperation --query '질문' [--store STORE_ID]")
        # python -m my_agent.nodes.cooperation --query '우리 매장이랑 협업하면 좋은 근처 가게 추천해줘.' --store 3B0F367222
        sys.exit(1)

    state = {"user_query": query}
    if store_id:
        state["store_id"] = store_id

    node = CooperationNode()
    result = node(state)
    print(json.dumps(result, ensure_ascii=False, indent=2))
