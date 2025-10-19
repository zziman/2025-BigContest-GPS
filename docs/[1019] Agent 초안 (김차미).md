# [1019] Agent guide (김차미)

- 가상환경 source .venv/bin/activate 로 활성화


- 각 노드 클래스는 다른 코드들 참고해서 클래스명 적어야 함
- metrics의 함수도 마찬가지로 맞춰야 함 (모르면 물어보세요)
- 각 노드에서는 가게 이름이 없거나 여러 개면 사용자에게 질문을 날려야 함! (general 제외)
- 가게 이름이 없고 있고는 resolve_store에서 판단 -> 때문에 그냥 쿼리를 resolve_store에 그냥 넘겨주면 됨


- my_agent.metrics.main_metrics에서 구축할 때 결국 마지막에 가게 주요지표, 상권 단위 정보 return하는 함수명은 build_main_metrics 여야 함
  -> 이해 안 되면 # my_agent/nodes/general.py 참고
  - 결과는 잘 나오는데 chat_history에서 답변이 잘리는 경향이 있음 -> 이거 디벨롭해야 함