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
        
        # ═════════════════════════════════════════
        # 1. Store 탐지 (store_id 없을 때만)
        # ═════════════════════════════════════════
        if not state.get("store_id"):
            state = resolve_store(state)
        
        store_id = state.get("store_id")
        
        # ═════════════════════════════════════════
        # 2. Metrics 로드 (store 있을 때만)
        # ═════════════════════════════════════════
        metrics = None
        
        if store_id:
            try:
                # Store + Bizarea 데이터 로드
                state = load_store_and_area_data(
                    state, 
                    include_region=False, 
                    latest_only=True
                )
                
                # ✅ Main Metrics 로드 (필수)
                main_metrics = None
                상권_단위_정보 = None
                try:
                    main_result = build_main_metrics(store_id)
                    main_metrics = main_result.get("main_metrics")
                    상권_단위_정보 = main_result.get("상권_단위_정보")
                    print("[INFO] ✅ Main Metrics 로드 성공")
                except Exception as e:
                    print(f"[ERROR] Main Metrics 로드 실패: {e}")
                
                # ✅ Strategy Metrics 로드 (선택)
                strategy_metrics = None
                try:
                    from my_agent.metrics.strategy_metrics import build_strategy_metrics
                    strategy_result = build_strategy_metrics(store_id)
                    strategy_metrics = strategy_result.get("strategy_metrics")
                    print("[INFO] ✅ Strategy Metrics 로드 성공")
                except Exception as e:
                    print(f"[WARN] Strategy Metrics 로드 실패 (옵션): {e}")
                
                # ✅ General Metrics 로드 (선택)
                general_metrics = None
                try:
                    general_result = build_general_metrics(store_id)
                    general_metrics = general_result.get("general_metrics")
                    print("[INFO] ✅ General Metrics 로드 성공")
                except Exception as e:
                    print(f"[WARN] General Metrics 로드 실패 (옵션): {e}")
                
                # 통합
                metrics = {
                    "main_metrics": main_metrics,
                    "상권_단위_정보": 상권_단위_정보,
                    "strategy_metrics": strategy_metrics,
                    "general_metrics": general_metrics
                }
                
            except Exception as e:
                print(f"[ERROR] Metrics 로드 실패: {e}")
                import traceback
                traceback.print_exc()
                metrics = None
        
        state["metrics"] = metrics
        
        # ═════════════════════════════════════════
        # 3. 프롬프트 생성
        # ═════════════════════════════════════════
        prompt = self._build_prompt(
            user_query=user_query,
            user_info=state.get("user_info"),
            metrics=metrics,
            web_snippets=web_snippets
        )
        
        # ═════════════════════════════════════════
        # 4. LLM 호출
        # ═════════════════════════════════════════
        try:
            response = self.llm.invoke(prompt).content
            
            # ✅ 웹 출처 추가
            if web_snippets:
                response = self._append_web_sources(response, web_snippets)
            
            state["final_response"] = response
            state["error"] = None
            state["need_clarify"] = False
            
        except Exception as e:
            state["error"] = f"LLM 호출 실패: {e}"
            state["final_response"] = "죄송합니다. 응답 생성 중 오류가 발생했습니다."
        
        return state
    
    def _build_prompt(
        self,
        user_query: str,
        user_info: Optional[Dict],
        metrics: Optional[Dict],
        web_snippets: list
    ) -> str:
        """프롬프트 생성"""
        
        system = """당신은 소상공인을 위한 **데이터 기반 마케팅 전략가**입니다.

### 핵심 원칙
1. **근거 기반**: 제공된 데이터나 웹 정보를 반드시 활용
2. **실행 가능성**: 추상적 조언 금지, 구체적 액션 제시
3. **맞춤형**: 상황에 맞는 전략 (일반론 금지)
4. **투명성**: 근거를 명확히 제시

### 금지 사항
- 과장/보장 표현 ("100% 성공", "확실한 효과" 등)
- 데이터 없는 추측
- 복사/붙여넣기식 일반론
"""
        
        # Metrics 있음
        if metrics:
            web_section = ""
            if web_snippets:
                web_section = f"\n### 웹 참고 정보\n{self._format_web_snippets(web_snippets)}\n"
            
            # ✅ Metrics 우선순위: main → 상권 → strategy → general
            metrics_section = ""
            
            # 1. Main Metrics (핵심)
            if metrics.get("main_metrics"):
                metrics_section += f"### 📊 주요 지표 (Main Metrics)\n{json.dumps(metrics['main_metrics'], ensure_ascii=False, indent=2)}\n\n"
            
            # 2. 상권 정보
            if metrics.get("상권_단위_정보"):
                metrics_section += f"### 🏪 상권 정보\n{json.dumps(metrics['상권_단위_정보'], ensure_ascii=False, indent=2)}\n\n"
            
            # 3. Strategy Metrics (전략 방향성)
            if metrics.get("strategy_metrics"):
                metrics_section += f"### 🎯 전략 지표 (Strategy Metrics)\n{json.dumps(metrics['strategy_metrics'], ensure_ascii=False, indent=2)}\n\n"
            
            # 4. General Metrics (보조 정보)
            if metrics.get("general_metrics"):
                metrics_section += f"### 📋 보조 정보 (참고용)\n{json.dumps(metrics['general_metrics'], ensure_ascii=False, indent=2)}\n"
            
            return f"""{system}

### 가게 정보
{json.dumps(user_info, ensure_ascii=False, indent=2)}

{metrics_section}
{web_section}
### 질문
{user_query}

### 답변 형식
1. **현재 상황 요약** (데이터 기반 2-3문장)
2. **핵심 데이터 분석** (근거 2-3개, 수치 포함)
3. **전략 제안** (실행 가능하고 구체적으로)
4. **기대 효과**
"""
        
        # Metrics 없음
        else:
            web_section = ""
            if web_snippets:
                web_section = f"\n### 웹 참고 정보\n{self._format_web_snippets(web_snippets)}\n"
            
            return f"""{system}
{web_section}
### 질문
{user_query}

### 답변 형식
1. **핵심 답변** (2-3문장)
2. **상세 설명** (근거/사례 포함)
3. **실전 조언** (구체적으로)
"""
    
    def _format_web_snippets(self, snippets: list) -> str:
        """웹 스니펫 포맷팅"""
        if not snippets:
            return "(없음)"
        
        lines = []
        for i, snip in enumerate(snippets[:5], 1):
            title = snip.get("title", "제목 없음")
            source = snip.get("source", "")
            snippet = snip.get("snippet", "")
            url = snip.get("url", "")
            
            lines.append(f"{i}. **{title}** ({source})")
            if snippet:
                lines.append(f"   └ {snippet[:150]}...")
            if url:
                lines.append(f"   └ {url}")
        
        return "\n".join(lines)
    
    def _append_web_sources(self, response: str, web_snippets: list) -> str:
        """✅ 웹 출처 추가 (토글 형식 + 요약)"""
        if not web_snippets:
            return response
        
        sources = []
        sources.append("\n\n---")
        sources.append("<details>")
        sources.append("<summary>🔗 <b>참고 출처</b> (클릭하여 펼치기)</summary>")
        sources.append("\n")
        
        for i, snip in enumerate(web_snippets[:5], 1):
            title = snip.get("title", "제목 없음")
            url = snip.get("url", "")
            source = snip.get("source", "출처 불명")
            snippet = snip.get("snippet", "")
            
            sources.append(f"**{i}. {title}**")
            if source:
                sources.append(f"  - 출처: {source}")
            if snippet:
                # 간단 요약 (첫 100자만)
                summary = snippet[:100] + ("..." if len(snippet) > 100 else "")
                sources.append(f"  - 요약: {summary}")
            if url:
                sources.append(f"  - 링크: {url}")
            sources.append("")  # 빈 줄
        
        sources.append("</details>")
        sources.append("---")
        
        return response + "\n".join(sources)


# ═════════════════════════════════════════
# CLI Test
# ═════════════════════════════════════════
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
        print("❗ 사용법: python -m my_agent.nodes.general --query '질문' [--store STORE_ID]")
        print("예시 1: python -m my_agent.nodes.general --query '최신 음식점 마케팅 트렌드 알려줘'")
        print("예시 2: python -m my_agent.nodes.general --query '본죽 매출 분석' --store 761947ABD9")
        sys.exit(1)

    state = {"user_query": query}
    if store_id:
        state["store_id"] = store_id

    node = GeneralNode()
    result = node(state)
    
    print("\n" + "="*60)
    print("✅ 실행 결과")
    print("="*60)
    print(json.dumps(result, ensure_ascii=False, indent=2))