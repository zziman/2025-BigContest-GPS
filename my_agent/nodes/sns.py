# my_agent/nodes/sns.py

# -*- coding: utf-8 -*-
"""
SNSNode - SNS 채널 추천 및 홍보안 작성 노드
- 방문 고객 특성 분석
- 적합한 SNS 채널 추천
- 구체적인 운영 전략 및 예시 문구 제안
"""

from typing import Dict, Any
from langchain_google_genai import ChatGoogleGenerativeAI

from my_agent.utils.config import GOOGLE_API_KEY, LLM_MODEL, LLM_TEMPERATURE
from my_agent.utils.tools import resolve_store, load_store_and_area_data
from my_agent.utils.postprocess import postprocess_response, format_web_snippets

from my_agent.metrics.main_metrics import build_main_metrics
from my_agent.metrics.strategy_metrics import build_strategy_metrics
from my_agent.metrics.sns_metrics import build_sns_metrics



# SNS 채널별 특성 가이드
SNS_CHANNEL_GUIDE = {
    "Instagram": {
        "주요_타깃": "20~30대, 여성 고객 비중 높음",
        "콘텐츠_특성": "비주얼 중심(사진/짧은 영상), 해시태그 기반 노출",
        "적합한_업종": "비주얼이 중요한 업종(카페, 디저트, 레스토랑)",
        "적합한_고객_특성": "젊은층, 트렌드에 민감, 감성 소비",
        "운영_난이도": "중간 (꾸준한 비주얼 콘텐츠 제작 필요)",
        "비용": "무료 (광고 집행 시 유료)",
    },
    "TikTok": {
        "주요_타깃": "10~20대, MZ세대",
        "콘텐츠_특성": "짧은 영상(15~60초), 바이럴 가능성 높음, 참여형 콘텐츠",
        "적합한_업종": "재미/독특한 메뉴, 챌린지 가능한 아이템",
        "적합한_고객_특성": "젊은층, 유행 민감, 빠른 확산 선호",
        "운영_난이도": "높음 (영상 편집 스킬 필요, 트렌드 파악 중요)",
        "비용": "무료 (광고 집행 시 유료)",
    },
    "Naver Place": {
        "주요_타깃": "전 연령대 (특히 30~50대)",
        "콘텐츠_특성": "검색 기반 노출, 리뷰/별점 중심, 위치 정보",
        "적합한_업종": "모든 업종 (특히 지역 기반 매장)",
        "적합한_고객_특성": "거주 고객, 직장인, 검색으로 매장 찾는 고객",
        "운영_난이도": "낮음 (기본 정보 등록 후 리뷰 관리)",
        "비용": "무료 (스마트플레이스 광고 시 유료)",
    },
    "Facebook": {
        "주요_타깃": "40~60대, 중장년층",
        "콘텐츠_특성": "긴 텍스트+사진, 커뮤니티 기반, 이벤트 공유",
        "적합한_업종": "중장년층 타깃 업종, 지역 커뮤니티 밀착형",
        "적합한_고객_특성": "단골 고객, 거주 고객, 커뮤니티 활동 활발",
        "운영_난이도": "낮음 (텍스트 중심, 상대적으로 부담 적음)",
        "비용": "무료 (광고 집행 시 유료)",
    },
    "YouTube": {
        "주요_타깃": "전 연령대 (특히 20~40대)",
        "콘텐츠_특성": "긴 영상 콘텐츠, 스토리텔링, 검색 노출 우수",
        "적합한_업종": "브랜드 스토리가 강한 업종, 요리 과정 공개 가능",
        "적합한_고객_특성": "브랜드에 관심 많은 고객, 깊이 있는 정보 선호",
        "운영_난이도": "높음 (영상 제작 시간/비용 소요)",
        "비용": "무료 (제작 비용 별도, 광고 집행 시 유료)",
    },
    "카카오톡 채널": {
        "주요_타깃": "전 연령대 (특히 40대 이상)",
        "콘텐츠_특성": "1:1 메시지, 쿠폰/이벤트 발송, 단골 관리",
        "적합한_업종": "모든 업종 (단골 고객 관리 필수 업종)",
        "적합한_고객_특성": "단골 비중 높음, 재방문율 중요한 매장",
        "운영_난이도": "낮음 (메시지 발송 중심)",
        "비용": "무료 (메시지 발송량에 따라 유료)",
    },
    "배달앱 리뷰 관리": {
        "주요_타깃": "배달 이용 고객 (전 연령대)",
        "콘텐츠_특성": "리뷰 답글, 별점 관리, 프로모션 설정",
        "적합한_업종": "배달 가능 업종 (치킨, 중식, 분식 등)",
        "적합한_고객_특성": "배달 매출 비중 30% 이상",
        "운영_난이도": "낮음 (리뷰 답글 중심)",
        "비용": "무료 (배달 수수료 별도)",
    },
    "Google Maps": {
        "주요_타깃": "전 연령대 (특히 외국인, 유동 고객)",
        "콘텐츠_특성": "위치 기반 검색, 리뷰, 사진",
        "적합한_업종": "관광지/유동인구 많은 지역 매장",
        "적합한_고객_특성": "유동인구 고객 비중 높음, 관광객 많은 지역",
        "운영_난이도": "낮음 (기본 정보 등록 후 리뷰 관리)",
        "비용": "무료 (광고 집행 시 유료)",
    },
}

class SNSNode:
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model=LLM_MODEL,
            google_api_key=GOOGLE_API_KEY,
            temperature=LLM_TEMPERATURE)

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        user_query = state.get("user_query", "").strip()
        web_snippets = state.get("web_snippets", [])

        # 1. 항상 store 탐지 시도
        if not state.get("store_id"):
            state = resolve_store(state)
        
        store_id = state.get("store_id")

        # 2. store 있는 경우에만 metrics 생성
        metrics: Dict[str, Any] = {}
        if state.get("store_id"):
            # 가게/상권 데이터 적재
            state = load_store_and_area_data(state, include_region=False, latest_only=True)

            store_id = state["store_id"]
            # 각 지표 빌드 (실패해도 나머지 진행)
            try:
                res_main = build_main_metrics(store_id)  # 예: {"main_metrics": {...}, "상권_단위_정보": {...}}
                if isinstance(res_main, dict):
                    if "main_metrics" in res_main and res_main["main_metrics"]:
                        metrics["main_metrics"] = res_main["main_metrics"]
                    if "상권_단위_정보" in res_main and res_main["상권_단위_정보"]:
                        metrics["상권_단위_정보"] = res_main["상권_단위_정보"]
            except Exception:
                pass

            try:
                m_strategy = build_strategy_metrics(store_id), "strategy_metrics"
                if m_strategy:
                    metrics["strategy_metrics"] = m_strategy
            except Exception:
                pass

            try:
                m_sns = build_sns_metrics(store_id), "sns_metrics"
                if m_sns:
                    metrics["sns_metrics"] = m_sns
            except Exception:
                pass

        state["metrics"] = metrics if metrics else None
        # 웹 참고 정보 포맷 적용
        web_section = ""
        if web_snippets:
            web_section = f"\n### 웹 참고 정보\n{format_web_snippets(web_snippets)}\n"


        # 3. Prompt 구성(JSON 구조로 그대로 포함)
        prompt = f"""
# 당신은 SNS 마케팅 전문가입니다  
주어진 정보를 바탕으로 **데이터 기반 SNS 채널 추천과 실행 가능한 홍보 전략**을 제시하세요.

---

## 질문
{user_query}

## 가게 정보
{state.get("user_info")}

## 데이터 지표
{state.get("metrics")}

## SNS 채널별 특성 (참고용)
{SNS_CHANNEL_GUIDE}

## 웹 참고 정보
{format_web_snippets(web_snippets)}

---

## 출력 형식 
### 1. 현재 상황 요약  
- 데이터를 바탕으로 매장의 현황과 주요 특징을 2~3문장으로 정리  

### 2. 핵심 데이터 분석  
- 핵심 지표 2~3개를 근거로 분석 (수치 포함)

### 3. 전략 제안  
- 가게 데이터와 가장 잘 맞는 채널을 우선 순위별로 2~3개 추천   
- 각 채널별 구체적인 운영 전략 제시 

### 4. 기대 효과 
- 전략 실행 시 기대할 수 있는 지표 개선이나 매출 효과 설명

---

## 작성 규칙
1. 제공된 데이터를 기반으로 **고객 특성(연령대, 방문 패턴, 객단가 등)** 분석  
2. 위의 SNS 채널 특성을 참고하여 **가게 데이터와 가장 적합한 채널을 우선순위별로 3~4개 추천**
   - 각 채널별 **추천 근거** 명시  
   - 각 채널별 **운영 전략** 제시 (업로드 주기, 콘텐츠 유형, 해시태그 전략 등)  
   - 각 채널별 **기대 효과** 명시  
3. **실제 사용 가능한 홍보 문구**를 2~3개 제안 (해시태그 포함)  
4. 일반론 금지 — 매장 데이터 기반으로만 전략 제시  
5. 가게 데이터가 부족할 경우 웹 참고 정보를 바탕으로 일반적인 조언 제시

        """
        
    
        # LLM 호출
        raw_response = self.llm.invoke(prompt).content

        # 후처리 적용
        final_output = postprocess_response(
            raw_response=raw_response,
            web_snippets=web_snippets
        )

        # 결과 반환
        state["error"] = None
        state["final_response"] = final_output
        state["need_clarify"] = False  # 미정
        return state


if __name__ == "__main__":
    import sys, json

    args = sys.argv[1:]
    query = None
    store_id = None

    for i, a in enumerate(args):
        if a == "--query":
            query = args[i + 1]
        elif a == "--store":
            store_id = args[i + 1]

    if not query:
        print("사용법: python -m my_agent.nodes.sns --query '질문' [--store STORE_ID]")
        # python -m my_agent.nodes.sns --query "해당 가게의 재방문율을 높이는 전략 알려줘" --store 761947ABD9
        sys.exit(1)

    state = {"user_query": query}
    if store_id:
        state["store_id"] = store_id

    node = SNSNode()
    result = node(state)
    print(json.dumps(result, ensure_ascii=False, indent=2))
      