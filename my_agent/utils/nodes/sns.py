# -*- coding: utf-8 -*-
"""
SNS 추천 노드
"""
from langchain_google_genai import ChatGoogleGenerativeAI
from my_agent.utils.config import GOOGLE_API_KEY, LLM_MODEL, LLM_TEMPERATURE
from my_agent.utils.state import GraphState
from my_agent.utils.prompt_builder import build_base_context, build_signals_context
from my_agent.utils.postprocess import postprocess_response

def build_web_context(state: GraphState, limit: int = 3) -> str:
    snips = state.get("web_snippets") or []
    rows = []
    for s in snips[:limit]:
        title = s.get("title", "")
        src   = s.get("source", "")
        sn    = s.get("snippet", "")
        rows.append(f"- {title} · {src}: {sn}")
    return "\n".join(rows) if rows else "N/A"

def append_sources(text: str, state: GraphState, limit: int = 3) -> str:
    snips = state.get("web_snippets") or []
    if not snips:
        return text
    lines = ["\n\n---\n🔗 참고 출처"]
    for s in snips[:limit]:
        title = s.get("title", "(제목 없음)")
        src   = s.get("source", "")
        url   = s.get("url", "")
        if url:
            lines.append(f"- {title} · {src} · {url}")
        else:
            lines.append(f"- {title} · {src}")
    return text + "\n".join(lines)

PROMPT = """당신은 SNS 마케팅 전문가입니다.

아래 가맹점 데이터를 기반으로 SNS 채널 추천 및 콘텐츠 전략을 작성하세요.

[INTERNAL DATA]
{base_context}
{signals_context}

[EXTERNAL (최근 리뷰/기사/블로그 스니펫 요약)]
{web_context}

[주요 고객층]
{persona}

[추천 채널]
{channel_hints}

[출력 형식]
1) 추천 SNS 채널 (2~3개, 각 채널별 이유)
2) 타겟별 콘텐츠 아이디어 (3~5개)
3) 홍보 메시지 예시 (3개)

주의:
- 내부 데이터와 외부 스니펫 중 어떤 근거를 썼는지 문장 끝에 (내부) / (외부)로 표기
- 과장 없이 실행 가능한 수준으로만 작성
"""

class SNSNode:
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model=LLM_MODEL,
            google_api_key=GOOGLE_API_KEY,
            temperature=LLM_TEMPERATURE
        ) if GOOGLE_API_KEY else None
        self.prompt_template = PROMPT
    
    def __call__(self, state: GraphState) -> GraphState:
        card = state.get("card_data", {})
        signals = state.get("signals", [])
        persona = state.get("persona", "")
        channel_hints = state.get("channel_hints", [])

        base_ctx = build_base_context(card)
        sig_ctx  = build_signals_context(signals)
        web_ctx  = build_web_context(state)

        prompt = self.prompt_template.format(
            base_context=base_ctx,
            signals_context=sig_ctx,
            web_context=web_ctx,
            persona=persona,
            channel_hints=", ".join(channel_hints) if channel_hints else "데이터 기반 추천"
        )
        
        if self.llm:
            try:
                response = self.llm.invoke(prompt)
                raw = response.content
            except Exception as e:
                raw = f"LLM 호출 실패: {e}"
        else:
            raw = "(데모) SNS 마케팅 전략 생성 중..."
        
        state["raw_response"] = raw

        final, actions = postprocess_response(
            raw, card, signals, intent=state.get("intent","GENERAL"),
            web_snippets=state.get("web_snippets"), web_meta=state.get("web_meta")
        )
        final = append_sources(final, state)  # 참고 출처 추가
        state["final_response"] = final
        state["actions"] = actions
        return state
