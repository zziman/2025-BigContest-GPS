# [1021] DuckDB guide (이지민)

- [ ]  `scripts/build_duckdb.py` 구축 스크립트
- [ ]  `test_duckdb.py` DuckDB 통합 테스트

## DuckDB 구축

---

| CSV | DuckDB |
| --- | --- |
| 매번 전체 CSV 파일을 읽음 (느림) | 필요한 부분만 디스크에서 읽음 |
| 모든 데이터를 메모리에 올림 (메모리 낭비) | 인덱스 활용 → 빠른 검색 |
| 필터링/조인 시 전체 스캔 필요 | SQL 최적화 엔진 사용 |
| 인덱스 없음 → 검색 느림 | 메모리 효율적  |

```python
data.duckdb (52MB)
│
├─ [franchise 테이블] (72,255 rows)
│  ├─ 가맹점_구분번호 (인덱스 ✓)
│  ├─ 기준년월 (인덱스 ✓)
│  ├─ 가맹점명 (인덱스 ✓)
│  ├─ 업종
│  ├─ 상권_지리
│  └─ ... (86개 컬럼)
│  └─ [복합 인덱스]
│     ├─ (가맹점_구분번호, 기준년월)
│     └─ (기준년월, 상권_지리, 업종) ← 조인용
│
└─ [biz_area 테이블] (36,709 rows)
   ├─ 기준년월
   ├─ 업종
   ├─ 상권_지리
   ├─ 당월_매출_금액
   └─ ... (179개 컬럼)
   └─ [복합 인덱스]
      └─ (기준년월, 상권_지리, 업종) ← 조인용
```

```python
### load_bizarea_data() 함수
```
franchise 테이블          biz_area 테이블
┌─────────────┐          ┌──────────────┐
│ 202301      │          │ 202301       │
│ 왕십리      │          │ 왕십리       │
│ 한식-죽     │          │ 한식-죽      │
│             │          │ 상권코드: A  │ ← ROW_NUMBER() = 1 ⭐
└─────────────┘          ├──────────────┤
                         │ 202301       │
                         │ 왕십리       │
                         │ 한식-죽      │
                         │ 상권코드: D  │ ← ROW_NUMBER() = 2 (버림)
                         └──────────────┘

결과: 1개 row만
┌─────────────┬──────────────┐
│ franchise   │ biz_area (A) │
└─────────────┴──────────────┘
```

```python
📌 Step 1: 설정 파일 수정
   └─ my_agent/utils/config.py
      ├─ DUCKDB_PATH 추가
      └─ USE_DUCKDB 플래그 추가 (line 80에서 Duck DB/CSV 사용 가능) 

📌 Step 2: DuckDB 구축 스크립트 작성
   └─ scripts/build_duckdb.py 생성
      ├─ CSV 파일 검증
      ├─ DuckDB 테이블 생성 (franchise, biz_area)
      ├─ 인덱스 생성 (검색 최적화)
      └─ 데이터 검증 및 성능 테스트

📌 Step 3: DuckDB 구축 실행 및 검증
   ├─ python scripts/build_duckdb.py
   └─ 검증 결과:
      ✅ franchise: 72,255 rows, 91 columns
      ✅ biz_area: 36,709 rows, 183 columns
      ✅ 공통 컬럼 (기준년월, 업종, 상권_지리) 결측치 0%
      ✅ 조인 성공률: 208.9%
      ✅ 쿼리 속도: 7-16ms

📌 Step 4: MCP Tools 수정
   └─ mcp/tools.py 전면 개편
      ├─ DuckDB 연결 함수 추가
      ├─ 행정동(region) 관련 코드 완전 제거
      ├─ CSV fallback 지원
      └─ 공통 컬럼 기반 매칭

📌 Step 5: 통합 테스트
   └─ test_duckdb.py 실행
      ✅ 가맹점 검색: 8개 결과 (0.01초)
      ✅ 가맹점 데이터 로드: 정상
      ✅ 상권 데이터 조회: 조인 성공

📌 Step 6: Dashboard 수정
   └─ dashboard.py
      ├─ DuckDB 우선 로딩
      └─ CSV fallback 지원

📌 Step 7: 의존성 정리
   └─ my_agent/utils/tools.py
      └─ load_region_data 함수 제거
```

| Phase | DuckDB | CSV | 차이(CSV−DuckDB) | 변화율 |
| --- | --- | --- | --- | --- |
| Router | 2.2s | 2.2s | −0.0s | −2.0% |
| Web search | 18.5s | 24.6s | **+6.1s** | **+32.8%** |
| Load store+area | 0.38s | 0.65s | **+0.27s** | +71.8% |
| Main metrics | 0.019s | 0.012s | −0.007s | −35.1% |
| Strategy metrics | 0.018s | 0.012s | −0.006s | −34.9% |
| General metrics | 0.025s | 0.012s | −0.013s | −52.3% |
| LLM invoke | **45.7s** | **34.2s** | **−11.4s** | **−25.0%** |
- LLM invoke는 LangChain → Google Generative AI API 요청이라 DuckDB와 완전히 독립된 구간
    - 입력 프롬프트 길이 + 모델 서버 상태에서 의해서 결정되고
    - 같은 모델/프롬프트를 5번 호출해도 ±10초 차이 나는 게 흔하다고 함