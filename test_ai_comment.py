import asyncio
from browser_automation import NaverNeighborBot
from comment_ai import CommentGenerator

GEMINI_API_KEY = 'AIzaSyBHcVrzgI0O8Cq0K3Bv3uPzciBVA8DElR4'
TARGET_ID = 'lizidemarron'

async def test_ai_comment():
    bot = NaverNeighborBot()

    try:
        await bot.start_browser()

        if not await bot.check_login_status():
            if not await bot.login('test_wang', 'a0215620$$'):
                print("로그인 실패 - 30초 내 수동 로그인")
                await asyncio.sleep(30)

        print("\n=== 1. 최신글 logNo 추출 ===")
        log_no = await bot.get_latest_post_log_no(TARGET_ID)
        if not log_no:
            print("FAIL: logNo 추출 실패")
            return
        print(f"PASS: logNo = {log_no}")

        print("\n=== 2. 글 내용 추출 ===")
        content = await bot.get_post_content(TARGET_ID, log_no)
        print(f"제목: {content['title']}")
        print(f"본문 (앞 300자): {content['body'][:300]}")

        print("\n=== 3. Gemini AI 댓글 생성 ===")
        generator = CommentGenerator(GEMINI_API_KEY)
        ai_comment = generator.generate(content['title'], content['body'])
        if not ai_comment:
            print("FAIL: AI 댓글 생성 실패")
            return
        print(f"생성된 댓글: '{ai_comment}'")

        print("\n=== 4. 댓글 작성 ===")
        result = await bot.write_comment(TARGET_ID, log_no, ai_comment)
        if result:
            print(f"PASS: AI 댓글 작성 성공!")
        else:
            print("FAIL: 댓글 작성 실패")

        print("\n브라우저를 30초간 유지합니다. 댓글 확인하세요.")
        await asyncio.sleep(30)

    finally:
        await bot.close_browser()

asyncio.run(test_ai_comment())
