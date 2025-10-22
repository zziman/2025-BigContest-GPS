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
from my_agent.utils.postprocess import postprocess_response, format_web_snippets


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
# 당신은 데이터 기반 문제 진단 전문가입니다  
주어진 정보를 해석하여 매장의 **핵심 문제와 원인**을 도출하세요.

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
### 1. 현재 상황 분석
- 데이터를 바탕으로 현재 매장의 상황을 요약 (2~3문장)

### 2. 핵심 문제 요약
- 매장이 겪고 있는 가장 핵심적인 비즈니스 문제를 한 문장으로 요약

### 3. 이상 지표 분석
- abnormal_metrics를 활용하여 감지된 이상 지표를 구체적으로 나열

### 4. 문제 원인
- 데이터를 근거로 한 주요 원인 2~4가지 제시

### 5. 개선 방향
- 문제 해결을 위한 마케팅 아이디어 제안  
- 각 아이디어의 **데이터적 근거** 명시  
- 웹 참고 데이터 활용 가능

### 6. 기대 효과
- 전략 실행 후 기대할 수 있는 변화와 지표 개선 전망

---

## 작성 규칙
1. 오직 위 JSON 데이터(metrics)에 기반하여 분석  
2. 임의의 수치 생성 금지  
3. 데이터 근거를 포함한 문장 작성  
4. 추상적 설명 및 일반론 금지  
5. 근거와 아이디어를 구체적으로 명시  
6. 참고 출처 명시 가능
"""

        # 4. LLM 호출
        raw_response = self.llm.invoke(prompt).content

        final_response = postprocess_response(
            raw_response=raw_response,
            web_snippets=web_snippets
        )

        state["final_response"] = final_response
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
