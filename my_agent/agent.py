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
    workflow.add_node(
        "web_augment",
        WebAugmentNode(default_topk=DEFAULT_TOPK))
    workflow.add_node("general", GeneralNode())
    workflow.add_node("issue", IssueNode())
    workflow.add_node("sns", SNSNode())
    workflow.add_node("revisit", RevisitNode())
    workflow.add_node("cooperation", CooperationNode())
    workflow.add_node("season", SeasonNode())

    workflow.add_node("relevance_checker", check_relevance)
    workflow.add_node("memory_updater", update_conversation_memory)
    
    # ─── 엣지 ───
    workflow.set_entry_point("router")
    
    # router 후 need_clarify 체크
    def _after_router(state):
        if state.get("need_clarify"):
            print("[GRAPH] need_clarify=True 감지 → 즉시 종료")
            return "clarify"
        return "continue"
    
    workflow.add_conditional_edges(
        "router",
        _after_router,
        {
            "clarify": END,  # 후보 선택 필요 → 즉시 종료
            "continue": "web_augment"  # 정상 진행
        }
    )

    def _route_intent(state):
        intent = (state.get("intent") or "GENERAL").upper()
        if intent in ["SNS", "REVISIT", "ISSUE", "GENERAL", "COOPERATION", "SEASON"]:
            return intent
        return "GENERAL"
    
    ## 확인하고 싶으면 자기 노드 이름으로 변환
    #def _route_intent(state):
        #return "SNS"

    workflow.add_conditional_edges(
        "web_augment",
        _route_intent,
        {
            "GENERAL": "general",
            "ISSUE": "issue",
            "SNS": "sns",
            "REVISIT": "revisit", 
            "COOPERATION": "cooperation",
            "SEASON": "season"
        }
    )

    for node in ["general", "issue", "sns", "revisit", "cooperation", "season"]:
        workflow.add_edge(node, "relevance_checker")

    workflow.add_conditional_edges(
        "relevance_checker",
        lambda s: "pass" if s.get("relevance_passed") else "retry",
        {"pass": "memory_updater", "retry": END}
    )

    workflow.add_edge("memory_updater", END)

    return workflow.compile()
