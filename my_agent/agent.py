# my_agent/agent.py
from langgraph.graph import StateGraph, END
# from langgraph.checkpoint.memory import MemorySaver  # ← 이 줄 삭제 또는 주석

from my_agent.utils.state import GraphState
from my_agent.utils.nodes.router import RouterNode
from my_agent.utils.tools import (
    resolve_store,
    load_card_and_region_data,
    build_features,
    check_relevance,
)
from my_agent.utils.nodes.sns import SNSNode
from my_agent.utils.nodes.revisit import RevisitNode
from my_agent.utils.nodes.issue import IssueNode
from my_agent.utils.nodes.general import GeneralNode
from my_agent.utils.nodes.web_augment import WebAugmentNode
from my_agent.utils.chat_history import update_conversation_memory  # ← 추가

def create_graph():
    workflow = StateGraph(GraphState)

    # ─── 노드 등록 ───
    workflow.add_node("router", RouterNode())
    workflow.add_node("store_resolver", resolve_store)
    workflow.add_node("data_collector", load_card_and_region_data)
    workflow.add_node("feature_builder", build_features)
    workflow.add_node("web_augment", WebAugmentNode(default_topk=5, recency_days=60))
    workflow.add_node("sns", SNSNode())
    workflow.add_node("revisit", RevisitNode())
    workflow.add_node("issue", IssueNode())
    workflow.add_node("general", GeneralNode())
    workflow.add_node("relevance_checker", check_relevance)
    workflow.add_node("memory_updater", update_conversation_memory)  # ← 메모리 노드

    # ─── 엣지 ───
    workflow.set_entry_point("router")
    workflow.add_edge("router", "store_resolver")

    workflow.add_conditional_edges(
        "store_resolver",
        lambda state: "clarify" if state.get("need_clarify") else "proceed",
        {"clarify": END, "proceed": "data_collector"},
    )

    workflow.add_edge("data_collector", "feature_builder")
    workflow.add_edge("feature_builder", "web_augment")

    def _route_after_web(state):
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

    for node in ["sns", "revisit", "issue", "general"]:
        workflow.add_edge(node, "relevance_checker")

    workflow.add_conditional_edges(
        "relevance_checker",
        lambda state: "pass" if state.get("relevance_passed") else "retry",
        {"pass": "memory_updater", "retry": END},  # ← memory_updater로 변경
    )
    
    workflow.add_edge("memory_updater", END)  # ← 메모리 후 종료

    # ✅✅✅ 여기가 핵심! checkpointer 없이 컴파일
    return workflow.compile()  # checkpointer 파라미터 없음!