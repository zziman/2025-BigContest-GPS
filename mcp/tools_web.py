# -*- coding: utf-8 -*-
# mcp/tools_web.py
import time, json, re
import urllib.parse as up
import requests
from typing import List, Dict, Any, Optional, Tuple
from .contracts import WebSearchInput, WebSearchOutput, WebDoc

# 🔧 프로젝트 설정: secrets.toml > .env > default (app/config.py에서 통일)
from my_agent.utils.config import (
    NAVER_CLIENT_ID, NAVER_CLIENT_SECRET,
    SURFER_API_KEY, TABILI_API_KEY,
    SEARCH_TIMEOUT, DEFAULT_TOPK, DEFAULT_RECENCY_DAYS
)

def _norm(text: Optional[str]) -> str:
    return (text or "").strip()

def _clip(s: str, n=300) -> str:
    s = re.sub(r"\s+", " ", s or "").strip()
    return s[:n]

def _to_ts(published_at: str) -> float:
    """
    다양한 형식(pubDate, ISO8601 등)을 best-effort로 epoch seconds로 변환
    """
    s = _norm(published_at)
    if not s:
        return 0.0
    # 1) 흔한 ISO8601: 2025-10-15T12:34:56
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return time.mktime(time.strptime(s[:19], fmt))
        except Exception:
            pass
    # 2) Naver pubDate: 'Wed, 16 Oct 2025 10:00:00 +0900'
    try:
        # %z는 +0900 파싱 지원 (Python 3.7+). time.mktime은 tz 미지원이라 변환 후 보정이 필요할 수 있으나
        # 여기선 신선도 필터 용도라 대략적 비교면 충분.
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(s)
        return dt.timestamp()
    except Exception:
        return 0.0

def _rank_blend(items: List[WebDoc]) -> List[WebDoc]:
    # 간단 블렌딩: score DESC → published_at DESC → title ASC
    return sorted(
        items,
        key=lambda x: (
            -float(x.get("score", 0) or 0),
            -_to_ts(x.get("published_at", "")),
            x.get("title", "") or ""
        )
    )

def _apply_recency_filter(items: List[WebDoc], recency_days: int) -> List[WebDoc]:
    if recency_days <= 0:
        return items
    cutoff = time.time() - recency_days * 86400
    out = []
    for d in items:
        ts = _to_ts(d.get("published_at", ""))
        if ts == 0.0 or ts >= cutoff:
            out.append(d)
    return out

# ───────────────────────────
# Providers
# ───────────────────────────
def _naver_search(q: str, top_k: int) -> Tuple[str, List[WebDoc]]:
    if not (NAVER_CLIENT_ID and NAVER_CLIENT_SECRET):
        return "naver", []
    url = "https://openapi.naver.com/v1/search/news.json"
    # 블로그: https://openapi.naver.com/v1/search/blog.json
    params = {"query": q, "display": min(top_k, 10), "start": 1, "sort": "date"}
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }
    r = requests.get(url, params=params, headers=headers, timeout=SEARCH_TIMEOUT)
    r.raise_for_status()
    data = r.json().get("items", []) or []
    docs: List[WebDoc] = []
    for it in data:
        title = _norm(re.sub("<.*?>", "", it.get("title", "")))
        link = _norm(it.get("link"))
        snippet = _clip(re.sub("<.*?>", "", it.get("description", "")))
        origin = it.get("originallink") or link or ""
        source = up.urlparse(origin).netloc or up.urlparse(link or "").netloc
        pub = _norm(it.get("pubDate", ""))  # RFC822
        docs.append({
            "title": title,
            "url": link,
            "snippet": snippet,
            "source": source,
            "published_at": pub,
            "score": 0.7,  # 베이스 가중치
        })
    return "naver", docs

def _serper_search(q: str, top_k: int) -> Tuple[str, List[WebDoc]]:
    # Serper (서퍼): https://google.serper.dev/search  (POST)
    if not SURFER_API_KEY:
        return "serper", []
    url = "https://google.serper.dev/search"
    headers = {"X-API-KEY": SURFER_API_KEY, "Content-Type": "application/json"}
    payload = {"q": q, "num": top_k}
    r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=SEARCH_TIMEOUT)
    r.raise_for_status()
    j = r.json() or {}
    data = (j.get("news") or []) + (j.get("organic") or [])
    docs: List[WebDoc] = []
    for it in data[:top_k]:
        title = _norm(it.get("title"))
        link = _norm(it.get("link") or it.get("url"))
        snippet = _clip(it.get("snippet") or it.get("description") or "")
        source = up.urlparse(link or "").netloc
        pub = _norm(it.get("date") or it.get("publishedDate") or it.get("dateUtc") or "")
        docs.append({
            "title": title,
            "url": link,
            "snippet": snippet,
            "source": source,
            "published_at": pub,
            "score": 0.9,
        })
    return "serper", docs

def _tavily_search(q: str, top_k: int) -> Tuple[str, List[WebDoc]]:
    # Tavily (타빌리): https://api.tavily.com/search  (POST, Bearer)
    if not TABILI_API_KEY:
        return "tavily", []
    url = "https://api.tavily.com/search"
    headers = {"Authorization": f"Bearer {TABILI_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "query": q,
        "max_results": top_k,
        "search_depth": "advanced",   # 필요 시 'basic'
        "include_answer": False,
        "include_raw_content": False,
    }
    r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=SEARCH_TIMEOUT)
    r.raise_for_status()
    j = r.json() or {}
    data = j.get("results", []) or []
    docs: List[WebDoc] = []
    for it in data[:top_k]:
        link = _norm(it.get("url"))
        docs.append({
            "title": _norm(it.get("title")),
            "url": link,
            "snippet": _clip(it.get("content") or it.get("snippet") or ""),
            "source": up.urlparse(link or "").netloc,
            "published_at": _norm(it.get("published_time") or it.get("date") or ""),
            "score": 0.8,
        })
    return "tavily", docs

# ───────────────────────────
# Public MCP tool
# ───────────────────────────
def web_search(query: str, provider: str = "auto",
               top_k: int = DEFAULT_TOPK,
               recency_days: int = DEFAULT_RECENCY_DAYS) -> WebSearchOutput:
    q = _norm(query)
    if not q:
        return {"success": False, "provider_used": provider, "count": 0, "docs": [], "error": "empty query"}

    providers = []
    if provider in ("auto", "naver"):  providers.append(_naver_search)
    if provider in ("auto", "serper", "surfer"): providers.append(_serper_search)  # 'surfer' 별칭 허용
    if provider in ("auto", "tavily", "tabili"): providers.append(_tavily_search)  # 'tabili' 오타 별칭 허용

    merged: List[WebDoc] = []
    used: List[str] = []

    for fn in providers:
        try:
            name, docs = fn(q, top_k)
            if docs:
                used.append(name)
                merged.extend(docs)
        except Exception:
            # 공급자 하나 실패해도 전체 실패로 만들지 않음
            continue

    if not merged:
        return {"success": False, "provider_used": ",".join(used) or provider, "count": 0, "docs": [], "error": "no results"}

    # 신선도 필터 → 랭킹 블렌딩 → 상위 K
    merged = _apply_recency_filter(merged, recency_days)
    merged = _rank_blend(merged)[:top_k]

    return {"success": True, "provider_used": ",".join(used) or provider, "count": len(merged), "docs": merged, "error": None}
