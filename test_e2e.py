"""
E2E 테스트: 서로이웃 신청 → 성공 계정 AI 댓글 전체 플로우
GUI 없이 browser_automation.py의 run()을 직접 호출하여 전체 파이프라인 검증
"""
import asyncio
from browser_automation import NaverNeighborBot

# 테스트 설정
BLOG_URL = 'https://blog.naver.com/lizidemarron/224165855125'
USER_ID = 'test_wang'
PASSWORD = 'a0215620$$'
GEMINI_API_KEY = 'AIzaSyBHcVrzgI0O8Cq0K3Bv3uPzciBVA8DElR4'

logs = []

def log_callback(msg):
    logs.append(msg)
    print(f"  >> {msg}")

def progress_callback(current, total):
    print(f"  [진행률] {current}/{total}")

async def test_e2e():
    print("=" * 60)
    print("E2E 테스트: 서로이웃 신청 → AI 댓글 전체 플로우")
    print("=" * 60)

    bot = NaverNeighborBot(log_callback=log_callback)

    try:
        await bot.run(
            blog_url=BLOG_URL,
            user_id=USER_ID,
            password=PASSWORD,
            progress_callback=progress_callback,
            enable_comment=True,
            comment_text="안녕하세요! 글 잘 봤습니다 :)",
            gemini_api_key=GEMINI_API_KEY
        )
    except Exception as e:
        print(f"\n❌ E2E 테스트 실패: {e}")
        return

    print("\n" + "=" * 60)
    print("E2E 테스트 결과 분석")
    print("=" * 60)

    # 결과 분석
    login_ok = any("로그인 성공" in l for l in logs)
    accounts_found = any("계정" in l and "발견" in l for l in logs)
    neighbor_done = any("서로이웃 신청 완료" in l for l in logs)
    comment_done = any("댓글 작성 완료" in l for l in logs)
    ai_comment = any("AI 댓글 생성" in l for l in logs)
    no_accounts = any("이웃추가 가능한 계정이 없습니다" in l for l in logs)

    print(f"  로그인: {'✅ PASS' if login_ok else '❌ FAIL'}")
    print(f"  계정 추출: {'✅ PASS' if accounts_found or no_accounts else '❌ FAIL'}")
    print(f"  서로이웃 신청: {'✅ PASS' if neighbor_done else '⚠️ SKIP (계정 없음)' if no_accounts else '❌ FAIL'}")

    if no_accounts:
        print(f"\n⚠️ 이웃추가 가능한 계정이 없어 댓글 테스트 불가")
        print(f"   (이미 모든 계정에 이웃 신청 완료된 상태)")
        print(f"\n✅ E2E 파이프라인 정상 동작 확인 (계정 없음으로 댓글 단계 미도달)")
    else:
        print(f"  AI 댓글 생성: {'✅ PASS' if ai_comment else '⚠️ N/A'}")
        print(f"  댓글 작성: {'✅ PASS' if comment_done else '❌ FAIL'}")

        if neighbor_done and comment_done:
            print(f"\n✅ E2E 전체 플로우 성공!")
        elif neighbor_done:
            print(f"\n⚠️ 서로이웃 신청은 성공, 댓글 작성은 실패/스킵")

    print("\n전체 로그:")
    for l in logs:
        print(f"  {l}")

asyncio.run(test_e2e())
