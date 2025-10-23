# my_agent/nodes/general.py
# -*- coding: utf-8 -*-
"""
GeneralNode - 일반 마케팅 분석/조언 노드
- main_metrics (필수): 핵심 성과 지표
- strategy_metrics (선택): 전략 방향성 지표
- general_metrics (선택): 보완 정보
"""

from typing import Dict, Any, Optional
from langchain_google_genai import ChatGoogleGenerativeAI
import json

from my_agent.utils.config import GOOGLE_API_KEY, LLM_MODEL, LLM_TEMPERATURE
from my_agent.utils.tools import resolve_store, load_store_and_area_data
from my_agent.metrics.main_metrics import build_main_metrics
from my_agent.metrics.general_metrics import build_general_metrics
from my_agent.utils.postprocess import postprocess_response, format_web_snippets


class GeneralNode:
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model=LLM_MODEL,
            google_api_key=GOOGLE_API_KEY,
            temperature=LLM_TEMPERATURE
        )
    
    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """General 노드 실행"""
        user_query = state.get("user_query", "").strip()
        web_snippets = state.get("web_snippets", [])
        
        # 1. Store 탐지 (store_id 없을 때만)
        if not state.get("store_id"):
            state = resolve_store(state)
        
        store_id = state.get("store_id")
        
        # 2. Metrics 로드 (store 있을 때만)
        metrics: Dict[str, Any] = {}
        errors: Dict[str, str] = {}
        
        if store_id:
            try:
                # Store + Bizarea 데이터 로드
                state = load_store_and_area_data(
                    state, 
                    include_region=False, 
                    latest_only=True
                )
                
                # Main Metrics 로드 (필수)
                try:
                    res_main = build_main_metrics(store_id)
                    if isinstance(res_main, dict):
                        if res_main.get("main_metrics"):
                            metrics["main_metrics"] = res_main["main_metrics"]
                        if res_main.get("상권_단위_정보"):
                            metrics["상권_단위_정보"] = res_main["상권_단위_정보"]
                    print("[INFO] Main Metrics 로드 성공")
                except Exception as e:
                    errors["build_main_metrics"] = str(e)
                    print(f"[ERROR] Main Metrics 로드 실패: {e}")
                
                # Strategy Metrics 로드 (선택)
                try:
                    from my_agent.metrics.strategy_metrics import build_strategy_metrics
                    res_strategy = build_strategy_metrics(store_id)
                    if isinstance(res_strategy, dict) and res_strategy.get("strategy_metrics"):
                        metrics["strategy_metrics"] = res_strategy["strategy_metrics"]
                    print("[INFO] Strategy Metrics 로드 성공")
                except Exception as e:
                    errors["build_strategy_metrics"] = str(e)
                    print(f"[WARN] Strategy Metrics 로드 실패 (옵션): {e}")
                
                # General Metrics 로드 (선택)
                try:
                    res_general = build_general_metrics(store_id)
                    if isinstance(res_general, dict) and res_general.get("general_metrics"):
                        metrics["general_metrics"] = res_general["general_metrics"]
                    print("[INFO] General Metrics 로드 성공")
                except Exception as e:
                    errors["build_general_metrics"] = str(e)
                    print(f"[WARN] General Metrics 로드 실패 (옵션): {e}")
                
            except Exception as e:
                errors["load_store_and_area_data"] = str(e)
                print(f"[ERROR] 데이터 로드 실패: {e}")
                import traceback
                traceback.print_exc()
        
        state["metrics"] = metrics if metrics else None
        state["errors"] = errors if errors else None
        
        # 3. 프롬프트 생성
        prompt = self._build_prompt(state)
        
        # 4. LLM 호출
        try:
            raw_response = self.llm.invoke(prompt).content

            final_response = postprocess_response(
                raw_response=raw_response,
                web_snippets=web_snippets
            )

            state["final_response"] = final_response
            state["error"] = None
            state["need_clarify"] = False
            return state
            
        except Exception as e:
            state["error"] = f"LLM 호출 실패: {e}"
            state["final_response"] = "죄송합니다. 응답 생성 중 오류가 발생했습니다."
        
        return state
    
    def _build_prompt(self, state: Dict[str, Any]) -> str:
        """변수 추출 후 간결하게 사용"""
        
        system = """당신은 소상공인을 위한 **데이터 기반 마케팅 전략가**입니다.
주어진 정보를 해석하여 매장의 **현재 상태 분석 및 실행 가능한 마케팅 전략**을 제시하세요.
"""
        
        # 변수 추출
        user_query = state.get("user_query")
        user_info = state.get("user_info")
        metrics = state.get("metrics")
        web_snippets = state.get("web_snippets", [])
        
        # Metrics가 있는 경우
        if metrics:
            return f"""{system}
---

## 질문
{user_query}

## 가게 정보
{user_info}

## 데이터 지표
{metrics}

## 웹 참고 정보
{format_web_snippets(web_snippets)}

---

## 출력 형식

### 1. 현재 상황 요약
- 데이터를 바탕으로 매장의 현황과 주요 특징을 2~3문장으로 정리

### 2. 핵심 데이터 분석
- 핵심 지표 2~3개를 근거로 분석 (수치 포함)

### 3. 전략 제안
- 실행 가능한 마케팅 전략 2~3개 제시
- 전략별 예상 효과 및 적용 방법 명시

### 4. 기대 효과
- 전략 실행 시 기대할 수 있는 지표 개선이나 매출 효과 설명

---

## 작성 규칙
1. **근거 기반** — 제공된 데이터나 웹 정보를 반드시 활용
2. **실행 가능성** — 추상적 조언 금지, 구체적 액션 제시
3. **맞춤형 전략** — 상황에 맞는 솔루션 제시
4. **투명성** — 모든 주장에 근거 명시
5. "100% 성공", "확실한 효과" 등 과장 표현 금지
6. 데이터 없는 추측 금지
7. 복사/붙여넣기식 일반론 금지
"""
        
        # Metrics가 없는 경우
        else:
            return f"""{system}
---

## 질문
{user_query}

## 웹 참고 정보
{format_web_snippets(web_snippets)}

---

## 출력 형식

### 1. 현재 상황 요약
- 질문의 맥락을 파악하여 2~3문장으로 요약

### 2. 핵심 데이터 분석
- 웹 정보나 일반적 마케팅 지식을 바탕으로 2~3개 근거 제시

### 3. 전략 제안
- 실행 가능한 마케팅 전략 2~3개 제시
- 전략별 예상 효과 및 적용 방법 명시

### 4. 기대 효과
- 전략 실행 시 기대할 수 있는 효과 설명

---

## 작성 규칙
1. **근거 기반** — 웹 정보를 반드시 활용
2. **실행 가능성** — 추상적 조언 금지, 구체적 액션 제시
3. **맞춤형 전략** — 상황에 맞는 솔루션 제시
4. **투명성** — 모든 주장에 근거 명시
5. "100% 성공", "확실한 효과" 등 과장 표현 금지
6. 데이터 없는 추측 금지
7. 복사/붙여넣기식 일반론 금지
"""


# CLI Test
if __name__ == "__main__":
    import sys
    
    args = sys.argv[1:]
    query = None
    store_id = None

    for i, a in enumerate(args):
        if a == "--query" and i + 1 < len(args):
            query = args[i + 1]
        elif a == "--store" and i + 1 < len(args):
            store_id = args[i + 1]

    if not query:
        print("사용법: python -m my_agent.nodes.general --query '질문' [--store STORE_ID]")
        print("예시 1: python -m my_agent.nodes.general --query '최신 음식점 마케팅 트렌드 알려줘'")
        print("예시 2: python -m my_agent.nodes.general --query '본죽 매출 분석' --store 761947ABD9")
        sys.exit(1)

    state = {"user_query": query}
    if store_id:
        state["store_id"] = store_id

    node = GeneralNode()
    result = node(state)
    
    print("\n" + "="*60)
    print("실행 결과")
    print("="*60)
    print(json.dumps(result, ensure_ascii=False, indent=2))