# my_agent/utils/adapters.py
from my_agent.agent import create_graph
from my_agent.utils.state import GraphState
from my_agent.utils.chat_history import save_chat_history, load_chat_history
from typing import Dict, Any

def run_one_turn(user_query: str, thread_id: str = "default") -> Dict[str, Any]:
    graph = create_graph()

    history = load_chat_history(thread_id)
    previous_messages = history.get("messages", [])

    # 초기 상태 업데이트:
    initial_state: GraphState = {
        "user_query": user_query,
        "store_id": None,
        "user_info": None,  ## resolve_store의 출력
        "store_candidates": [],
        "need_clarify": False,
        "messages": previous_messages,
        "relevance_passed": False,
        "retry_count": 0,
        "error": None,
    }

    try:
        final_state = graph.invoke(initial_state)

        # 히스토리 저장 (user_info도 함께 저장)
        metadata = {
            "store_id": final_state.get("store_id"),
            "store_name": final_state.get("user_info", {}).get("store_name") if final_state.get("user_info") else None,
            "intent": final_state.get("intent")
        }
        save_chat_history(
            thread_id=thread_id,
            messages=final_state.get("messages", []),
            metadata=metadata
        )

        # 결과 패키징
        result = {
            "status": "need_clarify" if final_state.get("need_clarify") else (
                "error" if final_state.get("error") else "ok"
            ),
            "intent": final_state.get("intent"),
            "store_id": final_state.get("store_id"),
            "user_info": final_state.get("user_info"),  # ✅ user_info 포함
            "store_candidates": final_state.get("store_candidates", []),
            "final_response": final_state.get("final_response"),
            "messages": final_state.get("messages", []),
            "error": final_state.get("error")
        }

        # optional 필드 추가
        if final_state.get("metrics"):
            result["metrics"] = final_state["metrics"]
        if final_state.get("actions"):
            result["actions"] = final_state["actions"]
        if final_state.get("web_snippets"):
            result["web_snippets"] = final_state["web_snippets"]

        return result

    except Exception as e:
        return {"status": "error", "error": f"그래프 실행 실패: {str(e)}"}
