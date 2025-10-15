# -*- coding: utf-8 -*-
"""
LangGraph 공용 상태 스키마
"""
from typing import TypedDict, Optional, List, Dict, Any, Annotated
from langgraph.graph import add_messages
from langchain_core.messages import BaseMessage


class GraphState(TypedDict):
    """
    전체 그래프 공용 상태
    """
    # ─── 입력 ───
    user_query: str
    store_name_input: Optional[str]
    
    # ─── 라우팅 ───
    intent: Optional[str]  # SNS, REVISIT, ISSUE, GENERAL
    
    # ─── 가맹점 확정 ───
    store_id: Optional[str]
    store_candidates: List[dict]  # 후보 리스트
    need_clarify: bool
    
    # ─── 데이터 ───
    card_data: Optional[Dict[str, Any]]
    area_data: Optional[Dict[str, Any]]
    region_data: Optional[Dict[str, Any]]

    # ★ 웹 보강 결과(새로 추가)
    web_snippets: Optional[List[Dict[str, Any]]]   # MCP web_search 결과 요약 리스트
    web_meta: Optional[Dict[str, Any]]             # provider_used, query, count 등

    # ─── 분석 결과 ───
    signals: List[str]  # RETENTION_ALERT, CHANNEL_MIX_ALERT 등
    persona: Optional[str]
    channel_hints: List[str]
    
    # ─── LLM 응답 ───
    raw_response: Optional[str]
    final_response: Optional[str]
    
    # ─── 액션 ───
    actions: List[Dict[str, Any]]
    
    # ─── 메모리 (멀티턴) ───
    messages: Annotated[List[BaseMessage], add_messages]
    conversation_summary: Optional[str]
    
    # ─── 제어 ───
    relevance_passed: bool
    retry_count: int
    error: Optional[str]

    # ★ 내부데이터 빈약 시 웹 보강 강제 플래그(새로 추가)
    need_web_fallback: Optional[bool]
