# my_agent/utils/postprocess.py

# -*- coding: utf-8 -*-
"""
응답 후처리: 정제, 배지 추가, 액션 생성
"""
import re
from typing import Dict, Any, List, Tuple, Optional
from urllib.parse import urlparse


def _safe_str(x) -> str:
    """안전한 문자열 변환"""
    return "" if x is None else str(x)


def _format_yyyymm(yyyymm: Any) -> Optional[str]:
    """YYYYMM → 'YYYY년 MM월' 포맷"""
    s = _safe_str(yyyymm)
    if len(s) >= 6 and s[:4].isdigit() and s[4:6].isdigit():
        return f"{s[:4]}년 {s[4:6]}월"
    return None


def _dedup_sources(snips: List[Dict[str, Any]], limit: int = 3) -> List[Dict[str, Any]]:
    """웹 스니펫 중복 제거 (URL/도메인 기준)"""
    seen = set()
    out = []
    for s in snips or []:
        title = _safe_str(s.get("title", "")).strip()
        url = _safe_str(s.get("url", "")).strip()
        dom = urlparse(url).netloc if url else _safe_str(s.get("source", "")).strip()
        key = (title.lower(), dom.lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
        if len(out) >= limit:
            break
    return out


def _build_sources_block(snips: List[Dict[str, Any]], meta: Optional[Dict[str, Any]]) -> str:
    """참고 출처 섹션 생성"""
    snips = _dedup_sources(snips, limit=3)
    if not snips:
        return ""
    lines = ["\n\n---\n🔗 참고 출처"]
    if meta:
        q = _safe_str(meta.get("query", ""))
        prov = _safe_str(meta.get("provider_used", ""))
        if q or prov:
            lines.append(f"*검색 정보: provider={prov or 'auto'}, query=\"{q}\"*")
    for s in snips:
        title = _safe_str(s.get("title", "(제목 없음)"))
        url = _safe_str(s.get("url", ""))
        src = _safe_str(s.get("source", urlparse(url).netloc if url else ""))
        date = _safe_str(s.get("published_at", ""))
        head = f"- {title} · {src}"
        if date:
            head += f" · {date}"
        if url:
            head += f" · {url}"
        lines.append(head)
        snip = _safe_str(s.get("snippet", "")).strip()
        if snip:
            snip = re.sub(r"\s+", " ", snip)[:220]
            lines.append(f"  └ {snip}")
    return "\n".join(lines)


def clean_response(response: str) -> str:
    """응답 텍스트 정제"""
    response = re.sub(r"\n{3,}", "\n\n", response or "")
    response = response.strip()
    response = re.sub(r"#{4,}", "###", response)
    return response


def add_proxy_badge(response: str, is_proxy: bool) -> str:
    """프록시 데이터 사용 배지"""
    if is_proxy:
        return "📊 [프록시 기반 추정]\n이 분석은 동일 업종/지역의 평균 데이터를 기반으로 추정되었습니다.\n\n" + response
    return response


def add_data_quality_badge(response: str, card: Dict[str, Any]) -> str:
    """데이터 기준 날짜 표시"""
    msg = _format_yyyymm(card.get("yyyymm", ""))
    if msg:
        response += f"\n\n📅 **기준 데이터**: {msg}"
    return response


def add_disclaimer(response: str, card: Dict[str, Any]) -> str:
    """면책 조항 추가"""
    disclaimer = """
---
💡 **안내사항**
- 본 분석은 신한카드 거래 데이터를 기반으로 한 통계적 추정입니다.
- 실제 실행 시 가맹점 상황에 맞게 조정이 필요합니다.
- 마케팅 효과는 실행 방법에 따라 달라질 수 있습니다.
"""
    return response + disclaimer


def generate_action_seed(
    card: Dict[str, Any],
    signals: List[str],
    intent: str
) -> List[Dict[str, Any]]:
    """액션 플랜 시드 생성"""
    def fmt_pct(x):
        try:
            return f"{float(x) * 100:.1f}%"
        except Exception:
            return _safe_str(x)
    
    actions: List[Dict[str, Any]] = []
    priority = 1
    
    if "RETENTION_ALERT" in signals:
        actions.append({
            "priority": priority,
            "category": "retention",
            "title": "재방문 고객 확보 프로그램",
            "description": "스탬프/쿠폰 프로그램 도입",
            "why": f"현재 재방문율 {fmt_pct(card.get('repeat_rate', 0))}로 업종 평균 대비 낮음",
            "expected_impact": "재방문율 5~10%p 향상",
            "difficulty": "중",
        })
        priority += 1
    
    if "CHANNEL_MIX_ALERT" in signals:
        actions.append({
            "priority": priority,
            "category": "channel",
            "title": "배달 의존도 감소 전략",
            "description": "매장 내 식사 프로모션 강화",
            "why": f"배달 비중 {fmt_pct(card.get('delivery_share', 0))}로 높아 수익성 저하",
            "expected_impact": "마진율 3~5%p 개선",
            "difficulty": "중",
        })
        priority += 1
    
    if not actions:
        actions.append({
            "priority": 1,
            "category": "general",
            "title": "종합 마케팅 진단",
            "description": "현황 분석 및 맞춤 전략 수립",
            "why": "체계적인 마케팅 전략 필요",
            "expected_impact": "매출 5~10% 향상",
            "difficulty": "중",
        })
    
    return actions[:5]


def postprocess_response(
    raw_response: str,
    card: Dict[str, Any],
    signals: List[str],
    intent: str = "GENERAL",
    web_snippets: Optional[List[Dict[str, Any]]] = None,
    web_meta: Optional[Dict[str, Any]] = None,
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    최종 응답 후처리
    
    Args:
        raw_response: 생성된 원본 응답
        card: 카드 데이터
        signals: 시그널 리스트
        intent: 의도
        web_snippets: 웹 검색 결과 (선택)
        web_meta: 웹 메타데이터 (선택)
    
    Returns:
        (최종_텍스트, 액션_리스트)
    """
    text = clean_response(raw_response)
    text = add_proxy_badge(text, card.get("proxy", False))
    text = add_data_quality_badge(text, card)
    
    # 웹 출처 추가
    if web_snippets:
        text += _build_sources_block(web_snippets, web_meta)
    
    # 디스클레이머는 항상 마지막
    text = add_disclaimer(text, card)
    
    # 액션 시드 생성
    actions = generate_action_seed(card, signals, intent)
    
    return text, actions