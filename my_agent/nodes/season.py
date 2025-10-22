# my_agent/nodes/season.py

# -*- coding: utf-8 -*-
"""
SeasonNode - 계절·날씨 기반 마케팅 전략 노드
- 계절, 날씨, 상권 패턴 데이터 기반으로 마케팅 인사이트 생성
"""

from typing import Dict, Any
from langchain_google_genai import ChatGoogleGenerativeAI
from my_agent.utils.config import GOOGLE_API_KEY, LLM_MODEL, LLM_TEMPERATURE
from my_agent.utils.tools import resolve_store, load_store_and_area_data
from my_agent.metrics.main_metrics import build_main_metrics
from my_agent.metrics.strategy_metrics import build_strategy_metrics
from my_agent.metrics.season_metrics import build_season_metrics
from my_agent.utils.postprocess import postprocess_response, format_web_snippets


class SeasonNode:
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model=LLM_MODEL,
            google_api_key=GOOGLE_API_KEY,
            temperature=LLM_TEMPERATURE
        )

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        user_query = state.get("user_query", "").strip()
        web_snippets = state.get("web_snippets", [])

        # store_id 확인 및 로드
        if not state.get("store_id"):
            state = resolve_store(state)
        store_id = state.get("store_id")

        if not store_id:
            state["error"] = "store_id를 찾을 수 없습니다."
            return state

        try:
            m_main = build_main_metrics(store_id)
            metrics["main_metrics"] = m_main.get("main_metrics", {})
        except Exception as e:
            print(f"[WARN] main_metrics 생성 실패: {e}")

        try:
            m_strategy = build_strategy_metrics(store_id)
            metrics["strategy_metrics"] = m_strategy.get("strategy_metrics", {})
        except Exception as e:
            print(f"[WARN] strategy_metrics 생성 실패: {e}")
            
        # season metrics 생성
        try:
            m_season = build_season_metrics(store_id)
            metrics = {"season_metrics": m_season.get("season_metrics", {})}
        except Exception as e:
            metrics = {}
            state["error"] = f"season_metrics 생성 실패: {e}"

        state["metrics"] = metrics if metrics else None

        # LLM 프롬프트 구성
        prompt = f"""
# 당신은 계절·날씨 기반 마케팅 전략 전문가입니다.  
주어진 데이터를 바탕으로 매장의 **계절적 특징, 날씨 영향, 상권 고객 흐름 패턴**을 해석하세요.

---

## 사용자 질문
{user_query}

## 가게 기본 정보
{state.get("user_info")}

## 계절 및 날씨 데이터
{state.get("metrics")}

## 참고 웹 정보
{format_web_snippets(web_snippets)}

---

## 출력 형식
### 1. 현재 계절 및 날씨 요약
- 평균기온, 강수 상태, 전반적인 기상 특징을 간단히 요약

### 2. 상권 고객 활동 패턴
- 상권 내 주요 활성 시간대와 그 의미를 설명  
- 예: "오후 17~21시는 직장인 퇴근 유입 중심의 시간대"

### 3. 고객 패턴 분석
- 핵심 고객군을 분석하여 고객 패턴을 파악
- 예: "여성 20대가 핵심 고객군이기 때문에 SNS 프로모션 효과가 높을 가능성"

### 4. 계절형 마케팅 전략 제안
- 현재 계절과 날씨, 고객유형에 맞는 구체적 마케팅 전략 제시  
- 예: “가을철 저녁 유입 증가 → 야외 테이크아웃 세트 할인”  
- 각 전략은 **데이터 근거**를 함께 제시

### 5. 실행 시 기대효과
- 매출, 유입, 체류시간 등의 개선 가능성 예측

---

## 작성 규칙
1. 모든 분석은 season_metrics 데이터에 근거  
2. 계절·날씨·시간대 패턴을 함께 고려  
3. 구체적이고 실질적인 마케팅 아이디어 제시  
4. 근거 수치나 요약 문장을 반드시 포함
"""

        # LLM 호출
        raw_response = self.llm.invoke(prompt).content
        final_response = postprocess_response(raw_response, web_snippets)

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
        print("사용법: python -m my_agent.nodes.season --query '질문' [--store STORE_ID]")
        # python -m my_agent.nodes.season --query "날씨에 맞는 마케팅 전략을 알려줘" --store 3B0F367222
        sys.exit(1)
    state = {"user_query": query}
    if store_id:
        state["store_id"] = store_id

    node = SeasonNode()
    result = node(state)
    print(json.dumps(result, ensure_ascii=False, indent=2))
