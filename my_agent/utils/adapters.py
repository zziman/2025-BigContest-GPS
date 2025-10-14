# -*- coding: utf-8 -*-
"""
그래프 실행 어댑터: Streamlit/CLI 공용
"""
from my_agent.agent import create_graph
from my_agent.utils.state import GraphState
from typing import Dict, Any


def run_one_turn(
    user_query: str,
    store_name: str,
    thread_id: str = "default"
) -> Dict[str, Any]:
    """
    단일 턴 실행 (Streamlit/CLI 공용)
    
    Args:
        user_query: 사용자 질문
        store_name: 가맹점명
        thread_id: 대화 스레드 ID (멀티턴 구분)
    
    Returns:
        실행 결과 딕셔너리
    """
    graph = create_graph()
    
    # 초기 상태
    initial_state: GraphState = {
        "user_query": user_query,
        "store_name_input": store_name,
        "intent": None,
        "store_id": None,
        "store_candidates": [],
        "need_clarify": False,
        "card_data": None,
        "area_data": None,
        "region_data": None,
        "signals": [],
        "persona": None,
        "channel_hints": [],
        "raw_response": None,
        "final_response": None,
        "actions": [],
        "messages": [],
        "conversation_summary": None,
        "relevance_passed": False,
        "retry_count": 0,
        "error": None
    }
    
    # 그래프 실행
    config = {"configurable": {"thread_id": thread_id}}
    
    try:
        final_state = graph.invoke(initial_state, config)
        
        # 결과 포맷팅
        return {
            "status": "need_clarify" if final_state.get("need_clarify") else (
                "error" if final_state.get("error") else "ok"
            ),
            "intent": final_state.get("intent"),
            "store_id": final_state.get("store_id"),
            "store_candidates": final_state.get("store_candidates", []),
            "card": final_state.get("card_data"),
            "final_response": final_state.get("final_response"),
            "actions": final_state.get("actions", []),
            "error": final_state.get("error")
        }
    
    except Exception as e:
        return {
            "status": "error",
            "error": f"그래프 실행 실패: {str(e)}"
        }