## 노드 디버깅 테스트하는 디버깅.py

from my_agent.utils.adapters import run_one_turn

if __name__ == "__main__":
    print("\n✅ Chatbot 테스트 시작")
    query = input("💬 질문을 입력하세요: ")
    result = run_one_turn(query)

    print("\n📌 실행 결과 ------------------------------")
    print(f"▶ 상태: {result.get('status')}")
    print(f"▶ Intent: {result.get('intent')}")

    if result.get("user_info"):
        print(f"▶ 가맹점: {result['user_info'].get('store_name')} ({result['store_id']})")
    else:
        print("▶ 가맹점 정보 없음 (웹/일반 모드)")

    print("\n--- ✅ 답변 --------------------------------")
    print(result.get("final_response"))

    if result.get("web_snippets"):
        print("\n🔎 참고한 웹 정보:")
        for snip in result["web_snippets"]:
            print(f"- {snip['title']} ({snip['url']})")


## 사용법
## python 디버깅.py 입력하고 자기 노드에 맞는 질문 입력하면 됨
## ex) 이슈면 라우터에서 이슈에 걸릴만한 질문 입력
## chat_history/default.json으로 저장되고 터미널에도 출력됨
