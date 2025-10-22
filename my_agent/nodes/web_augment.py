# my_agent/nodes/web_augment.py

# -*- coding: utf-8 -*-

from typing import Dict, Any, List
from mcp.adapter_client import call_mcp_tool

# Intent별 키워드 가중 검색
_INTENT_KEYWORDS = {
    "GENERAL": ["성공 사례", "마케팅 전략", "프로모션", "매출 향상"],
    "SNS": ["인스타그램 홍보", "SNS 마케팅", "리뷰 관리", "바이럴 사례"],
    "ISSUE": ["매출 하락 원인", "문제 분석", "고객 이탈", "시장 변화"],
    "REVISIT": ["재방문율 향상", "단골 고객 관리", "리텐션 전략", "고객 충성도"],
    "COOPERATION": ["상권 협업", "제휴 마케팅", "파트너 매장", "공동 프로모션", "상생"],
    "SEASON": ["계절별 소비 패턴", "날씨 영향 마케팅", "기상 데이터 기반 전략", "시즈널 마케팅"],
}

def _norm(x: Any) -> str:
    return (str(x) if x else "").strip()


def _build_query(state):
    intent = (state.get("intent") or "GENERAL").upper()
    user_q = str(state.get("user_query") or "").strip()
    user_info = state.get("user_info") or {}

    # store 정보가 있다면 검색 query에 반영
    base = " ".join([
        str(user_info.get("store_name") or "").strip(),
        str(user_info.get("marketing_area") or "").strip(),
    ]).strip()

    # intent 키워드들을 OR 그룹으로 묶기
    kw_group = " OR ".join(_INTENT_KEYWORDS.get(intent, []))
    query = f"{base} ({kw_group})".strip() if base else f"{user_q} ({kw_group})".strip()
    
    # 매장 정보 없으면 그냥 사용자 질문 사용
    return query or "소상공인 마케팅 전략"


class WebAugmentNode:
    """ 웹 검색 보강 노드 - GENERAL/SNS/ISSUE/REVISIT/COOPERATION/SEASON 자동 적용 """

    def __init__(self, default_topk=5, intents=("GENERAL", "SNS", "ISSUE", "REVISIT", "COOPERATION", "SEASON")): 
        self.default_topk = default_topk
        self.intents = set(intents)

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        intent = (state.get("intent") or "GENERAL").upper()

        # 실행 조건: 지정된 intent or fallback 요청
        if not (intent in self.intents or state.get("need_web_fallback", False)):
            print(f"[WebAugmentNode] Skipping - intent={intent} not in {self.intents}")
            return state

        query = _build_query(state)
        print(f"[WebAugmentNode] Searching with query: {query}")
        
        resp = call_mcp_tool(
            "web_search",
            query=query,
            top_k=self.default_topk,
            rewrite_query=False,  # 질의 재구성 자동 적용 X
            debug=False
        )

        # 실패 시 무시하고 진행
        if not resp or not resp.get("success"):
            print(f"[WebAugmentNode] Web search failed: {resp.get('error') if resp else 'No response'}")
            return state

        # 불필요한 필드 제거한 깨끗한 스니펫 구성 (title, url, snippet 만 사용)
        clean_snippets = []
        for d in resp.get("docs", []):
            title = _norm(d.get("title"))
            url = _norm(d.get("url"))
            snippet = _norm(d.get("snippet"))
            if title and url and snippet:
                clean_snippets.append({
                    "title": title,
                    "url": url,
                    "snippet": snippet[:250]  # 너무 길면 잘라줌
                })

        state["web_snippets"] = clean_snippets
        state["web_meta"] = {
            "provider_used": _norm(resp.get("provider_used")),
            "count": len(clean_snippets),
            "query": query
        }
        
        print(f"[WebAugmentNode] Found {len(clean_snippets)} web snippets")
        return state