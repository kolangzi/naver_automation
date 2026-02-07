import asyncio
from browser_automation import NaverNeighborBot

async def test_integration():
    bot = NaverNeighborBot()

    try:
        await bot.start_browser()

        if not await bot.check_login_status():
            if not await bot.login('test_wang', 'a0215620$$'):
                print("로그인 실패 - 30초 내 수동 로그인")
                await asyncio.sleep(30)

        target_id = 'lizidemarron'

        print("\n=== get_latest_post_log_no 테스트 ===")
        log_no = await bot.get_latest_post_log_no(target_id)
        if not log_no:
            print("FAIL: logNo를 찾지 못함")
            return
        print(f"PASS: logNo = {log_no}")

        print("\n=== get_post_content 테스트 ===")
        content = await bot.get_post_content(target_id, log_no)
        print(f"제목: {content['title'][:80]}")
        print(f"본문: {content['body'][:200]}")
        if content['title']:
            print("PASS: 글 내용 추출 성공")
        else:
            print("WARN: 제목이 비어있음")

        print("\n=== write_comment 테스트 ===")
        result = await bot.write_comment(target_id, log_no, "통합 테스트 댓글입니다!")
        if result:
            print("PASS: 댓글 작성 성공!")
        else:
            print("FAIL: 댓글 작성 실패")

        print("\n브라우저를 30초간 유지합니다. 댓글 확인하세요.")
        await asyncio.sleep(30)

    finally:
        await bot.close_browser()

asyncio.run(test_integration())
