# [1021] Guide node guide (이지민)

## General Node 프로세스

---

“그외의 목적 (일반 Q&A + 사례 탐색 + 트렌드 설명 + 전략 조언)"

- 가게 현황에 대한 질문
- 잘 나가는 마케팅 사례
- 잘 나가는 가게의 특징
- 최신 마케팅 트렌드
- 기타 전략 조언

```python
입력 state (user_query, store_id?, web_snippets?)
    ↓
STEP 1: 가맹점 탐지(resolve_store) — store_id 없을 때만
    ↓
STEP 2: Metrics 로드(main / strategy / general)
    ↓
STEP 3: 프롬프트 생성(웹 참고 정보 포함 가능)
    ↓
STEP 4: LLM 호출(append_sources_in_text 옵션에 따라 본문에 출처 부착 여부 결정)
    ↓
출력 state(final_response, metrics, web_snippets, need_clarify=False, error=None)
```

> **Case 1 (store + metrics 있음)**
> 
> 
> `resolve_store` → `load_store_and_area_data` → `build_main/strategy/general_metrics` →
> 
> 프롬프트에 지표 JSON 넣고 데이터 근거형 조언 생성.
> 

> **Case 2 (store 없음 = metrics도 없음)**
> 
> 
> `resolve_store` 후에도 `store_id` 없으면 메트릭 로드 생략 →
> 
> 프롬프트가 “웹 참고 정보 + 일반 마케팅 포맷”으로 구성되어 일반 마케팅 + 웹 검색 근거로 답변.
> 
1. (필요 시) `resolve_store`로 `store_id` 확정
2. `store_id` 있으면 메트릭 로드: `main` → `strategy(옵션)` → `general(옵션)`
3. 메트릭/웹스니펫 포함해 프롬프트 구성
4. LLM 호출 → `final_response` 저장 (+ `web_snippets`는 UI에서만 사용)
    
    → 출력: `final_response`, `metrics(있으면)`, `web_snippets`, `need_clarify=False`, `error=None`
    

## General Metrics 프로세스

---

입력: `store_id`

1. `load_store_and_area_data`로 `store_data`/`bizarea_data` 로드
2. 경쟁력 4개: 업종매출지수 백분위, 상권 내 매출순위 비율, 업종매출 편차, 업종 내 해지 비중
3. 상권환경 2개(있으면): 유사 업종 점포 수, 폐업률
4. NaN 제거 후 `{ "general_metrics": {...}, "yyyymm": "YYYYMM" }` 반환