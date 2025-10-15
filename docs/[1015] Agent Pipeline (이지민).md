# [1015] Agent Pipeline (이지민)

## Pipeline

---

```python
[사용자 입력]
     │   (store name + 질문)
     ▼
┌───────────────────┐
│ Adapter           │  ← run_one_turn(): state 초기화, graph.invoke()
└─────────┬─────────┘
          ▼
┌───────────────────┐
│ Intent Router     │  ← LLM 우선 분류(+규칙 보정)
│  - SNS?           │
│  - 재방문?        │
│  - 문제진단?      │
│  - 종합전략?      │
└─────────┬─────────┘
          │
          ▼
┌───────────────────────────┐
│ SearchStore / Resolve     │  ← MCP: search_merchant
│ (가맹점 후보 탐색/확정)   │
└─────────────┬─────────────┘
              │
              │  후보가 여러 개?
              ├──▶ Clarify (후보 선택 유도)
              │          └─▶ [Adapter 결과: status="need_clarify"]
              │
              ▼
┌───────────────────────────┐
│ Data Collector            │  ← MCP: load_store_data / resolve_region /
│ (카드/상권/행정동 수집)   │           load_area_data / load_region_data
└─────────────┬─────────────┘
              ▼
┌───────────────────────────┐
│ Feature Builder           │  ← signals / persona / channel_hints
│ (지표/인사이트 계산)      │
└─────────────┬─────────────┘
              ▼
┌───────────────────────────┐
│ Web Augment               │  ← MCP: web_search (naver/serper/tavily/auto)
│ (외부 레퍼런스 보강)      │     → web_snippets / web_meta
└─────────────┬─────────────┘
              ▼
   ┌──────────┼───────────┬───────────────┬───────────────┐
   │          │           │               │               │
   ▼          ▼           ▼               ▼
┌─────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐
│ SNS Node    │  │ Revisit Node │  │ Issue Node   │  │ General Node│
│ (SNS전략)   │  │ (재방문전략)  │  │ (문제 진단)   │  │ (종합전략)  │
└───────┬─────┘  └──────┬───────┘  └──────┬───────┘  └──────┬──────┘
        │               │                 │                 │
        └───────────────┴─────────────────┴─────────────────┘
                            │  (공통: LLM + 후처리)
                            ▼
┌───────────────────────────┐
│ Strategy Generator (LLM)  │  ← 프롬프트(노드별) + web_snippets 참고,
│ + Postprocess             │     배지/면책/액션/출처 블록
└─────────────┬─────────────┘
              ▼
┌───────────────────────────┐
│ Relevance Check           │  ← 길이/데이터근거/숫자/의도 키워드 검증
│ (소프트 웹인용 점검 포함) │
└─────────────┬─────────────┘
              ▼
        ┌───────────────┬────────────────────┐
        │               │                    │
        ▼               ▼                    ▼
     ✅ 최종 응답      ⚠️ Clarify            ❌ Error
 (Adapter가 status/     (후보 선택 유도,      (수집/LLM 등
  final/actions와 함께    상태 요약 반환)       오류 메시지)
  UI 렌더)

```

- LangGraph Node
    
    
    | Node ID  | 구현(파일/함수) | 목적 | 읽는 상태키 | 쓰는 상태키 |
    | --- | --- | --- | --- | --- |
    | `router` | `my_agent/utils/nodes/router.py: RouterNode` | 사용자 질문 의도 분류 | `user_query` | `intent` |
    | `store_resolver` | `my_agent/utils/tools.py: resolve_store` | 가맹점명 → 후보 탐색/확정 | `store_name_input` | `store_candidates`, `store_id`, `need_clarify`, `error` |
    | `data_collector` | `my_agent/utils/tools.py: load_card_and_region_data` | 카드/상권/행정동 데이터 수집 | `store_id` | `card_data`, `area_data`, `region_data`, `error` |
    | `feature_builder` | `my_agent/utils/tools.py: build_features` | 신호/페르소나/채널 힌트 생성 | `card_data` | `signals`, `persona`, `channel_hints`, `error` |
    | `web_augment` | `my_agent/utils/nodes/web_augment.py: WebAugmentNode` | 질의·시그널 기반 외부 웹 레퍼런스 보강(MCP `web_search`) | `user_query`, `signals`, `intent` | `web_snippets`, `web_meta`, `error` |
    | `sns` | `my_agent/utils/nodes/sns.py: SNSNode` | SNS 전략 생성(LLM) | `card_data`, `signals`, `persona`, `user_query`, `channel_hints`, `web_snippets`, `web_meta` | `raw_response`, `final_response`, `actions` |
    | `revisit` | `my_agent/utils/nodes/revisit.py: RevisitNode` | 재방문 전략(LLM) | `card_data`, `signals`, `persona`, `user_query`, `web_snippets`, `web_meta` | `raw_response`, `final_response`, `actions` |
    | `issue` | `my_agent/utils/nodes/issue.py: IssueNode` | 문제 진단(LLM) | `card_data`, `signals`, `user_query`, `web_snippets`, `web_meta` | `raw_response`, `final_response`, `actions` |
    | `general` | `my_agent/utils/nodes/general.py: GeneralNode` | 종합 전략(LLM) | `card_data`, `signals`, `persona`, `user_query`, `web_snippets`, `web_meta` | `raw_response`, `final_response`, `actions` |
    | `relevance_checker` | `my_agent/utils/tools.py: check_relevance` | 응답 품질 검증(소프트 웹인용 규칙 포함) | `raw_response`, `final_response`, `user_query`, `card_data`, `intent`, `web_snippets` | `relevance_passed`, `retry_count`, `error` |
- MCP Tool
    
    
    | 툴 이름 | 목적 | 필수 파라미터 | 반환(주요 키) | 호출처(노드) |
    | --- | --- | --- | --- | --- |
    | `search_merchant` | 가맹점명으로 후보 조회 | `merchant_name: str` | `found: bool`, `merchants: list[dict]` | `store_resolver` |
    | `load_store_data` | 확정 가맹점의 카드 데이터 로드 | `store_id: str` | `success: bool`, `data: dict` | `data_collector` |
    | `resolve_region` | 지역명 → 행정동 코드 매핑 | `district: str` | `success: bool`, `admin_dong_code: str` | `data_collector` |
    | `load_area_data` | 상권(상업지표) 데이터 로드 | `admin_dong_code: str` | `success: bool`, `data: dict` | `data_collector` |
    | `load_region_data` | 행정동(인구/주거 등) 데이터 로드 | `admin_dong_code: str` | `success: bool`, `data: dict` | `data_collector` |
    | `web_search` | 외부 웹 레퍼런스 수집(네이버·Serper·Tavily) | `query: str`, *(옵션)* `provider: "naver" | "serper" | "tavily" |
- 예: “본죽 문제점이 뭐야?” 내부 동작 과정
    1. **UI 입력 → 어댑터 호출**
        - 사용자가 Chatbot 메뉴에서 “본죽 문제점이 뭐야?” 입력.
        - Streamlit이 세션 히스토리에 `HumanMessage` 추가 후 어댑터 호출:
            
            ```python
            result = run_one_turn(
                user_query="본죽 문제점이 뭐야?",
                store_name=None,                 # Home에서 따로 선택한 가맹점이 없으면 None
                thread_id=st.session_state.thread_id,
                messages=st.session_state.messages,   # (선택) 세션 히스토리 전달
            )
            
            ```
            
        - 어댑터는 **state 초기화**(`_init_state`)하고, **그래프 싱글톤**을 가져옴(`_get_graph` → `create_graph` 캐시).
    2. **RouterNode → 의도 분류**
        - `RouterNode()`가 `state["user_query"]` 분석:
            - “문제/이슈/원인/진단/개선” 신호 감지 → **ISSUE**로 판정.
        - `state["intent"] = "ISSUE"` 설정.
    3. **가맹점 확정 → resolve_store (tools 함수형 노드)**
        - `store_name_input`(= `store_name`) 있으면 MCP `search_merchant` 사용.
        - 후보 다수 시 `_rank_candidates`(정확일치 > prefix > 길이)로 정렬.
        - `CONFIRM_ON_MULTI == 1` & 후보>1 → `need_clarify=True`로 종료
            
            (어댑터는 `status="need_clarify"`, 후보 테이블과 함께 UI 반환).
            
        - 그 외 자동 확정 → `state["store_id"]` 채움.
    4. **데이터 수집 → load_card_and_region_data (tools)**
        - MCP 툴 체인:
            - `load_store_data(store_id)` → `state["card_data"]`
            - `resolve_region(district)` → 행정동 코드
            - `load_area_data(admin_dong_code)` → `state["area_data"]`(옵션)
            - `load_region_data(admin_dong_code)` → `state["region_data"]`(옵션)
        - 실패 시 `state["error"]` 설정 → 어댑터가 `status="error"`로 반환.
    5. **특징 생성 → build_features (tools)**
        - 카드 데이터에서 시그널/페르소나/채널 힌트 생성:
            - `RETENTION_ALERT`(재방문율<0.2)
            - `CHANNEL_MIX_ALERT`(배달비중≥0.5)
            - `NEW_CUSTOMER_FOCUS`(신규비중>0.4)
        - `state["persona"]`, `state["channel_hints"]` 설정.
    6. **외부 레퍼런스 보강 → WebAugmentNode (신규 단계)**
        - 질의와 시그널을 바탕으로 **웹 검색**(네이버/Serper/Tavily) 수행:
            - provider = 사용자가 지정하지 않으면 `auto`(키 유무·쿼리 성격으로 자동 선택)
            - `top_k`(기본 5), `recency_days`(기본 60) 적용
        - 결과를 정규화하여 `state["web_snippets"]`(title/url/snippet/source/published_at/score), `state["web_meta"]`(provider_used/query) 저장.
        - 이후 노드(ISSUE/SNS/REVISIT/GENERAL)에서 컨텍스트 참고 가능.
    7. **의도 분기 → IssueNode 실행**
        - `intent=="ISSUE"` 이므로 `IssueNode()` 수행.
    8. **IssueNode LLM 호출 + 프롬프트 조립**
        - 노드 내부 프롬프트(내장) +
            
            `tools.build_base_context(card_data)` +
            
            `tools.build_signals_context(signals)` +
            
            `user_query`로 프롬프트 구성.
            
        - `ChatGoogleGenerativeAI` 호출 → `state["raw_response"]` 저장.
        - `tools.postprocess_response` 호출(웹 보강 반영):
            - 텍스트 정리(`clean_response`)
            - **프록시 배지/기준 데이터 배지** 부착
            - **웹 출처 블록 자동 부착**(있을 때, `state["web_snippets"]`, `state["web_meta"]`)
            - **액션 시드**와 **면책** 추가
            - 결과를 `state["final_response"]`, `state["actions"]`에 저장.
    9. **품질 검증 → check_relevance (tools)**
        - `ENABLE_RELEVANCE_CHECK`가 True면:
            - **기본 관련성**(길이, 가맹점명 포함, 데이터 근거/숫자 포함)
            - **ISSUE 키워드 수** 검사
            - (소프트 규칙) 웹 스니펫이 있으면 응답에 최소한의 **출처 힌트**가 노출되었는지 점검
                
                실패 시 에러 메시지는 기록하되 하드-실패로 전환하지 않음(현재 설정).
                
    10. **어댑터 결과 요약 반환**
        - 어댑터가 LangGraph 출력을 아래 스키마로 정리해 UI에 전달:
            
            ```python
            {
              "status": "ok" | "need_clarify" | "error",
              "final_response": str | None,
              "actions": list,
              "store_candidates": list,          # need_clarify일 때만
              "web_snippets": list | None,       # (편의상 직접 동봉; 또는 state 안에만)
              "web_meta": dict | None,           # (provider_used, query)
              "error": str | None,
              "state": out,                      # 디버깅용 전체 상태
            }
            
            ```
            
        - Streamlit은 `status`에 따라 텍스트/표/경고를 렌더:
            - `ok`: `AIMessage(final_response)`를 세션 히스토리에 push, **출처 UI**(expander)도 함께 노출
            - `need_clarify`: 후보 테이블과 메시지 렌더
            - `error`: 에러 메시지 렌더
    
    > 한 줄 요약
    > 
    > 
    > **UI → 어댑터(run_one_turn) → 그래프(create_graph 캐시) → Router → Resolver → Data → Features → WebAugment(웹 보강) → ISSUE 노드(LLM) → 후처리/검증 → 어댑터 요약 → UI 렌더**
    > 

## Implementation

---

<aside>

### 1) `my_agent/utils/nodes/`

---

- **`router.py`**
    
    **역할**
    
    - 사용자 질의 의도를 **LLM 우선**으로 분류 (`SNS / REVISIT / ISSUE / GENERAL`), 실패 시 **키워드 룰** 보정.
    
    **입력**
    
    - `GraphState.user_query: str`
    
    **출력**
    
    - `GraphState.intent: Literal["SNS","REVISIT","ISSUE","GENERAL"]`
    
    **핵심 동작**
    
    1. LLM 분류 → 라벨 정규화(동의어 alias)
    2. 실패 시 RULES 키워드 매칭 → 기본값 `GENERAL`
    3. `state["intent"] = intent`

---

- **`sns.py` / `revisit.py` / `issue.py` / `general.py`** (구조 동일)
    
    **역할**
    
    - 사용자 질의 의도를 **LLM 우선**으로 분류 (`SNS / REVISIT / ISSUE / GENERAL`), 실패 시 **키워드 룰** 보정.
    
    **입력**
    
    - `GraphState.user_query: str`
    
    **출력**
    
    - `GraphState.intent: Literal["SNS","REVISIT","ISSUE","GENERAL"]`
    
    **핵심 동작**
    
    1. LLM 분류 → 라벨 정규화(동의어 alias)
    2. 실패 시 RULES 키워드 매칭 → 기본값 `GENERAL`
    3. `state["intent"] = intent`

---

- **`web_augment.py`**
    
    **역할**
    
    - 질의/시그널/의도를 받아 **외부 웹 레퍼런스 보강** 수행 (MCP `web_search` 호출).
    - 결과를 통일 포맷으로 상태에 저장하여 생성 노드가 참고/후처리에서 인용 가능.
    
    **입력**
    
    - `GraphState.user_query`
    - `GraphState.signals`
    - `GraphState.intent`
    
    **출력**
    
    - `GraphState.web_snippets: List[WebDoc]`
    - `GraphState.web_meta: Dict[str, Any]` (`provider_used`, `query`, `count` 등)
    - 필요 시 `GraphState.error`
    
    **핵심 동작**
    
    - provider 자동선택(`auto`) 또는 환경변수(top_k/recency_days) 기반 호출
    - 결과 정규화(title, url, snippet, source, published_at, score)
</aside>

<aside>

### 2) 공용 유틸·엔진

---

- **`my_agent/utils/config.py`**
    
    **역할**
    
    - `secrets.toml`/`.env`/환경변수에서 설정 로드.
    - 모델/키/토글/경로 일원화 + 웹 검색 키 지원.
    
    **주요 키**
    
    - 모델: `GOOGLE_API_KEY`, `LLM_MODEL`, `LLM_TEMPERATURE`
    - 토글: `CONFIRM_ON_MULTI`, `ENABLE_RELEVANCE_CHECK`, `ENABLE_MEMORY`
    - 웹검색: `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`, `SERPER_API_KEY`, `TAVILY_API_KEY`
    - 검색 파라미터(옵션): `SEARCH_TOPK`(기본 5), `SEARCH_RECENCY_DAYS`(기본 60), `SEARCH_TIMEOUT`(기본 12)

---

- **`my_agent/utils/state.py`**
    
    **역할**
    
    - LangGraph 공용 상태 스키마 정의.
    
    **주요 필드(추가 포함)**
    
    - 입력/라우팅: `user_query`, `store_name_input`, `intent`
    - 가맹점 확정: `store_id`, `store_candidates`, `need_clarify`
    - 데이터: `card_data`, `area_data`, `region_data`
    - 분석: `signals`, `persona`, `channel_hints`
    - LLM: `raw_response`, `final_response`
    - 액션: `actions`
    - 웹 보강: `web_snippets`, `web_meta`
    - 제어/오류: `relevance_passed`, `retry_count`, `error`
    - 멀티턴: `messages`, `conversation_summary`

---

- **`my_agent/utils/tools.py`**
    
    **역할**
    
    - 파이프라인 함수형 유틸/노드 집합.
    
    **핵심 묶음**
    
    - **resolver**: `resolve_store` (MCP `search_merchant`로 후보 조회/랭킹/확정, `CONFIRM_ON_MULTI` 분기)
    - **data**: `load_card_and_region_data` (MCP `load_store_data`/`resolve_region`/`load_area_data`/`load_region_data`)
    - **feature**: `build_features` (signals/persona/channel_hints 생성)
    - **prompt builder**: `build_base_context`, `build_signals_context`
    - **postprocess**:
        - `postprocess_response(raw, card, signals, intent="GENERAL", web_snippets=None, web_meta=None)`
        - `clean_response`, `generate_action_seed`, `add_proxy_badge`, `add_data_quality_badge`, `add_disclaimer`
        - (업데이트) 웹 스니펫이 있으면 **응답 하단에 출처 블록**을 안전하게 덧붙이는 헬퍼 포함
    - **relevance**:
        - `check_relevance(state)` : 기본/인텐트별/구조/액션/금지어 검사
        - (보완) 웹 스니펫 존재 시 최소 인용 힌트 소프트 점검(하드-페일 아님)

---

- **`my_agent/agent.py`**
    
    **역할**
    
    - 그래프 정의 + 노드/엣지 + 체크포인트.
    
    **노드 등록**
    
    - 클래스: `RouterNode`, `SNSNode`, `RevisitNode`, `IssueNode`, `GeneralNode`
    - 함수: `resolve_store`, `load_card_and_region_data`, `build_features`, `check_relevance`
    - **NEW**: `WebAugmentNode(default_topk=5, recency_days=60)`
    
    **엣지**
    
    - `router → store_resolver`
    - `store_resolver`: `need_clarify → END`, `proceed → data_collector`
    - `data_collector → feature_builder → web_augment`
    - `web_augment`: intent에 따라 `sns/revisit/issue/general`
    - 각 생성 노드 → `relevance_checker → {pass: END, fail: END}`

---

- **`my_agent/utils/adapters.py`**
    
    **역할**
    
    - `run_one_turn(user_query, store_name, thread_id, messages=...)` 단일 호출.
    - 내부에서 `create_graph()` 캐시 후 `graph.invoke()` → UI 친화 포맷으로 요약.
    
    **반환 스키마**
    
    ```python
    {
      "status": "ok" | "need_clarify" | "error",
      "final_response": str | None,
      "actions": list,
      "store_candidates": list,  # need_clarify 시
      "web_snippets": list | None,
      "web_meta": dict | None,
      "intent": str | None,
      "store_id": str | None,
      "error": str | None,
      "state": dict,             # 디버깅 용
    }
    ```
    
</aside>

<aside>

### 3) MCP

---

- `mcp/contracts.py`
- `mcp/tools_web.py`
    
    **역할**
    
    - 외부 웹 검색 통합(Naver/Serper/Tavily) → 공통 포맷으로 반환.
    
    **환경키**
    
    - `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`, `SERPER_API_KEY`, `TAVILY_API_KEY`
    - (옵션) `SEARCH_TOPK`, `SEARCH_RECENCY_DAYS`, `SEARCH_TIMEOUT`
    
    **핵심**
    
    - 빈 키면 해당 provider skip
    - `provider="auto"`일 때 보유 키/질의 유형으로 선택
    - HTML 태그/엔티티 정리, 날짜/도메인 표준화
</aside>

<aside>

### 4) 실행 스크립트

---

- **`streamlit_app.py`**
    
    **역할**
    
    - **Home / Chatbot** 분리 UI.
    - Home: 가맹점명 검색 → 선택 → 대시보드 렌더(`dashboard.py` 직접 사용).
    - Chatbot: 가맹점 맥락 없이 독립, “🧹 새 대화 시작”으로 히스토리 초기화.
    - LLM 응답 하단에 **웹 출처 블록(expander)** 렌더.
    
    **사이드바**
    
    - 메뉴 라디오(Home/Chatbot), 디버그 정보(Thread ID/메시지 수/provider)
    
    **데이터 경로**
    
    - `./data/franchise_data.csv`, `./data/biz_area.csv`, `./data/admin_dong.csv`
- **`local_test.py`**
    
    **역할**
    
    - CLI에서 파이프라인 점검.
    - 결과에 **웹 스니펫/메타** 상위 3개를 요약 출력.
    
    **출력 항목**
    
    - 상태/Intent/Store ID
    - 최종 응답(앞 N자)
    - 액션 플랜(상위 3개)
    - 웹 출처: `title · source · date + url`, snippet 일부
</aside>