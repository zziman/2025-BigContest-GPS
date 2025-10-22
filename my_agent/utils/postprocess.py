# my_agent/utils/postprocess.py

# -*- coding: utf-8 -*-
"""
응답 후처리: 정제, 배지 추가, 액션 생성
"""
import re
from typing import Dict, Any, List, Tuple, Optional
from urllib.parse import urlparse

def _safe_str(x) -> str:
    return "" if x is None else str(x)


def add_store_hint(response: str) -> str:
    """가맹점명 안내 문구 추가"""
    hint = "가맹점명을 입력하신다면 더 정확한 정보를 제공해드릴 수 있습니다."
    return response + f"\n\n💡 {hint}"


def format_web_snippets(snippets: List[Dict]) -> str:
    """웹 스니펫을 깔끔하게 문자열로 변환 """
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


def append_web_sources(response: str, snippets: List[Dict]) -> str:
    """웹 출처 블록을 토글 형식으로 붙이기"""
    if not snippets:
        return response

    sources = []
    sources.append("\n\n---")
    sources.append("<details>")
    sources.append("<summary>🔗 <b>참고 출처</b> (클릭하여 펼치기)</summary>\n")
    
    for i, snip in enumerate(snippets[:5], 1):
        title = snip.get("title", "제목 없음")
        url = snip.get("url", "")
        source = snip.get("source", "출처 불명")
        snippet = snip.get("snippet", "")
        
        sources.append(f"**{i}. {title}**")
        if snippet:
            summary = snippet[:100] + ("..." if len(snippet) > 100 else "")
            sources.append(f"  - 요약: {summary}")
        if url:
            sources.append(f"  - 링크: {url}")
        sources.append("")  # 빈 줄
    
    sources.append("</details>")
    sources.append("---")
    
    return response + "\n".join(sources)

def postprocess_response(
    raw_response: str,
    web_snippets: Optional[List[Dict]] = None
) -> str:
    """
    최종 응답 후처리
    - 텍스트 정제
    - 웹 출처 추가
    """
    if not raw_response:
        return ""

    # ✅ 1️⃣ 텍스트 정제
    text = re.sub(r"\n{3,}", "\n\n", raw_response)
    text = re.sub(r"#{4,}", "###", text)
    text = re.sub(r"[•●▪◆▶]", "", text)
    text = text.strip()

    # ✅ 5️⃣ 웹 출처 추가
    if web_snippets:
        text = append_web_sources(text, web_snippets)

    return text







