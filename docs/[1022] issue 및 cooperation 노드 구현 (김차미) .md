### [1022] issue 및 cooperation 노드 구현 (김차미) 


- mcp/tools.py 수정
    - 후보 가맹점 검색 전용 함수 생성, 기상청 api 불러오는 함수 생성
    - 이에 따라 연동 파일 수정 (아래와 같음)
    - mcp/server.py → MCP 툴 등록
    - mcp/contracts.py → I/O 타입 정의
    - mcp/adapter_client.py → Python 내부에서 직접 호출 가능하도록 등록
- 라우터는 건들지 않음

- mcp/tools_web.py 수정
- my_agent/nodes/web_augment.py 수정
    - or 검색으로 확장 (노드별 빌드 쿼리)
    - industry를 빼버림 (실제 검색해봤을 때 뺀 게 더 잘 나옴)
- 라우터도 수정
- 엄청 많이 수정

- 기상청 api 받아와야 함 -> config 수정 / api 는 나중에 공유하겠습니다. 
- 