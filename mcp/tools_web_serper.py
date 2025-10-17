# -*- coding: utf-8 -*-
# mcp/tools_web.py

import time, json, re
import urllib.parse as up
import requests
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta

from .contracts import WebSearchOutput, WebDoc
from my_agent.utils.config import (
    SERPER_API_KEY, 
    SEARCH_TIMEOUT,
    DEFAULT_TOPK, DEFAULT_RECENCY_DAYS,
    # GOOGLE_API_KEY, LLM_MODEL, LLM_TEMPERATURE  # 이건 query rewrite 용도로 남기거나 제거 가능
    GOOGLE_API_KEY, LLM_MODEL, LLM_TEMPERATURE,
)

# LLM
from langchain_google_genai import ChatGoogleGenerativeAI

# Cosine rerank
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Optional (SBERT / CrossEncoder)
_HAS_SENTENCE_TRANSFORMERS = False
try:
    import torch
    from sentence_transformers import SentenceTransformer, CrossEncoder
    _HAS_SENTENCE_TRANSFORMERS = True
except Exception:
    _HAS_SENTENCE_TRANSFORMERS = False
    torch = None  

# Utils
def _norm(text: Optional[str]) -> str:
    return (text or "").strip()

def _clip(s: str, n=300) -> str:
    s = re.sub(r"\s+", " ", s or "").strip()
    return s[:n]

def _to_ts(date: str) -> float:
    s = _norm(date)
    if not s:
        return 0.0
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return time.mktime(time.strptime(s[:19], fmt))
        except Exception:
            pass
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(s).timestamp()
    except Exception:
        return 0.0

def _apply_recency_filter(items: List[WebDoc], recency_days: int) -> List[WebDoc]:
    if recency_days <= 0:
        return items
    cutoff = time.time() - recency_days * 86400
    out: List[WebDoc] = []
    for d in items:
        ts = _to_ts(d.get("date", ""))
        if ts == 0.0 or ts >= cutoff:
            out.append(d)
    return out

def _merge_unique(docs1: List[WebDoc], docs2: List[WebDoc]) -> List[WebDoc]:
    seen = set()
    merged: List[WebDoc] = []
    for d in docs1 + docs2:
        url = d.get("url", "")
        if not url or url in seen:
            continue
        seen.add(url)
        merged.append(d)
    return merged

def _add_date_filter(query: str, days: int = 90) -> str:
    """
    날짜 필터 추가 (ex: after:2024-10-01)
    """
    if "after:" in query:
        return query
    cutoff = datetime.now() - timedelta(days=days)
    cutoff_str = cutoff.strftime("%Y-%m-%d")
    return f"{query} after:{cutoff_str}"

# Query Rewrite (기존처럼 유지)
def _rewrite_query_gemini(query: str) -> str:
    prompt = f"""
            당신은 소상공인·자영업자를 돕는 마케팅 전문 검색어 생성기입니다.
            사용자가 질문한 내용을 바탕으로, 웹 검색 품질을 높일 수 있는 한국어 검색 쿼리를 재작성하세요.

            지침:
            - 마케팅/매출/고객/전략/사례/분석/상권/리뷰/홍보 같은 키워드를 포함하여 의도를 명확히 합니다.
            - 업종 및 지역 정보가 있으면 반영합니다.
            - 대상: 영세·중소 사업자
            - 핵심 키워드 중심
            - OR, 따옴표 등 특수 기호 사용 금지.
            - 한국어로만, 8~15 단어, 한 줄만 출력. 추가 설명 금지.

            입력:
            {query}

            출력(검색용 재작성 쿼리 한 줄):
                """.strip()
    try:
        llm = ChatGoogleGenerativeAI(
            model=LLM_MODEL,
            google_api_key=GOOGLE_API_KEY,
            temperature=LLM_TEMPERATURE,
        )
        resp = llm.invoke(prompt)
        return _norm(resp.content)
    except Exception:
        return query

# Serper 기반 웹 검색 함수
def _serper_search(q: str, top_k: int) -> Tuple[str, List[WebDoc]]:
    """
    Serper API를 호출해서 Google의 organic 결과를 가져오는 함수
    """
    if not SERPER_API_KEY:
        return "serper", []
    try:
        url = "https://google.serper.dev/search"
        headers = {
            "X-API-KEY": SERPER_API_KEY,
            "Content-Type": "application/json",
        }
        payload = {
            "q": q,
            "num": top_k,
            # 추가 옵션 필요하면 넣기 (예: hl, gl 등)
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=SEARCH_TIMEOUT)
        resp.raise_for_status()
        j = resp.json() or {}
        organic = j.get("organic", [])  # 리스트
        docs: List[WebDoc] = []
        for it in organic:
            link = _norm(it.get("link"))
            title = _clip(_norm(it.get("title") or ""))
            snippet = _clip(_norm(it.get("snippet") or ""))
            # Serper은 published date 제공 안 할 수 있음 → 빈 문자열 또는 it.get("published")
            pub = _norm(it.get("date") or it.get("published_date") or "")
            docs.append({
                "title": title,
                "url": link,
                "snippet": snippet,
                "raw_content": snippet,  # raw_content은 snippet 위주로 채움
                "source": up.urlparse(link).netloc,
                "date": pub,
                "score": float(it.get("position") or 0.0),  # 순서 기반 점수로 대체 가능
            })
        return "serper", docs
    except Exception as e:
        # 실패 시 빈 리스트 반환
        return "serper", []

# Cleaning 
def _clean_results(docs: List[WebDoc]) -> List[WebDoc]:
    seen = set()
    out: List[WebDoc] = []
    for d in docs:
        url = d.get("url")
        if not url or url in seen:
            continue
        title = _clip(re.sub(r"<.*?>", "", d.get("title", "") or ""))
        snippet = _clip(re.sub(r"<.*?>", "", d.get("snippet", "") or ""))
        if len(title) < 3 or len(snippet) < 5:
            continue
        d["title"] = title
        d["snippet"] = snippet
        seen.add(url)
        out.append(d)
    return out

# Rerankers
def _rerank_cosine(docs: List[WebDoc], query: str) -> List[WebDoc]:
    if not docs:
        return docs
    texts = [(d.get("title", "") + " " + d.get("snippet", "")).strip() for d in docs]
    try:
        vec = TfidfVectorizer().fit_transform([query] + texts)
        scores = cosine_similarity(vec[0:1], vec[1:]).flatten()
        for d, s in zip(docs, scores):
            d["score"] = float(s)
        return sorted(docs, key=lambda d: d["score"], reverse=True)
    except Exception:
        return docs

_SBERT_MODEL = None
_CROSS_MODEL = None

def _has_gpu() -> bool:
    try:
        return bool(torch is not None and torch.cuda.is_available())
    except Exception:
        return False

def _ensure_sbert():
    global _SBERT_MODEL
    if _SBERT_MODEL is None:
        _SBERT_MODEL = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

def _ensure_cross():
    global _CROSS_MODEL
    if _CROSS_MODEL is None:
        _CROSS_MODEL = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

def _rerank_sbert(docs: List[WebDoc], query: str) -> List[WebDoc]:
    if not docs:
        return docs
    if not (_HAS_SENTENCE_TRANSFORMERS and _has_gpu()):
        return _rerank_cosine(docs, query)
    try:
        _ensure_sbert()
        texts = [(d.get("title", "") + " " + d.get("snippet", "")).strip() for d in docs]
        emb_q = _SBERT_MODEL.encode([query], convert_to_tensor=True, normalize_embeddings=True)
        emb_d = _SBERT_MODEL.encode(texts, convert_to_tensor=True, normalize_embeddings=True)
        scores = (emb_q @ emb_d.T).squeeze(0).tolist()
        for d, s in zip(docs, scores):
            d["score"] = float(s)
        return sorted(docs, key=lambda d: d["score"], reverse=True)
    except Exception:
        return _rerank_cosine(docs, query)

def _rerank_cross(docs: List[WebDoc], query: str) -> List[WebDoc]:
    if not docs:
        return docs
    if not (_HAS_SENTENCE_TRANSFORMERS and _has_gpu()):
        return _rerank_cosine(docs, query)
    try:
        _ensure_cross()
        pairs = [(query, (d.get("title", "") + " " + d.get("snippet", "")).strip()) for d in docs]
        scores = _CROSS_MODEL.predict(pairs).tolist()
        for d, s in zip(docs, scores):
            d["score"] = float(s)
        return sorted(docs, key=lambda d: d["score"], reverse=True)
    except Exception:
        return _rerank_cosine(docs, query)

def _apply_rerank(docs: List[WebDoc], query: str, rerank: str) -> List[WebDoc]:
    if rerank in ("sbert", "cross") and not _has_gpu():
        rerank = "cosine"
    if rerank == "sbert":
        return _rerank_sbert(docs, query)
    if rerank == "cross":
        return _rerank_cross(docs, query)
    return _rerank_cosine(docs, query)

def _sort_by_recency_then_score(docs: List[WebDoc]) -> List[WebDoc]:
    def key(d):
        return (-float(d.get("score", 0.0)), -_to_ts(d.get("date", "")))
    return sorted(docs, key=key)

# Public API 
def web_search(query: str,
               top_k: int = DEFAULT_TOPK,
               recency_days: int = DEFAULT_RECENCY_DAYS,
               deep_search: bool = True,
               rewrite_query: bool = True,
               rerank: str = "cosine",
               debug: bool = False) -> WebSearchOutput:

    t0 = time.time()
    provider = "serper"
    original_query = _norm(query)
    used_query = original_query
    retry_count = 0
    fallback_used = False

    if not original_query:
        return _build_output(False, provider, [], original_query, used_query, retry_count, fallback_used, t0)

    if rewrite_query:
        used_query = _rewrite_query_gemini(original_query)
        if debug:
            print(f"[rewrite] '{original_query}' -> '{used_query}'")

    used_query = _add_date_filter(used_query, recency_days)
    # 1차 검색
    _, docs = _serper_search(used_query, top_k)

    # 결과 부족
    if deep_search and len(docs) < top_k:
        retry_count += 1
        fallback_used = True
        # 쿼리 재작성 후 다시 검색
        fallback_query = _rewrite_query_gemini(original_query + " 매출 회복 사례 고객 유입 전략 소상공인")
        fallback_query = _add_date_filter(fallback_query, recency_days + 180)
        _, docs2 = _serper_search(fallback_query, top_k)
        docs = _merge_unique(docs, docs2)

    results = _clean_results(docs)
    results = _apply_recency_filter(results, recency_days)
    results = _apply_rerank(results, used_query, rerank)[:top_k]
    results = _sort_by_recency_then_score(results)[:top_k]

    return _build_output(True, provider, results, original_query, used_query, retry_count, fallback_used, t0)

# Output Builder
def _build_output(success, provider_used, docs, raw_query, query_used, retry_count, fallback_used, t0):
    return {
        "success": success,
        "provider_used": provider_used,
        "count": len(docs),
        "docs": docs,
        "query": raw_query,
        "query_used": query_used,
        "meta": {
            "retry_count": retry_count,
            "fallback_used": bool(fallback_used),
            "execution_time": round(time.time() - t0, 3),
        },
    }

# Local Test
if __name__ == "__main__":
    print("[cosine] web_search(분식집 손님 줄었어, rerank=cosine")
    result = web_search("분식집 손님 줄었어", rerank="cosine", debug=True)
    with open("websearch_result.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
