# -*- coding: utf-8 -*-
"""
로컬 테스트: CLI에서 그래프 실행 (실제 데이터 기반)
- Streamlit 변경 사항 반영:
  * web_snippets / web_meta 출력
  * need_clarify 케이스 가독성 개선
  * 결과 요약 정리
"""
import os
os.environ['GRPC_VERBOSITY'] = 'ERROR'
os.environ['GRPC_TRACE'] = ''

from typing import List, Dict, Any, Optional
from my_agent.utils.adapters import run_one_turn


def hr(ch='-', n=60):
    print(ch * n)


def clip(text: str, n: int = 300) -> str:
    text = (text or "").strip()
    return text if len(text) <= n else text[:n] + "..."


def print_card_short(card: Dict[str, Any]):
    if not card:
        return
    print("\n[가맹점 요약]")
    print(f"  이름: {card.get('mct_name')}")
    print(f"  업종: {card.get('industry')}")
    print(f"  지역: {card.get('district')}")
    try:
        rr = float(card.get('repeat_rate', 0) or 0) * 100
        ds = float(card.get('delivery_share', 0) or 0) * 100
        print(f"  재방문율: {rr:.1f}%")
        print(f"  배달비중: {ds:.1f}%")
    except Exception:
        pass


def print_actions(actions: List[Dict[str, Any]], k: int = 3):
    if not actions:
        return
    print(f"\n[액션 플랜] 상위 {min(k, len(actions))}개")
    for a in actions[:k]:
        p = a.get('priority', '-')
        t = a.get('title', 'N/A')
        c = a.get('category', '-')
        why = a.get('why', '')
        print(f"  {p}. {t} ({c})")
        if why:
            print(f"     - 이유: {why}")


def print_sources(snips: Optional[List[Dict[str, Any]]],
                  meta: Optional[Dict[str, Any]],
                  k: int = 3):
    snips = snips or []
    if not snips:
        return
    provider = (meta or {}).get("provider_used", "auto")
    q = (meta or {}).get("query", "")
    print(f"\n[웹 출처] provider={provider}" + (f", query=\"{q}\"" if q else ""))
    for s in snips[:k]:
        title = s.get("title") or "(제목 없음)"
        src = s.get("source") or ""
        date = s.get("published_at") or ""
        url = s.get("url") or ""
        line = f" - {title}"
        if src:
            line += f" · {src}"
        if date:
            line += f" · {date}"
        print(line)
        if url:
            print(f"    {url}")
        snip = (s.get("snippet") or "").strip()
        if snip:
            print(f"    └ {clip(snip, 160)}")


def main():
    hr('=')
    print("2025 빅콘테스트 - 로컬 테스트")
    hr('=')

    # ✅ 실제 존재하는 가맹점명으로 테스트
    test_cases = [
        {"store_name": "호남",  "query": "재방문을 늘리려면 어떻게 해야 할까요?"},
        {"store_name": "본죽",  "query": "SNS 마케팅 전략 알려줘"},
        {"store_name": "카페",  "query": "우리 가게 문제점이 뭐야?"},
        {"store_name": "교촌",  "query": "재방문율을 높이는 방법은?"},
        # 가맹점명 없이 질의만 주는 케이스도 확인
        {"store_name": None,    "query": "본죽 문제점이 뭐야?"},
    ]

    for i, test in enumerate(test_cases, 1):
        hr()
        print(f"[테스트 {i}]")
        print(f"가게: {test.get('store_name') or '(미지정)'}")
        print(f"질문: {test['query']}")
        hr()

        try:
            result = run_one_turn(
                user_query=test['query'],
                store_name=test.get('store_name'),
                thread_id=f"test_{i}"
            )

            status = result.get('status', 'ok')
            intent = result.get('intent') or result.get('state', {}).get('intent', 'N/A')
            store_id = result.get('store_id') or result.get('state', {}).get('store_id', 'N/A')

            print(f"상태: {status}")
            print(f"Intent: {intent}")
            print(f"Store ID: {store_id}")

            if status == 'ok':
                print("\n✅ 성공")

                # (선택) 카드 요약: 어댑터가 card / card_data 어디에 넣는지에 따라 둘 다 확인
                card = result.get('card') or result.get('card_data') or result.get('state', {}).get('card_data', {})
                print_card_short(card)

                # 최종 응답
                response = result.get('final_response') or result.get('state', {}).get('final_response', '')
                print("\n[최종 응답] (앞 400자)")
                print(clip(response, 400))

                # 액션
                actions = result.get('actions') or result.get('state', {}).get('actions') or []
                print_actions(actions, k=3)

                # 웹 출처
                web_snips = result.get("web_snippets") or result.get("state", {}).get("web_snippets")
                web_meta  = result.get("web_meta") or result.get("state", {}).get("web_meta")
                print_sources(web_snips, web_meta, k=3)

            elif status == 'need_clarify':
                print("\n⚠️ 후보 확정 필요")
                candidates = result.get('store_candidates', [])
                if not candidates:
                    candidates = result.get('state', {}).get('store_candidates', []) or []
                print(f"- 후보 수: {len(candidates)}")
                for cand in candidates[:8]:
                    name = cand.get('가맹점명') or cand.get('mct_name') or cand.get('name') or 'N/A'
                    area = cand.get('가맹점_지역') or cand.get('district') or cand.get('area') or '-'
                    ind  = cand.get('업종') or cand.get('industry') or '-'
                    print(f"  · {name} ({area}, {ind})")

            else:
                print(f"\n❌ 에러: {result.get('error', '알 수 없는 오류')}")

        except Exception as e:
            print(f"\n❌ 예외 발생: {e}")
            import traceback
            traceback.print_exc()

    hr('=')
    print("테스트 종료")
    hr('=')


if __name__ == "__main__":
    main()
