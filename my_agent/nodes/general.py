# my_agent/nodes/general.py

# -*- coding: utf-8 -*-
"""
GeneralNode - 일반 마케팅 분석/조언 노드
- 항상 resolve_store 실행 (store 탐지는 자동 시도)
- store 없으면 fallback 답변
- store 있으면 general_metrics 포함 분석
"""

from typing import Dict, Any
from langchain_google_genai import ChatGoogleGenerativeAI

from my_agent.utils.config import GOOGLE_API_KEY, LLM_MODEL, LLM_TEMPERATURE
from my_agent.utils.tools import resolve_store, load_store_and_area_data
from my_agent.metrics.general_metrics import build_general_metrics


class GeneralNode:
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model=LLM_MODEL,
            google_api_key=GOOGLE_API_KEY,
            temperature=LLM_TEMPERATURE)

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        user_query = state.get("user_query", "").strip()
        web_snippets = state.get("web_snippets", [])

        # 1. 항상 store 탐지 시도
        state = resolve_store(state)

        # 2. store 있는 경우에만 metrics 생성
        metrics = None
        if state.get("store_id"):
            state = load_store_and_area_data(state, include_region=False, latest_only=True)
            try:
                metrics = build_general_metrics(state["store_id"]).get("general_metrics")
            except Exception:
                metrics = None

        state["metrics"] = {"general_metrics": metrics} if metrics else None

        # 3. Prompt 구성(JSON 구조로 그대로 포함)
        prompt = f"""
당신은 데이터 기반 마케팅 전략가입니다. 아래 정보를 바탕으로 **근거 있는 분석과 실행 전략**을 제시하세요.

### 질문
{user_query}

### 가게 정보
{state.get("user_info")}

### 데이터 지표
{state.get("metrics")}

### 웹 참고 정보
{web_snippets}

### 답변 규칙
- 분석 → 근거 → 실행 전략 순으로 답변
- **가능한 경우 제공된 데이터(metrics)에서 수치 근거 활용**
- 일반론 금지, **스토어 상황에 맞는 구체 전략** 제시
- 리스트 또는 표 활용 가능
- 만약 가게 정보와 데이터 지표가 제공되지 않으면 질문에 대한 답변은 웹 정보를 참고해 답변

### 출력 형식
1. 현재 상황 요약
2. 핵심 데이터 분석 (근거 2~3개)
3. 전략 제안 (실행 가능하고 구체적으로)
4. 기대 효과
        """

        # 4. LLM 호출
        response = self.llm.invoke(prompt).content
        state["error"] = None
        state["final_response"] = response
        state["need_clarify"] = False  # General은 clarify 없이 항상 답 생성
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
        print("❗ 사용법: python -m my_agent.nodes.general --query '질문' [--store STORE_ID]")
        # python -m my_agent.nodes.general --query "최신 음식점 마케팅 트렌드 알려줘"
        # python -m my_agent.nodes.general --query "최신 음식점 마케팅 트렌드 알려줘" --store 761947ABD9
        sys.exit(1)

    state = {"user_query": query}
    if store_id:
        state["store_id"] = store_id

    node = GeneralNode()
    result = node(state)
    print(json.dumps(result, ensure_ascii=False, indent=2))