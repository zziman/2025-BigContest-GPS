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
from my_agent.utils.nodes.web_augment import WebAugmentNode

def create_graph():
    workflow = StateGraph(GraphState)

    # ─── 노드 등록 ───
    workflow.add_node("router", RouterNode())
    workflow.add_node("store_resolver", resolve_store)
    workflow.add_node("data_collector", load_card_and_region_data)
    workflow.add_node("feature_builder", build_features)

    # ★ 웹 보강 노드 (MCP web_search 호출 담당)
    workflow.add_node("web_augment", WebAugmentNode(default_topk=5, recency_days=60))

    # 생성 노드
    workflow.add_node("sns", SNSNode())
    workflow.add_node("revisit", RevisitNode())
    workflow.add_node("issue", IssueNode())
    workflow.add_node("general", GeneralNode())

    workflow.add_node("relevance_checker", check_relevance)

    # ─── 엣지 ───
    workflow.set_entry_point("router")
    workflow.add_edge("router", "store_resolver")

    # store_resolver → clarify/proceed
    workflow.add_conditional_edges(
        "store_resolver",
        lambda state: "clarify" if state.get("need_clarify") else "proceed",
        {"clarify": END, "proceed": "data_collector"},
    )

    workflow.add_edge("data_collector", "feature_builder")

    # ✅ 변경 포인트 1: feature_builder 다음에 web_augment를 거친다
    workflow.add_edge("feature_builder", "web_augment")

    # ✅ 변경 포인트 2: 의도별 분기는 web_augment에서 수행
    def _route_after_web(state):
        # RouterNode가 넣어준 intent 값 사용, 기본값 GENERAL
        return (state.get("intent") or "GENERAL").upper()

    workflow.add_conditional_edges(
        "web_augment",
        _route_after_web,
        {
            "SNS": "sns",
            "REVISIT": "revisit",
            "ISSUE": "issue",
            "GENERAL": "general",
        },
    )

    # 생성 노드 → relevance_checker
    for node in ["sns", "revisit", "issue", "general"]:
        workflow.add_edge(node, "relevance_checker")

    # relevance_checker → 종료(또는 재시도 훅)
    workflow.add_conditional_edges(
        "relevance_checker",
        lambda state: "pass" if state.get("relevance_passed") else "retry",
        {"pass": END, "retry": END},
    )

    checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)