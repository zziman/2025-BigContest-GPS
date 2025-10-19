# my_agent/agent.py
# -*- coding: utf-8 -*-

from langgraph.graph import StateGraph, END

from my_agent.utils.state import GraphState
from my_agent.nodes.router import RouterNode
from my_agent.nodes.web_augment import WebAugmentNode
from my_agent.nodes.general import GeneralNode
# 앞으로 구현 예정
from my_agent.nodes.issue import IssueNode
from my_agent.nodes.sns import SNSNode
from my_agent.nodes.revisit import RevisitNode

from my_agent.nodes.relevance_check import check_relevance
from my_agent.utils.chat_history import update_conversation_memory
from my_agent.utils.config import DEFAULT_TOPK, DEFAULT_RECENCY_DAYS


def create_graph():
    workflow = StateGraph(GraphState)

    # ─── 노드 등록 ───
    workflow.add_node("router", RouterNode())
    workflow.add_node(
        "web_augment",
        WebAugmentNode(default_topk=DEFAULT_TOPK, recency_days=DEFAULT_RECENCY_DAYS)
    )
    workflow.add_node("general", GeneralNode())
    workflow.add_node("issue", IssueNode())
    workflow.add_node("sns", SNSNode())
    workflow.add_node("revisit", RevisitNode())
    workflow.add_node("relevance_checker", check_relevance)
    workflow.add_node("memory_updater", update_conversation_memory)
    
    # ─── 엣지 ───
    workflow.set_entry_point("router")
    workflow.add_edge("router", "web_augment")

    def _route_intent(state):
        intent = (state.get("intent") or "GENERAL").upper()
        if intent in ["SNS", "REVISIT", "ISSUE", "GENERAL"]:
            return intent
        return "GENERAL"

    workflow.add_conditional_edges(
        "web_augment",
        _route_intent,
        {
            "GENERAL": "general",
            "ISSUE": "issue",
            "SNS": "sns",
            "REVISIT": "revisit"
        }
    )

    for node in ["general", "issue", "sns", "revisit"]:
        workflow.add_edge(node, "relevance_checker")

    workflow.add_conditional_edges(
        "relevance_checker",
        lambda s: "pass" if s.get("relevance_passed") else "retry",
        {"pass": "memory_updater", "retry": END}
    )

    workflow.add_edge("memory_updater", END)

    return workflow.compile()