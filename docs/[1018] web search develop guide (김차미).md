# [1018] web search develop guide (김차미)

- 수정한 파일들
| 파일 경로 | 내용 |
|-----------|------|
| requirements.txt | 검색 기능 구현에 필요한 라이브러리 추가 |
| my_agent/utils/config.py | 잘못된 변수명 수정 (`sufer` → `serper`, `tavili` → `tavily`) |
| mcp/tools_web.py | 웹 검색 로직 구성 및 검색 옵션 정리 |
| my_agent/utils/nodes/web_augment.py | 검색 호출부 수정 |
| mcp/contracts.py | `validate_web_search_input` 및 `WebSearchInput` 구조 수정 |


### tools_web.py 사용 설명
- 유사도 cosine, uni-encoder, cross encoder 사용 가능
- 사용자 쿼리 재생성
- 최신 정보 활용 및 검색 문서 개수 안 되면 한 번 더 검색


- 더 디벨롭해야 하는 것
  -> 날짜가 나오지 않음
  -> 소요 시간 최대 30~40초 너무 길음
  -> cosine 말고 다른 것으로 했을 때를 확인해야 함..! 헷 ><>
- 실행해보고 싶다면...
  - if __main__에 검색해보고 싶은 쿼리 넣고...
  - 2025-BigContest/ 내에서 python -m mcp.tools_web_serper 터미널 실행
  - 2025-BigContest/ 내에 websearch_result.json 생성됨 -> 이거 확인하면 됨


### 호출부
- utils/nodes/web_augment.py

'''resp = call_mcp_tool(
    "web_search",
    query=query,
    top_k=self.default_topk,
    recency_days=self.recency_days,
    rewrite_query=True,     # 검색 쿼리 품질 향상
    rerank="cosine"         # 기본 rerank 유지
    )'''

- 여기서 rerank 바꿀 수 있음 / 그다지 큰 부분은 아니라 config로 안 뺌!!