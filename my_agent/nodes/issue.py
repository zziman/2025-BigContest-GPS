# my_agent/nodes/issue.py


# -*- coding: utf-8 -*-
"""
IssueNode - 핵심 문제 진단 노드
- store 기반 문제 분석 및 핵심 이슈 식별
- issue_metrics + abnormal_metrics 기반 문제 요약
"""

from typing import Dict, Any
from langchain_google_genai import ChatGoogleGenerativeAI

from my_agent.utils.config import GOOGLE_API_KEY, LLM_MODEL, LLM_TEMPERATURE
from my_agent.utils.tools import resolve_store, load_store_and_area_data

from my_agent.metrics.main_metrics import build_main_metrics
from my_agent.metrics.issue_metrics import build_issue_metrics


class IssueNode:
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

        store_id = state.get("store_id")

        # 2. store 있는 경우에만 metrics 생성
        metrics: Dict[str, Any] = {}
        if store_id:
            try:
                m_main = build_main_metrics(store_id)
                metrics["main_metrics"] = m_main.get("main_metrics", {})
            except Exception:
                pass

            try:
                m_issue = build_issue_metrics(store_id)
                metrics["issue_metrics"] = m_issue.get("issue_metrics", {})
                metrics["abnormal_metrics"] = m_issue.get("abnormal_metrics", {})
            except Exception:
                pass

        state["metrics"] = metrics if metrics else None

        # 3. Prompt 구성(JSON 구조 그대로 사용)
        prompt = f"""
당신은 데이터 기반 문제 진단 전문가입니다.
주어진 지표를 해석하여 현재 매장의 **핵심 문제와 원인**을 분석하세요.

### 질문
{user_query}

### 매장 정보
{state.get("user_info")}

### 데이터 지표
{state.get("metrics")}

### 웹 참고 데이터
{web_snippets}

---

### 출력 형식
아래 형식을 반드시 유지하여 문제를 분석하세요.

[현재 상황 분석]
- 매장의 현재 상황을 데이터 기반으로 요약 설명

[핵심 문제 요약]
- 이 매장이 겪고 있는 가장 핵심적인 비즈니스 문제를 한 줄로 콕 집어 표현

[이상 지표 분석]
- abnormal_metrics를 활용해 이상 징후를 나열

[문제 원인]
- 데이터와 논리를 근거로 원인을 2~4개 정리

[개선 방향]
- 문제점을 보완할 마케팅 아이디어와 근거를 제시
- 웹 검색 결과 또한 사용해서 아이디어를 제시

---

### 작성 규칙
- 오직 위 JSON 데이터(metrics) 기반으로만 분석
- **데이터 기반 문장 작성 (임의로 숫자 생성 금지)**
- 비즈니스적으로 정확하게 설명
- 너무 일반적인 말 금지
- 아이디어와 근거를 명확히 제시
- 참고 출처를 제시
"""

        # 4. LLM 호출
        response = self.llm.invoke(prompt).content
        state["final_response"] = response
        state["error"] = None
        state["need_clarify"] = False
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
        print("❗ 사용법: python -m my_agent.nodes.issue --query '질문' [--store STORE_ID]")
        sys.exit(1)

    state = {"user_query": query}
    if store_id:
        state["store_id"] = store_id

    node = IssueNode()
    result = node(state)
    print(json.dumps(result, ensure_ascii=False, indent=2))