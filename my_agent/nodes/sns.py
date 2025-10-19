# my_agent/nodes/sns.py


from typing import Dict, Any

class SNSNode:
    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        state["final_response"] = "📣 SNSNode는 아직 구현되지 않았습니다. 추후 업데이트 예정입니다."
        return state