# my_agent/nodes/web_augment.py

# -*- coding: utf-8 -*-

from typing import Dict, Any, List
from mcp.adapter_client import call_mcp_tool

# Intent별 키워드 가중 검색
_INTENT_KEYWORDS = {
    "GENERAL": ["사례", "성공", "전략", "트렌드", "노하우"],
    "SNS": ["SNS", "리뷰", "인스타그램", "홍보", "바이럴"],
    "ISSUE": ["원인", "하락", "문제", "진단", "분석"],
    "REVISIT": ["재방문", "단골", "리텐션", "충성도", "재구매"],  # ✅ REVISIT 추가
}

def _norm(x: Any) -> str:
    return (str(x) if x else "").strip()


def _build_query(state: Dict[str, Any]) -> str:
    intent = (state.get("intent") or "GENERAL").upper()
    user_q = _norm(state.get("user_query"))
    user_info = state.get("user_info") or {}

    # store 정보가 있다면 검색 query에 반영
    query_parts = [
        _norm(user_info.get("store_name")),
        _norm(user_info.get("industry")),
        _norm(user_info.get("marketing_area")),
        " ".join(_INTENT_KEYWORDS.get(intent, [])),
    ]

    query = " ".join([p for p in query_parts if p]).strip()

    # 매장 정보 없으면 그냥 사용자 질문 사용
    return query if query else user_q or "소상공인 마케팅 전략 사례"


class WebAugmentNode:
    """ 웹 검색 보강 노드 - GENERAL/SNS/ISSUE/REVISIT 자동 적용 """

    def __init__(self, default_topk=5, intents=("GENERAL", "SNS", "ISSUE", "REVISIT")):  # ✅ REVISIT 추가
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
        
        print(f"[WebAugmentNode] ✅ Found {len(clean_snippets)} web snippets")
        return state
