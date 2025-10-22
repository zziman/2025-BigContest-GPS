# my_agent/nodes/revisit.py

# -*- coding: utf-8 -*-
"""
RevisitNode - 재방문 유도 전략 노드 (멀티턴 대화 지원)
- 항상 resolve_store 실행 (store 탐지는 자동 시도)
- store 없으면 fallback 답변
- store 있으면 revisit 포함 분석
- 후처리(postprocess_response)로 텍스트 정제 + 웹 출처 토글 추가
"""

from typing import Dict, Any
from langchain_google_genai import ChatGoogleGenerativeAI

from my_agent.utils.config import GOOGLE_API_KEY, LLM_MODEL, LLM_TEMPERATURE
from my_agent.utils.tools import resolve_store, load_store_and_area_data

from my_agent.metrics.main_metrics import build_main_metrics
from my_agent.metrics.strategy_metrics import build_strategy_metrics
from my_agent.metrics.revisit_metrics import build_revisit_metrics
from my_agent.utils.postprocess import postprocess_response, format_web_snippets


class RevisitNode:
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model=LLM_MODEL,
            google_api_key=GOOGLE_API_KEY,
            temperature=LLM_TEMPERATURE
        )

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        user_query = (state.get("user_query") or "").strip()
        web_snippets = state.get("web_snippets", [])

        # 1) 항상 store 탐지 시도
        if not state.get("store_id"):
            state = resolve_store(state)

        store_id = state.get("store_id")

        # 2) store 있는 경우에만 metrics 생성
        metrics: Dict[str, Any] = {}
        errors: Dict[str, str] = {}

        if store_id:
            # 가게/상권 데이터 적재 (최신행만)
            try:
                state = load_store_and_area_data(state, include_region=False, latest_only=True)
            except Exception as e:
                errors["load_store_and_area_data"] = str(e)

            # 2-1) 메인 지표
            try:
                res_main = build_main_metrics(store_id)  # {"main_metrics": {...}, "상권_단위_정보": {...}} 권장
                if isinstance(res_main, dict):
                    if res_main.get("main_metrics"):
                        metrics["main_metrics"] = res_main["main_metrics"]
                    if res_main.get("상권_단위_정보"):
                        metrics["상권_단위_정보"] = res_main["상권_단위_정보"]
            except Exception as e:
                errors["build_main_metrics"] = str(e)

            # 2-2) 전략 강도 지표
            try:
                res_strategy = build_strategy_metrics(store_id)  # 보통 {"strategy_metrics": {...}}
                if isinstance(res_strategy, dict) and res_strategy.get("strategy_metrics"):
                    metrics["strategy_metrics"] = res_strategy["strategy_metrics"]
                else:
                    # 함수가 바로 dict를 반환하는 구현일 수도 있음
                    metrics["strategy_metrics"] = res_strategy
            except Exception as e:
                errors["build_strategy_metrics"] = str(e)

            # 2-3) 재방문 지표 + 이상치
            try:
                res_revisit = build_revisit_metrics(store_id)  # {"revisit_metrics": {...}, "abnormal_metrics": {...}, "yyyymm": ...}
                if isinstance(res_revisit, dict):
                    if res_revisit.get("revisit_metrics"):
                        metrics["revisit_metrics"] = res_revisit["revisit_metrics"]
                    if res_revisit.get("abnormal_metrics"):
                        metrics["revisit_abnormal"] = res_revisit["abnormal_metrics"]
                        
            except Exception as e:
                errors["build_revisit_metrics"] = str(e)

        state["metrics"] = metrics if metrics else None
        state["errors"] = errors if errors else None  # 디버깅 편의

        # 3) ✅ 프롬프트 (요청한 형식으로 교체)
        prompt = f"""
# 당신은 데이터 기반 재방문 전략 설계 전문가입니다  
주어진 정보를 바탕으로 매장의 **재방문율과 단골 고객 비중을 높이는 실행 전략**을 제시하세요.

---

## 질문
{user_query}

## 가게 정보
{state.get("user_info")}

## 데이터 지표
{state.get("metrics")}

## 웹 참고 정보
{format_web_snippets(web_snippets)}

---

## 출력 형식
### 1. 현재 상황 요약
- 매장 현황과 고객 및 상권 패턴을 간단히 요약  

### 2. 핵심 데이터 분석  
- 재방문 관련 주요 수치 및 추세 분석 (근거 중심)

### 3. 재방문 유도 전략  
- 구체적이고 실행 가능한 전략 제안  
- 캠페인, 혜택, 고객세분화 등 포함

### 4. 기대 효과
- 전략 실행 후 기대할 수 있는 변화와 지표 개선 전망

---

## 작성 규칙
1. **분석 → 근거 → 전략 → 기대효과** 순으로 구성  
2. 데이터(metrics)에서 **실제 수치를 직접 인용**  
3. 일반론 금지 — 매장 상황에 맞는 구체적 전략 제시  
4. 필요 시 **표나 리스트** 활용 가능  
5. 데이터 부족 시 웹 참고 정보 기반으로 현실적 리텐션 전략 보완  
6. 임의 수치 생성 금지
        """

        # 4) LLM 호출
        raw_response = self.llm.invoke(prompt).content

        # 5) ✅ 후처리 적용: 텍스트 정제 + 웹 출처 토글(있을 때만)
        final_output = postprocess_response(
            raw_response=raw_response,
            web_snippets=web_snippets
        )

        # 6) 상태 저장
        state["final_response"] = final_output
        state["error"] = None
        state["need_clarify"] = False
        return state


if __name__ == "__main__":
    import sys, json

    args = sys.argv[1:]
    query = None
    store_id = None

    for i, a in enumerate(args):
        if a == "--query" and i + 1 < len(args):
            query = args[i + 1]
        elif a == "--store" and i + 1 < len(args):
            store_id = args[i + 1]

    if not query:
        print("❗ 사용법: python -m my_agent.nodes.revisit --query '질문' [--store STORE_ID]")
        # 예) python -m my_agent.nodes.revisit --query "해당 가게의 재방문율을 높이는 전략 알려줘" --store 761947ABD9
        sys.exit(1)

    init_state = {"user_query": query}
    if store_id:
        init_state["store_id"] = store_id

    node = RevisitNode()
    result = node(init_state)
    print(json.dumps(result, ensure_ascii=False, indent=2))