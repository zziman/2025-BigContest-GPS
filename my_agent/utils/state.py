# my_agent/utils/state.py

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
    user_query: str  # 사용자 질문(문장 전체)
    
    # ─── 라우팅 ───
    intent: Optional[str]  # SNS, REVISIT, ISSUE, GENERAL
    
    # ─── 가맹점 확정 ───
    store_id: Optional[str]  # resolve_store 결과
    store_candidates: List[dict]  # 후보 리스트 -> 후보가 다수일 때(선택)
    need_clarify: bool  # 후보 확인 등 추가 질의 필요 여부
    # user_info (resolve_store가 채움)
    user_info: Optional[Dict[str, Any]]
    
    # ─── 데이터 ───
    store_data: Optional[Dict[str, Any]]      # 가맹점 데이터
    bizarea_data: Optional[Dict[str, Any]]    # 상권 데이터

    # ─── 웹 검색 데이터 ─── 
    web_snippets: Optional[List[Dict[str, Any]]]  # title/url/snippet 리스트
    web_meta: Optional[Dict[str, Any]]  # provider/count/query 등

    # ─── 분석 결과 ───
    metrics: Optional[Dict[str, Any]]       # 각 노드 목적에 맞는 메트릭 묶음
    raw_response: Optional[str]             # LLM 원문(선택)
    final_response: Optional[str]           # 사용자에게 보여줄 응답
    
    # ─── 액션(선택) ───
    actions: Optional[List[Dict[str, Any]]] # 후처리/노드가 필요 시 채움
    
    # ─── 멀티턴 메모리 ───
    messages: Annotated[List[BaseMessage], add_messages]
    conversation_summary: Optional[str]
    
    # ─── 제어 ───
    relevance_passed: bool
    retry_count: int
    error: Optional[str]

    # ─── 내부 데이터 부족 시 웹 보강 트리거 ─── 
    need_web_fallback: Optional[bool]
