# my_agent/nodes/revisit.py


from typing import Dict, Any

class RevisitNode:
    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        state["final_response"] = "🔁 RevisitNode는 아직 구현되지 않았습니다. 추후 업데이트 예정입니다."
        return state