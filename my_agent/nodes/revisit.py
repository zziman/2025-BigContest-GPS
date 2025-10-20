# my_agent/nodes/revisit.py

# -*- coding: utf-8 -*-
"""
RevisitNode - 재방문 유도 전략 노드
- 항상 resolve_store 실행 (store 탐지는 자동 시도)
- store 없으면 fallback 답변
- store 있으면 revisit 포함 분석
"""

from typing import Dict, Any
from langchain_google_genai import ChatGoogleGenerativeAI

from my_agent.utils.config import GOOGLE_API_KEY, LLM_MODEL, LLM_TEMPERATURE
from my_agent.utils.tools import resolve_store, load_store_and_area_data

from my_agent.metrics.main_metrics import build_main_metrics
from my_agent.metrics.strategy_metrics import build_strategy_metrics
# from my_agent.metrics.revisit_metrics import build_revisit_metrics


class RevisitNode:
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model=LLM_MODEL,
            google_api_key=GOOGLE_API_KEY,
            temperature=LLM_TEMPERATURE)

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        user_query = state.get("user_query", "").strip()
        web_snippets = state.get("web_snippets", [])

        # 1. 항상 store 탐지 시도
        if not state.get("store_id"):
            state = resolve_store(state)
        
        store_id = state.get("store_id")

        # 2. store 있는 경우에만 metrics 생성
        metrics: Dict[str, Any] = {}
        if state.get("store_id"):
            # 가게/상권 데이터 적재
            state = load_store_and_area_data(state, include_region=False, latest_only=True)

            store_id = state["store_id"]
            # 각 지표 빌드 (실패해도 나머지 진행)
            try:
                m_main = build_main_metrics(store_id), "main_metrics"
                if m_main:
                    metrics["main_metrics"] = m_main
            except Exception:
                pass

            try:
                m_strategy = build_strategy_metrics(store_id), "strategy_metrics"
                if m_strategy:
                    metrics["strategy_metrics"] = m_strategy
            except Exception:
                pass

            try:
                m_revisit = build_revisit_metrics(store_id), "revisit_metrics"
                if m_revisit:
                    metrics["revisit_metrics"] = m_revisit
            except Exception:
                pass

        state["metrics"] = metrics if metrics else None

        # 3. Prompt 구성(JSON 구조로 그대로 포함)
        prompt = f"""
당신은 데이터 기반 재방문 전략을 설계하는 전문가 전략가입니다. 
아래 정보를 바탕으로 매장의 재방문율과 단골 고객 비중을 높이기 위한 구체적 실행 전략을 제시하세요.

### 질문
{user_query}

### 가게 정보
{state.get("user_info")}

### 데이터 지표
{state.get("metrics")}

### 웹 참고 정보
{web_snippets}

### 답변 규칙
- 분석 → 근거 → 전략 → 기대효과 순으로 답변
- **제공된 데이터(metrics)에서 수치 근거 활용**
- 일반론 금지, **스토어 상황에 맞는 구체 전략** 제시
- 리스트 또는 표 활용 가능
- 지표가 부족한 경우에는 웹 정보(web_snippets)를 참고하되, 매장 상황에 맞는 현실적인 리텐션 전략을 제시
- 숫자나 지표를 임의로 만들어내지 않아야 함

### 출력 형식
1. 현재 상황 요약
2. 핵심 데이터 분석 (근거 중심)
3. 재방문 유도 전략 (실행 가능하고 구체적으로)
4. 기대 효과
        """

        # 4. LLM 호출
        response = self.llm.invoke(prompt).content
        state["error"] = None
        state["final_response"] = response
        state["need_clarify"] = False #미정
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
        print("❗ 사용법: python -m my_agent.nodes.revisit --query '질문' [--store STORE_ID]")
        # python -m my_agent.nodes.revisit --query "해당 가게의 재방문율을 높이는 전략 알려줘" --store 761947ABD9
        sys.exit(1)

    state = {"user_query": query}
    if store_id:
        state["store_id"] = store_id

    node = RevisitNode()
    result = node(state)
    print(json.dumps(result, ensure_ascii=False, indent=2))