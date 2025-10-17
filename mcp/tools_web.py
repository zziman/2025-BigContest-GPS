# -*- coding: utf-8 -*-
# mcp/tools_web.py

import time, json, re
import urllib.parse as up
import requests
from typing import List, Dict, Any, Optional, Tuple

from .contracts import WebSearchOutput, WebDoc
from my_agent.utils.config import (
    TAVILY_API_KEY, SEARCH_TIMEOUT,
    DEFAULT_TOPK, DEFAULT_RECENCY_DAYS,
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
    import torch  # for GPU check
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

def _to_ts(published_at: str) -> float:
    s = _norm(published_at)
    if not s:
        return 0.0
    # ISO-like
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return time.mktime(time.strptime(s[:19], fmt))
        except Exception:
            pass
    # RFC822
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
        ts = _to_ts(d.get("published_at", ""))
        if ts == 0.0 or ts >= cutoff:  # unknown dates keep (best-effort)
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

#  Query Rewrite (Gemini) 
def _rewrite_query_gemini(query: str) -> str:
    prompt = f"""
            당신은 소상공인·자영업자를 돕는 마케팅 전문 검색어 생성기입니다.
            사용자가 질문한 내용을 바탕으로, 웹 검색 품질을 높일 수 있는 한국어 검색 쿼리를 재작성하세요.

            지침:
            - 마케팅/매출/고객/전략/사례/분석/상권/리뷰/홍보 같은 키워드를 포함하여 의도를 명확히 합니다.
            - 업종 및 지역 정보가 있으면 반영합니다.
            - 대상: 영세・중소 사업자
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

#  Provider: Tavily 
def _tavily_search(q: str, top_k: int, time_range: str = "month", include_raw_content: bool = True, include_answer: bool = True) -> Tuple[str, List[WebDoc]]:
    if not TABILI_API_KEY:
        return "tavily", []
    try:
        url = "https://api.tavily.com/search"
        headers = {"Authorization": f"Bearer {TABILI_API_KEY}", "Content-Type": "application/json"}
        payload = {
            "query": q,
            "max_results": top_k,
            "search_depth": "advanced",
            "include_raw_content": include_raw_content,
            "include_answer": include_answer,
            "time_range": time_range,  # "day" | "week" | "month" | "year"
        }
        r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=SEARCH_TIMEOUT)
        r.raise_for_status()
        j = r.json() or {}
        data = j.get("results", []) or []
        tavily_answer = _norm(j.get("answer") or "")

        docs: List[WebDoc] = []
        for it in data:
            link = _norm(it.get("url"))
            # 넓게 커버: published_at 필드 보강 (URL 추출은 이번에 제외)
            pub = _norm(
                it.get("published_time")
                or it.get("published_date")
                or it.get("date")
                or it.get("date_published")
                or it.get("pub_date")
                or it.get("publishedAt")
                or ""
            )
            docs.append({
                "title": _clip(_norm(it.get("title"))),
                "url": link,
                "snippet": _clip(_norm(it.get("content") or "")),
                "raw_content": clean_raw_content(_clip(_norm(it.get("raw_content") or it.get("content") or ""), 1200)),
                "source": up.urlparse(link).netloc,
                "published_at": pub,
                "answer": tavily_answer if tavily_answer else _norm(it.get("answer") or ""),
                "score": float(it.get("score", 0.0)) if isinstance(it.get("score", 0.0), (int, float)) else 0.8,
            })
        return "tavily", docs, (tavily_answer or None)
    except Exception:
        return "tavily", [], None

#  Cleaning 
def _clean_results(docs: List[WebDoc]) -> List[WebDoc]:
    seen = set()
    out: List[WebDoc] = []
    for d in docs:
        url = d.get("url")
        if not url or url in seen:
            continue
        title = _clip(re.sub(r"<.*?>", "", d.get("title", "") or ""))
        snippet = _clip(re.sub(r"<.*?>", "", d.get("snippet", "") or ""))
        if len(title) < 3 or len(snippet) < 15:
            continue
        d["title"] = title
        d["snippet"] = snippet
        seen.add(url)
        out.append(d)
    return out

def clean_raw_content(text: str) -> str:
    if not text:
        return ""
    # 1. HTML 태그 제거
    text = re.sub(r"<[^>]+>", " ", text)
    # 2. URL 제거
    text = re.sub(r"http[s]?://\S+", " ", text)
    # 3. Markdown/이미지 태그 제거
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)  # ![]( )
    text = re.sub(r"\[[^\]]*\]\([^)]*\)", " ", text)   # []( )
    # 4. 잡다한 특수문자/이모지 제거
    text = re.sub(r"[^0-9가-힣a-zA-Z.,!?()\s]", " ", text)
    # 5. 공백 정리
    text = re.sub(r"\s+", " ", text).strip()
    return text

#  Rerankers 
def _rerank_cosine(docs: List[WebDoc], query: str) -> List[WebDoc]:
    if not docs:
        return docs
    texts = [(d.get("title", "") + " " + d.get("snippet", "")).strip() for d in docs]
    try:
        vec = TfidfVectorizer().fit_transform([query] + texts)
        scores = cosine_similarity(vec[0:1], vec[1:]).flatten()
        ranked = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)
        return [d for d, _ in ranked]
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
        # GPU 없으면 cosine rerank 사용
        print('[디버깅] _rerank_sbert 안됨')
        return _rerank_cosine(docs, query)
    try:
        _ensure_sbert()
        texts = [(d.get("title", "") + " " + d.get("snippet", "")).strip() for d in docs]
        emb_q = _SBERT_MODEL.encode([query], convert_to_tensor=True, normalize_embeddings=True)
        emb_d = _SBERT_MODEL.encode(texts, convert_to_tensor=True, normalize_embeddings=True)
        scores = (emb_q @ emb_d.T).squeeze(0).tolist()
        ranked = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)
        return [d for d, _ in ranked]
    except Exception:
        print('[디버깅] _rerank_sbert 안됨')
        return _rerank_cosine(docs, query)

def _rerank_cross(docs: List[WebDoc], query: str) -> List[WebDoc]:
    if not docs:
        return docs
    if not (_HAS_SENTENCE_TRANSFORMERS and _has_gpu()):
        # GPU 없으면 cosine rerank 사용
        print('[디버깅] _rerank_cross 안됨')
        return _rerank_cosine(docs, query)
    try:
        _ensure_cross()
        pairs = [(query, (d.get("title", "") + " " + d.get("snippet", "")).strip()) for d in docs]
        scores = _CROSS_MODEL.predict(pairs).tolist()
        ranked = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)
        return [d for d, _ in ranked]
    except Exception:
        print('[디버깅] _rerank_cross 안됨')
        return _rerank_cosine(docs, query)

def _apply_rerank(docs: List[WebDoc], query: str, rerank: str) -> List[WebDoc]:
    # CPU-only 환경에서는 무조건 cosine
    if rerank in ("sbert", "cross") and not _has_gpu():
        rerank = "cosine"
    if rerank == "sbert":
        return _rerank_sbert(docs, query)
    if rerank == "cross":
        return _rerank_cross(docs, query)
    return _rerank_cosine(docs, query)

def _sort_by_recency_then_score(docs: List[WebDoc]) -> List[WebDoc]:
    # rank_score(유사도) 우선, 같은 급에서는 최신순
    def key(d):
        return (-float(d.get("rank_score", 0.0)), -_to_ts(d.get("published_at", "")))
    return sorted(docs, key=key)

#  Public API 
def web_search(query: str,
               top_k: int = DEFAULT_TOPK,
               recency_days: int = DEFAULT_RECENCY_DAYS,
               deep_search: bool = True,
               rewrite_query: bool = True,
               rerank: str = "cosine",
               debug: bool = False) -> WebSearchOutput:

    t0 = time.time()
    provider = "tavily"
    original_query = _norm(query)
    used_query = original_query
    retry_count = 0
    fallback_used = False

    if not original_query:
        return _build_output(False, provider, [], original_query, used_query, retry_count, fallback_used, t0)

    # 쿼리 재작성
    if rewrite_query:
        used_query = _rewrite_query_gemini(original_query)
        if debug:
            print(f"[rewrite] '{original_query}' -> '{used_query}'")

    # Search
    # 1차: month
    _, r_month, tavily_answer = _tavily_search(used_query, top_k, time_range="month", include_raw_content=True, include_answer=True)
    # 부족하면 2차: year (month 유지 + year로 보충)
    r_combined = r_month[:]
    if len(r_month) <= 5:
        retry_count += 1
        fallback_used = True
        _, r_year, tavily_answer_y = _tavily_search(used_query, max(top_k, 10), time_range="year", include_raw_content=True, include_answer=True)
        if not tavily_answer and tavily_answer_y:
            tavily_answer = tavily_answer_y
        r_combined = _merge_unique(r_month, r_year)

    # Cleaning + Recency filter
    results = _clean_results(r_combined)
    results = _apply_recency_filter(results, recency_days)

    # Rerank
    results = _apply_rerank(results, used_query, rerank)[:top_k]
    results = _sort_by_recency_then_score(results)[:top_k]

    return _build_output(True, provider, results, original_query, used_query, retry_count, fallback_used, t0)

#  Output Builder 
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

#  Local Test 
if __name__ == "__main__":
    # 다양한 모드 테스트
    print("[cosine] web_search(분식집 손님 줄었어, rerank=cosine")
    result = web_search("분식집 손님 줄었어", rerank="cosine", debug=True)
    # print("[sbert ]", web_search("치킨집 매출 하락 원인", rerank="sbert", debug=True))
    # print("[cross ]", web_se로arch("카페 상권 분석 마케팅 전략", rerank="cross", debug=True))
    with open("websearch_result.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)