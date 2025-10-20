# [1021] Search Merchant guide (이지민)

## 가맹점 검색 툴 고도화

---

```python
사용자 입력
    ↓
STEP 1: LLM 추출 (utils/tools.py)
    ↓
STEP 2: 검색 조율 (utils/tools.py)
    ↓
STEP 3: DB 조회 (mcp/tools.py)
    ↓
STEP 4: 완전한 데이터 로드 (mcp/tools.py)
    ↓
최종 결과 (자동확정 or 선택요청)
```

> **STEP 1: LLM 추출 (`StoreResolver.extract_store_info`)**
> 
> 
> `my_agent/utils/tools.py` → `StoreResolver` 클래스
> 

사용자의 자연어 질문에서 가맹점 관련 텍스트 추출 

| 입력 | 출력 |
| --- | --- |
| "본죽 강남점 매출 분석해줘" | `"본죽 강남점"` (가맹점명) |
| "761947ABD9 분석" | `"761947ABD9"` (구분번호) |
| "761947ABD9 본죽 트렌드" | `"761947ABD9"` (구분번호 우선) |
| "치킨집 트렌드 알려줘" | `None` (가맹점 정보 없음) |
- 구분번호 우선 추출: 구분번호와 가맹점명이 함께 있으면 구분번호만 추출
- 구분번호인지 가맹점명인지 구분 X (MCP가 판단)
- DB 조회나 검증 과정 없이 순수 추출만 수행
- "우리 가게", "여기" 같은 모호한 표현은 무시

> **STEP 2: 검색 조율 (`resolve_store`)**
`my_agent/utils/tools.py` → `resolve_store()` 함수
> 

LLM 결과를 받아 MCP 호출 및 최종 결과 처리

1. LLM으로부터 추출된 텍스트 받기
2. 추출 실패 시 → GENERAL 모드 (가맹점 무관 질문)
3. 추출 성공 시 → MCP `search_merchant` 호출
4. MCP 결과에 따라 분기 처리
5. 자동 확정 시 → `load_store_data` 호출 (완전한 정보 로드)

| 상황 | 검색 유형 | 후보 수 | 처리 방식 |
| --- | --- | --- | --- |
| 구분번호 조회 성공 | `id` | 1개 | ✅ 자동 확정 |
| 구분번호 조회 실패 | `id` | 0개 | GENERAL 모드 |
| 가맹점명 1개 매칭 | `name` | 1개 | ✅ 자동 확정 |
| 가맹점명 여러 개 | `name` | 2개 이상 | ⚠️ 사용자 선택 요청 |
- **출력 (상태 업데이트)**
    - `store_id`: 확정된 가맹점_구분번호
    - `user_info`: 완전한 가맹점 정보
        
        ```python
        {
              "store_name": "본죽*강남점",
              "store_num": "761947ABD9",
              "location": "서울 강남구 역삼동...",
              "marketing_area": "역세권",  # ✅ 추가
              "industry": "분식",
              "months_operating": 24,  # ✅ 추가
              "is_individual": "개인사업자"  # ✅ 추가 (1→"개인사업자", 0→"프랜차이즈")
          }
        ```
        
    - `need_clarify`: 후보 선택 필요 여부
    - `store_candidates`: 후보 목록 (여러 개일 때)

> **STEP 3: DB 조회 (`search_merchant`)**
> 
> 
>  `mcp/tools.py` → `search_merchant()` 함수
> 

실제 DB 조회 및 매칭 로직 수행

- 1단계: 패턴 감지
    - 정규식으로 구분번호 패턴 체크 (`^[A-Z0-9]{10,11}$`)
    - 매칭되면 → 구분번호로 처리 (`search_type="id"`)
    - 아니면 → 가맹점명으로 처리 (`search_type="name"`)
- 2단계: DB 조회
    - 구분번호 조회
        - DB에서 정확히 해당 ID만 검색
        - 있으면 1개, 없으면 0개
    - 가맹점명 검색 (우선순위)
        1. 정확 일치 (완전히 같은 이름)
        2. 부분 일치 (이름에 포함)
        3. 앞 2글자 일치 (완화된 검색)
- 3단계: 결과 정렬 (가맹점명 검색 시)
    1.  마스킹 적은 순 (실제 가게명에 가까운 순)
    2. 이름 짧은 순
    3. 가나다순
- 4단계: 중복 제거
    - 같은 가맹점의 여러 시점 데이터 제거
    - 최신 데이터 1개만 남김
- **출력**
    - `found`: 검색 성공 여부
    - `count`: 후보 개수
    - `merchants`: 가맹점 목록
    - `search_type`: `"id"` 또는 `"name"` (어떤 방식으로 검색했는지)

## Agent 프로세스

---

```python
User Query
    ↓
┌─────────────────────────────────────────┐
│  Graph Workflow (LangGraph)             │
│                                         │
│  Router → Web Augment → Intent Node     │
│     ↓                        ↓          │
│  Clarify?                 General       │
│     ↓                     Sales         │
│    END                    Revisit       │
│                           SNS           │
│                              ↓          │
│                          Response       │
└─────────────────────────────────────────┘
    ↓
Final Response
```