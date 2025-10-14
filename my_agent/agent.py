# my_agent/agent.py
# -*- coding: utf-8 -*-
"""
그래프 조립: 노드 연결, 엣지, 체크포인트
"""
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from my_agent.utils.state import GraphState
from my_agent.utils.nodes.router import RouterNode  # 라우터만 클래스 유지
from my_agent.utils.tools import (
    resolve_store,               # 함수형 노드
    load_card_and_region_data,   # 함수형 노드
    build_features,              # 함수형 노드
    check_relevance,             # 함수형 노드
)
from my_agent.utils.nodes.sns import SNSNode
from my_agent.utils.nodes.revisit import RevisitNode
from my_agent.utils.nodes.issue import IssueNode
from my_agent.utils.nodes.general import GeneralNode


def create_graph():
    """
    전체 LangGraph 생성
    """
    workflow = StateGraph(GraphState)

    # ─── 노드 등록 ───
    workflow.add_node("router", RouterNode())
    workflow.add_node("store_resolver", resolve_store)                 # ← 함수 직접 등록
    workflow.add_node("data_collector", load_card_and_region_data)     # ← 함수 직접 등록
    workflow.add_node("feature_builder", build_features)               # ← 함수 직접 등록
    workflow.add_node("sns", SNSNode())
    workflow.add_node("revisit", RevisitNode())
    workflow.add_node("issue", IssueNode())
    workflow.add_node("general", GeneralNode())
    workflow.add_node("relevance_checker", check_relevance)            # ← 함수 직접 등록

    # ─── 엣지 ───
    workflow.set_entry_point("router")

    workflow.add_edge("router", "store_resolver")

    # store_resolver 분기: need_clarify면 종료
    workflow.add_conditional_edges(
        "store_resolver",
        lambda state: "clarify" if state.get("need_clarify") else "proceed",
        {
            "clarify": END,
            "proceed": "data_collector",
        },
    )

    workflow.add_edge("data_collector", "feature_builder")

    # feature_builder → intent별 노드 분기
    workflow.add_conditional_edges(
        "feature_builder",
        lambda state: state.get("intent", "GENERAL"),
        {
            "SNS": "sns",
            "REVISIT": "revisit",
            "ISSUE": "issue",
            "GENERAL": "general",
        },
    )

    # 각 노드 → relevance_checker
    for node in ["sns", "revisit", "issue", "general"]:
        workflow.add_edge(node, "relevance_checker")

    # relevance_checker 분기: 통과하면 종료, 실패하면 (현재는) 종료
    workflow.add_conditional_edges(
        "relevance_checker",
        lambda state: "pass" if state.get("relevance_passed") else "retry",
        {
            "pass": END,
            "retry": END,   # TODO: 실패 시 재생성 루프 추가 가능
        },
    )

    # ─── 체크포인트 (메모리) ───
    checkpointer = MemorySaver()

    return workflow.compile(checkpointer=checkpointer)
