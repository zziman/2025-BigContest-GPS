# my_agent/utils/chat_history.py
 
#  -*- coding: utf-8 -*-
"""
채팅 히스토리 JSON 저장/로드
"""
import json
import os
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

from my_agent.utils.state import GraphState


# 히스토리 저장 경로
HISTORY_DIR = Path("chat_history")
HISTORY_DIR.mkdir(exist_ok=True)


def _message_to_dict(msg: BaseMessage) -> Dict[str, Any]:
    """LangChain 메시지 → JSON 직렬화 가능한 딕셔너리"""
    return {
        "role": "user" if isinstance(msg, HumanMessage) else "assistant",
        "content": msg.content,
        "timestamp": datetime.now().isoformat(),
    }


def _dict_to_message(data: Dict[str, Any]) -> BaseMessage:
    """딕셔너리 → LangChain 메시지"""
    if data["role"] == "user":
        return HumanMessage(content=data["content"])
    else:
        return AIMessage(content=data["content"])


def save_chat_history(
    thread_id: str,
    messages: List[BaseMessage],
    metadata: Optional[Dict[str, Any]] = None
) -> str:
    """
    채팅 히스토리를 JSON 파일로 저장
    
    Args:
        thread_id: 대화 스레드 ID
        messages: LangChain 메시지 리스트
        metadata: 추가 메타데이터 (store_id, store_name 등)
    
    Returns:
        저장된 파일 경로
    """
    filepath = HISTORY_DIR / f"{thread_id}.json"
    
    # 기존 파일이 있으면 로드
    if filepath.exists():
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {
            "thread_id": thread_id,
            "created_at": datetime.now().isoformat(),
            "messages": [],
            "metadata": metadata or {}
        }
    
    # 새 메시지 추가
    data["messages"] = [_message_to_dict(m) for m in messages]
    data["updated_at"] = datetime.now().isoformat()
    
    # 메타데이터 병합
    if metadata:
        data["metadata"].update(metadata)
    
    # 저장
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    return str(filepath)


def load_chat_history(thread_id: str) -> Dict[str, Any]:
    """
    JSON 파일에서 채팅 히스토리 로드
    
    Args:
        thread_id: 대화 스레드 ID
    
    Returns:
        {
            "messages": List[BaseMessage],
            "metadata": Dict,
            "created_at": str,
            "updated_at": str
        }
    """
    filepath = HISTORY_DIR / f"{thread_id}.json"
    
    if not filepath.exists():
        return {
            "messages": [],
            "metadata": {},
            "created_at": None,
            "updated_at": None
        }
    
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    return {
        "messages": [_dict_to_message(m) for m in data.get("messages", [])],
        "metadata": data.get("metadata", {}),
        "created_at": data.get("created_at"),
        "updated_at": data.get("updated_at"),
    }


def list_chat_histories() -> List[Dict[str, Any]]:
    """모든 채팅 히스토리 메타정보 조회"""
    histories = []
    
    for filepath in HISTORY_DIR.glob("*.json"):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            histories.append({
                "thread_id": data.get("thread_id"),
                "created_at": data.get("created_at"),
                "updated_at": data.get("updated_at"),
                "message_count": len(data.get("messages", [])),
                "store_name": data.get("metadata", {}).get("store_name"),
                "store_id": data.get("metadata", {}).get("store_id"),
            })
        except Exception:
            continue
    
    # 최근 업데이트 순 정렬
    histories.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    return histories


def delete_chat_history(thread_id: str) -> bool:
    """채팅 히스토리 삭제"""
    filepath = HISTORY_DIR / f"{thread_id}.json"
    
    if filepath.exists():
        filepath.unlink()
        return True
    return False


def export_all_histories(output_path: str = "./all_chat_histories.json"):
    """모든 히스토리를 하나의 JSON으로 내보내기"""
    all_data = []
    
    for filepath in HISTORY_DIR.glob("*.json"):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            all_data.append(data)
        except Exception:
            continue
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)
    
    return output_path


def update_conversation_memory(state: GraphState) -> GraphState:
    """
    대화 메모리 업데이트 (노드용)
    
    Note: 이 함수는 그래프 노드로 등록되어 사용됩니다.
    """
    user_query = state.get("user_query", "")
    final_response = state.get("final_response", "")
    
    if user_query:
        state["messages"].append(HumanMessage(content=user_query))
    if final_response:
        state["messages"].append(AIMessage(content=final_response))
    
    # 10턴 초과 시 요약 (현재는 더미)
    if len(state["messages"]) >= 10:
        state["conversation_summary"] = "최근 대화 요약..."
    
    return state
