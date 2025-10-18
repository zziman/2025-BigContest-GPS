# my_agent/utils/adapters.py
from my_agent.agent import create_graph
from my_agent.utils.state import GraphState
from my_agent.utils.chat_history import (
    save_chat_history,
    load_chat_history
)
from typing import Dict, Any


def run_one_turn(
    user_query: str,
    store_name: str,
    thread_id: str = "default"
) -> Dict[str, Any]:
    """
    단일 턴 실행 (Streamlit/CLI 공용)
    """
    graph = create_graph()
    
    # ✅ 기존 히스토리 로드
    history = load_chat_history(thread_id)
    previous_messages = history.get("messages", [])
    
    # 초기 상태 (기존 메시지 포함)
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
        "messages": previous_messages,
        "conversation_summary": None,
        "relevance_passed": False,
        "retry_count": 0,
        "error": None
    }
    
    # ✅ config 제거 (체크포인터 없으므로 불필요)
    # config = {"configurable": {"thread_id": thread_id}}
    
    try:
        # ✅ config 파라미터 제거
        final_state = graph.invoke(initial_state)  # config 제거
        
        # ✅ 히스토리 저장 (메타데이터 포함)
        metadata = {
            "store_name": store_name,
            "store_id": final_state.get("store_id"),
            "intent": final_state.get("intent"),
        }
        save_chat_history(
            thread_id=thread_id,
            messages=final_state.get("messages", []),
            metadata=metadata
        )
        
        # 디버그 로그
        print({
            "LOG": "adapter_after_invoke",
            "need_clarify": final_state.get("need_clarify"),
            "intent": final_state.get("intent"),
            "store_id": final_state.get("store_id"),
            "messages_count": len(final_state.get("messages", [])),
        })
        
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
            "messages": final_state.get("messages", []),
            "error": final_state.get("error")
        }
    
    except Exception as e:
        return {
            "status": "error",
            "error": f"그래프 실행 실패: {str(e)}"
        }