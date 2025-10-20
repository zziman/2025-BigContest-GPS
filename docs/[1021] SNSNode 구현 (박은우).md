- 가상환경 source .venv/bin/activate 로 활성화

- my_agent/agent.py에서 아래 주석 활성화하면 SNS 노드로만 실행 가능 
- ## 확인하고 싶으면 자기 노드 이름으로 변환
   -  #def _route_intent(state):
     -    #return "SNS"
- 현재 이상치를 기준으로 LLM에게 전달 X
- 지표는 방문 고객특성, 상권 정보, 매출 정보 및 주력 연령대로 SNS 노드에 제공 

