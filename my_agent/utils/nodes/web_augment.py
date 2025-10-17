# -*- coding: utf-8 -*-
# web_augment.py

from typing import Dict, Any, List
from mcp.adapter_client import call_mcp_tool

class WebAugmentNode:
    def __init__(self, default_topk: int = 5, recency_days: int = 60, intents=("SNS","ISSUE")):
        self.default_topk = default_topk
        self.recency_days = recency_days
        self.intents = set(intents)

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        intent = state.get("intent", "GENERAL")
        use = (intent in self.intents) or state.get("need_web_fallback", False)
        if not use:
            return state

        card = state.get("store_card", {})
        q_parts = [
            card.get("mct_name"), card.get("industry_kor") or card.get("industry"),
            card.get("district"), "후기 OR 리뷰 OR 블로그 OR 기사"
        ]
        query = " ".join([p for p in q_parts if p]).strip() or state.get("user_query","")
        if not query:
            return state

        resp = call_mcp_tool(
            "web_search", query=query, provider="auto",
            top_k=self.default_topk, recency_days=self.recency_days
        )
        if not resp.get("success"):
            return state

        docs = resp.get("docs", [])
        state["web_snippets"] = [{
            "title": d.get("title",""),
            "source": d.get("source",""),
            "url": d.get("url",""),
            "snippet": d.get("snippet",""),
            "published_at": d.get("published_at","")
        } for d in docs]
        state["web_meta"] = {
            "provider_used": resp.get("provider_used",""),
            "count": resp.get("count",0),
            "query": query
        }
        return state
