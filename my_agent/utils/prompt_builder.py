# -*- coding: utf-8 -*-
"""
프롬프트 생성 유틸리티
"""
from typing import Dict, Any, List


def format_percentage(value: float, decimals: int = 0) -> str:
    """퍼센테이지 포맷팅"""
    return f"{value * 100:.{decimals}f}%"


def safe_float(value: Any, default: float = 0.0) -> float:
    """안전한 float 변환"""
    try:
        return float(value) if value is not None else default
    except (ValueError, TypeError):
        return default


def extract_top_demographics(card: Dict[str, Any]) -> List[tuple[str, float]]:
    """성별/연령대 비중 상위 3개 추출"""
    demo_keys = [
        ("남성_20대이하", "male_u20"),
        ("남성_30대", "male_30"),
        ("남성_40대", "male_40"),
        ("남성_50대", "male_50"),
        ("남성_60대이상", "male_60"),
        ("여성_20대이하", "female_u20"),
        ("여성_30대", "female_30"),
        ("여성_40대", "female_40"),
        ("여성_50대", "female_50"),
        ("여성_60대이상", "female_60"),
    ]
    demo_map = {}
    for label, key in demo_keys:
        val = card.get(key, 0) or 0
        demo_map[label] = safe_float(val)
    sorted_demo = sorted(demo_map.items(), key=lambda x: x[1], reverse=True)
    return sorted_demo[:3]


def build_base_context(card: Dict[str, Any]) -> str:
    """가맹점 기본 정보 컨텍스트"""
    name = card.get("mct_name", "해당 가맹점")
    industry = card.get("industry", "업종 미상")
    district = card.get("district", "")
    yyyymm = card.get("yyyymm", "")
    repeat_rate = format_percentage(card.get("repeat_rate", 0))
    delivery_share = format_percentage(card.get("delivery_share", 0))
    new_rate = format_percentage(card.get("new_rate", 0))
    top_demos = extract_top_demographics(card)
    demo_str = ", ".join([f"{label} {format_percentage(val)}" for label, val in top_demos])
    
    return f"""
[가맹점 기본 정보 - {yyyymm}]
- 상호명: {name}
- 업종: {industry}
- 지역: {district}
- 재방문율: {repeat_rate}
- 배달 비중: {delivery_share}
- 신규 고객 비중: {new_rate}
- 주요 고객층: {demo_str}
- 거주 고객: {format_percentage(card.get("residential_share", 0))}
- 유동 고객: {format_percentage(card.get("floating_share", 0))}
""".strip()


def build_signals_context(signals: List[str]) -> str:
    """이슈 시그널 컨텍스트"""
    if not signals:
        return ""
    desc = {
        "RETENTION_ALERT": "⚠️ 재방문율이 낮음 (20% 미만)",
        "CHANNEL_MIX_ALERT": "⚠️ 배달 의존도가 높음 (50% 이상)",
        "NEW_CUSTOMER_FOCUS": "✅ 신규 고객 유입이 활발함",
    }
    lines = [desc.get(s, s) for s in signals]
    return "\n[주요 이슈]\n" + "\n".join(lines)


def build_full_prompt(
    card: Dict[str, Any],
    user_query: str,
    signals: List[str],
    node_specific_instruction: str
) -> str:
    """전체 프롬프트 조합"""
    base = build_base_context(card)
    sig = build_signals_context(signals)
    
    return f"""
당신은 친절한 마케팅 상담사입니다.

{base}

{sig}

[사용자 질문]
{user_query}

[출력 지침]
{node_specific_instruction}

결과는 자연스러운 문장으로 작성하고, 근거는 위 데이터를 활용하세요.
""".strip()