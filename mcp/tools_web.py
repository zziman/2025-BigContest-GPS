# mcp/tools_web.py
# -*- coding: utf-8 -*-

import time, json, re
import urllib.parse as up
import requests
from typing import List, Dict, Any, Optional, Tuple

from .contracts import WebSearchOutput, WebDoc
from my_agent.utils.config import (
    SERPER_API_KEY,
    SEARCH_TIMEOUT,
    DEFAULT_TOPK,
    GOOGLE_API_KEY,
    LLM_MODEL,
    LLM_TEMPERATURE,
)

from langchain_google_genai import ChatGoogleGenerativeAI


# 공통 유틸
def _norm(text: Optional[str]) -> str:
    return (text or "").strip()

def _clip(s: str, n=300) -> str:
    s = re.sub(r"\s+", " ", s or "").strip()
    return s[:n]

def clean_raw_content(text: str) -> str:
    """HTML, URL, Markdown 등을 정리"""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"http[s]?://\S+", " ", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"[^0-9가-힣a-zA-Z.,!?()\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# 쿼리 재작성 (Gemini, optional)
def _rewrite_query_gemini(query: str) -> str:
    prompt = f"""
    당신은 소상공인·자영업자를 돕는 마케팅 전문 검색어 생성기입니다.
    아래 문장을 Google 웹 검색에 적합한 한국어 쿼리로 재작성하세요.
    (8~15 단어, 특수문자 금지, 한 줄만 출력)
    입력: {query}
    출력:
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


# Serper API 호출
def _serper_search(q: str, top_k: int = 10) -> Tuple[str, List[WebDoc]]:
    """Serper.dev (Google Search API) 호출"""
    if not SERPER_API_KEY:
        return "serper", []
    try:
        url = "https://google.serper.dev/search"
        headers = {
            "X-API-KEY": SERPER_API_KEY,
            "Content-Type": "application/json",
        }
        payload = {"q": q, "num": min(top_k, 20)}
        r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=SEARCH_TIMEOUT)
        r.raise_for_status()

        j = r.json() or {}
        results = j.get("organic", []) or []

        docs: List[WebDoc] = []
        for idx, it in enumerate(results[:top_k]):
            link = _norm(it.get("link") or it.get("url"))
            title = _clip(_norm(it.get("title")))
            snippet = _clip(_norm(it.get("snippet") or ""))
            docs.append({
                "title": title,
                "url": link,
                "snippet": snippet,
                "raw_content": clean_raw_content(snippet),
                "source": up.urlparse(link).netloc,
                "published_at": _norm(it.get("date") or ""),
            })
        return "serper", docs
    except Exception as e:
        print("[Serper 검색 실패]", e)
        return "serper", []


# 결과 정제
def _clean_results(docs: List[WebDoc]) -> List[WebDoc]:
    seen = set()
    out: List[WebDoc] = []
    for d in docs:
        url = d.get("url")
        if not url or url in seen:
            continue
        title = _clip(re.sub(r"<.*?>", "", d.get("title", "") or ""))
        snippet = _clip(re.sub(r"<.*?>", "", d.get("snippet", "") or ""))
        if len(title) < 3 or len(snippet) < 10:
            continue
        d["title"] = title
        d["snippet"] = snippet
        seen.add(url)
        out.append(d)
    return out


# 메인 함수
def web_search(query: str,
               top_k: int = DEFAULT_TOPK,
               rewrite_query: bool = True,
               debug: bool = False) -> WebSearchOutput:
    """
    Serper 기반 웹 검색 (Google)
    - rewrite_query=True  → Gemini로 재작성
    - rewrite_query=False → 쿼리에 ' 마케팅 전략' 자동 추가
    """
    t0 = time.time()
    provider = "serper"
    original_query = _norm(query)
    used_query = original_query

    if not original_query:
        return _build_output(False, provider, [], original_query, used_query, 0, False, t0)

    # 쿼리 재생성
    t_rewrite_start = time.time()
    if rewrite_query:
        used_query = _rewrite_query_gemini(original_query)
        if debug:
            print(f"[rewrite] '{original_query}' → '{used_query}'")
    else:
        used_query = original_query
    t_rewrite = time.time() - t_rewrite_start

    # Serper 검색
    t_search_start = time.time()
    _, docs = _serper_search(used_query, top_k)
    t_search = time.time() - t_search_start

    # 결과 정제
    t_clean_start = time.time()
    results = _clean_results(docs)
    t_clean = time.time() - t_clean_start

    total_time = time.time() - t0

    if debug:
        print("\n---- 실행 시간 요약")
        print(f"- 쿼리 변환: {t_rewrite:.3f}s")
        print(f"- Serper 검색: {t_search:.3f}s")
        print(f"- 결과 정제: {t_clean:.3f}s")
        print(f"- 총 실행 시간: {total_time:.3f}s\n")

    result = _build_output(True, provider, results, original_query, used_query, 0, False, t0)
    result["meta"].update({
        "rewrite_time": round(t_rewrite, 3),
        "search_time": round(t_search, 3),
        "clean_time": round(t_clean, 3),
    })
    return result


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
    print("[Serper] web_search 테스트")
    result = web_search("분식집 손님 줄었어", rewrite_query=False, debug=True)
    with open("websearch_result.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print("결과 저장 완료: websearch_result.json")
