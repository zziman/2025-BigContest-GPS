# my_agent/agent.py
# -*- coding: utf-8 -*-

from langgraph.graph import StateGraph, END

from my_agent.utils.state import GraphState
from my_agent.nodes.router import RouterNode
from my_agent.nodes.web_augment import WebAugmentNode
from my_agent.nodes.general import GeneralNode
from my_agent.nodes.issue import IssueNode
from my_agent.nodes.sns import SNSNode
from my_agent.nodes.revisit import RevisitNode
from my_agent.nodes.cooperation import CooperationNode
from my_agent.nodes.season import SeasonNode

from my_agent.nodes.relevance_check import check_relevance
from my_agent.utils.chat_history import update_conversation_memory
from my_agent.utils.config import DEFAULT_TOPK, DEFAULT_RECENCY_DAYS


def create_graph():
    workflow = StateGraph(GraphState)

    # ─── 노드 등록 ───
    workflow.add_node("router", RouterNode())
    workflow.add_node("web_augment", WebAugmentNode(default_topk=DEFAULT_TOPK))
    workflow.add_node("general", GeneralNode())
    workflow.add_node("issue", IssueNode())
    workflow.add_node("sns", SNSNode())
    workflow.add_node("revisit", RevisitNode())
    workflow.add_node("cooperation", CooperationNode())
    workflow.add_node("season", SeasonNode())

    workflow.add_node("relevance_checker", check_relevance)
    workflow.add_node("memory_updater", update_conversation_memory)

    # ─── 엔트리 포인트 ───
    workflow.set_entry_point("router")

    # ─── Router 이후 clarify 여부 ───
    def _after_router(state):
        if state.get("need_clarify"):
            print("[GRAPH] need_clarify=True 감지 → 즉시 종료")
            return "clarify"
        return "continue"

    workflow.add_conditional_edges(
        "router",
        _after_router,
        {"clarify": END, "continue": "web_augment"}
    )

    # ─── Intent 라우팅 ───
    def _route_intent(state):
        intent = (state.get("intent") or "GENERAL").upper()
        if intent in ["SNS", "REVISIT", "ISSUE", "GENERAL", "COOPERATION", "SEASON"]:
            return intent
        return "GENERAL"

    workflow.add_conditional_edges(
        "web_augment",
        _route_intent,
        {
            "GENERAL": "general",
            "ISSUE": "issue",
            "SNS": "sns",
            "REVISIT": "revisit",
            "COOPERATION": "cooperation",
            "SEASON": "season",
        },
    )

    # ─── 각 노드 → 릴리번스 체크 ───
    for node in ["general", "issue", "sns", "revisit", "cooperation", "season"]:
        workflow.add_edge(node, "relevance_checker")

    # ─── 릴리번스 결과 분기 ───
    def _after_relevance(state):
        if state.get("relevance_passed"):
            return "pass"
        print("[GRAPH] relevance_passed=False → web_augment로 재시도")
        return "retry"

    workflow.add_conditional_edges(
        "relevance_checker",
        _after_relevance,
        {
            "pass": "memory_updater",
            "retry": "web_augment",  # 실패 시 web_augment로 되돌리기
        },
    )

    # ─── 메모리 업데이트 후 종료 ───
    workflow.add_edge("memory_updater", END)

    return workflow.compile()
