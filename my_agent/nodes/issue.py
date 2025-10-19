# my_agent/nodes/issue.py


# -*- coding: utf-8 -*-
"""
IssueNode - 문제 진단형 노드 (임시 버전)
나중에 실제 로직 구현 예정
"""

from typing import Dict, Any

class IssueNode:
    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        # 임시 출력
        state["final_response"] = "🛠 IssueNode는 아직 구현되지 않았습니다. 추후 업데이트 예정입니다."
        return state