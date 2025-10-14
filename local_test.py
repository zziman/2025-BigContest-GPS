# -*- coding: utf-8 -*-
"""
로컬 테스트: CLI에서 그래프 실행 (실제 데이터 기반)
"""
import os
os.environ['GRPC_VERBOSITY'] = 'ERROR'
os.environ['GRPC_TRACE'] = ''

from my_agent.utils.adapters import run_one_turn

def main():
    print("=" * 60)
    print("2025 빅콘테스트 - 로컬 테스트")
    print("=" * 60)
    
    # ✅ 실제 존재하는 가맹점명으로 테스트
    test_cases = [
        {
            "store_name": "호남",  # 호남* (한식-육류/고기)
            "query": "재방문을 늘리려면 어떻게 해야 할까요?"
        },
        {
            "store_name": "본죽",  # 본죽* (죽 전문점)
            "query": "SNS 마케팅 전략 알려줘"
        },
        {
            "store_name": "카페",  # 카페* (카페)
            "query": "우리 가게 문제점이 뭐야?"
        },
        {
            "store_name": "교촌",  # 교촌****** (치킨)
            "query": "재방문율을 높이는 방법은?"
        }
    ]
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n[테스트 {i}] 가게: {test['store_name']}")
        print(f"질문: {test['query']}")
        print("-" * 60)
        
        try:
            result = run_one_turn(
                user_query=test['query'],
                store_name=test['store_name'],
                thread_id=f"test_{i}"
            )
            
            print(f"상태: {result['status']}")
            print(f"Intent: {result.get('intent', 'N/A')}")
            print(f"Store ID: {result.get('store_id', 'N/A')}")
            
            if result['status'] == 'ok':
                print("\n✅ 성공!")
                
                card = result.get('card', {})
                if card:
                    print(f"\n[가맹점 정보]")
                    print(f"  이름: {card.get('mct_name')}")
                    print(f"  업종: {card.get('industry')}")
                    print(f"  지역: {card.get('district')}")
                    print(f"  재방문율: {card.get('repeat_rate', 0)*100:.1f}%")
                    print(f"  배달비중: {card.get('delivery_share', 0)*100:.1f}%")
                
                response = result.get('final_response', '(없음)')
                print(f"\n[최종 응답] (앞 200자)")
                print(response[:200] + "..." if len(response) > 200 else response)
                
                actions = result.get('actions', [])
                if actions:
                    print(f"\n[액션 플랜] {len(actions)}개")
                    for action in actions[:3]:
                        print(f"  {action.get('priority', '-')}. {action.get('title')} ({action.get('category')})")
            
            elif result['status'] == 'need_clarify':
                candidates = result.get('store_candidates', [])
                print(f"\n⚠️  후보 확정 필요: {len(candidates)}개")
                for cand in candidates[:5]:
                    print(f"  - {cand.get('가맹점명', 'N/A')} ({cand.get('가맹점_지역', 'N/A')}, {cand.get('업종', 'N/A')})")
            
            else:
                print(f"\n❌ 에러: {result.get('error', '알 수 없는 오류')}")
        
        except Exception as e:
            print(f"\n❌ 예외 발생: {e}")
            import traceback
            traceback.print_exc()
        
        print("=" * 60)


if __name__ == "__main__":
    main()