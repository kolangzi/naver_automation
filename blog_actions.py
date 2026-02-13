import asyncio
import re
from typing import Callable, Optional


async def click_sympathy_on_frame(main_frame, log: Callable[[str], None]) -> bool:
    try:
        like_face_btn = await main_frame.query_selector('.my_reaction a.u_likeit_button._face')
        if not like_face_btn:
            log("  공감 버튼을 찾지 못함 - 스킵")
            return False

        btn_class = await like_face_btn.get_attribute('class') or ''
        if ' on' in btn_class or btn_class.endswith(' on'):
            log("  이미 공감한 글 - 스킵")
            return True

        await like_face_btn.evaluate('el => el.click()')
        await asyncio.sleep(1)

        like_btn = await main_frame.query_selector('.my_reaction a.u_likeit_list_button._button[data-type="like"]')
        if not like_btn:
            log("  공감(하트) 옵션을 찾지 못함 - 스킵")
            return False

        aria_pressed = await like_btn.get_attribute('aria-pressed')
        if aria_pressed == 'true':
            log("  이미 공감한 글 - 스킵")
            return True

        await like_btn.evaluate('el => el.click()')
        await asyncio.sleep(2)

        log("  공감 클릭 완료!")
        return True

    except Exception as e:
        log(f"  공감 클릭 오류: {str(e)[:80]}")
        return False


async def get_latest_post_log_no(page, target_id: str, log: Callable[[str], None]) -> Optional[str]:
    post_list_url = f'https://blog.naver.com/PostList.naver?blogId={target_id}&categoryNo=0&from=postList'
    log(f"[{target_id}] 최신글 목록 접속...")
    await page.goto(post_list_url)
    from utils import HumanDelay
    await HumanDelay.page_load()
    await asyncio.sleep(3)

    for f in page.frames:
        match = re.search(r'sympathyFrm(\d+)', f.name)
        if match:
            log_no = match.group(1)
            log(f"[{target_id}] 최신 글 logNo: {log_no}")
            return log_no

    js_log_nos = await page.evaluate("""
        () => {
            const results = [];
            document.querySelectorAll('iframe').forEach(f => {
                const nm = f.name.match(/\\d{10,}/);
                if (nm) results.push(nm[0]);
            });
            return [...new Set(results)];
        }
    """)
    if js_log_nos:
        log(f"[{target_id}] 최신 글 logNo: {js_log_nos[0]}")
        return js_log_nos[0]

    log(f"[{target_id}] logNo를 찾지 못함")
    return None


async def get_post_content(page, target_id: str, log_no: str,
                           log: Callable[[str], None], get_main_frame) -> tuple:
    post_url = f'https://blog.naver.com/{target_id}/{log_no}'
    log(f"[{target_id}] 글 접속: {post_url}")
    await page.goto(post_url)
    from utils import HumanDelay
    await HumanDelay.page_load()
    await asyncio.sleep(3)

    main_frame = get_main_frame()
    if not main_frame:
        return {'title': '', 'body': ''}, None

    title = ''
    title_el = await main_frame.query_selector('.se-title-text')
    if title_el:
        title = await title_el.inner_text()

    body = ''
    body_el = await main_frame.query_selector('.se-main-container')
    if body_el:
        body = await body_el.inner_text()

    log(f"[{target_id}] 제목: {title[:50]}")
    return {'title': title.strip(), 'body': body.strip()[:1000]}, main_frame


async def check_my_comment_exists(main_frame, my_blog_id: str) -> bool:
    existing_nicks = await main_frame.query_selector_all(".u_cbox_nick")
    if not existing_nicks:
        comment_btn = await main_frame.query_selector("a._cmtList")
        if comment_btn:
            await comment_btn.evaluate("el => el.click()")
            await asyncio.sleep(3)

    comment_nicks = await main_frame.query_selector_all(".u_cbox_nick")
    for nick_el in comment_nicks:
        try:
            nick_text = (await nick_el.inner_text()).strip()
            if my_blog_id.lower() in nick_text.lower():
                return True
        except:
            continue
    comment_authors = await main_frame.query_selector_all(".u_cbox_info a[href*='blog.naver.com']")
    for author_el in comment_authors:
        try:
            href = await author_el.get_attribute("href") or ""
            m = re.search(r"blog\.naver\.com/([^/?&#]+)", href)
            if m and m.group(1).lower() == my_blog_id.lower():
                return True
        except:
            continue
    return False


async def write_comment(main_frame, target_id: str, comment: str,
                        log: Callable[[str], None]) -> bool:
    try:
        comment_write_btn = await main_frame.query_selector('a:has-text("댓글 쓰기")')
        if not comment_write_btn:
            comment_write_btn = await main_frame.query_selector('a:has-text("댓글")')
        if comment_write_btn:
            await comment_write_btn.evaluate("el => el.click()")
            await asyncio.sleep(3)

        placeholder = await main_frame.query_selector(".u_cbox_guide")
        if placeholder:
            await placeholder.evaluate("el => el.click()")
            await asyncio.sleep(1)

        comment_input = await main_frame.query_selector('div[contenteditable="true"].u_cbox_text')
        if not comment_input:
            comment_input = await main_frame.query_selector('div[contenteditable="true"]')
        if not comment_input:
            log(f"  [{target_id}] 댓글 입력 필드 못 찾음 - skip")
            return False

        await comment_input.evaluate('''(el, text) => {
            el.focus();
            el.innerText = text;
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
            el.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true }));
        }''', comment)
        await asyncio.sleep(1)

        register_btn = await main_frame.query_selector(".u_cbox_btn_upload")
        if not register_btn:
            register_btn = await main_frame.query_selector('button:has-text("등록")')
        if not register_btn:
            log(f"  [{target_id}] 등록 버튼 못 찾음 - skip")
            return False

        await register_btn.evaluate("el => el.click()")
        await asyncio.sleep(3)
        log(f"  [{target_id}] 댓글 등록 완료: '{comment[:30]}'")
        return True

    except Exception as e:
        log(f"  [{target_id}] 댓글 오류: {str(e)[:80]}")
        return False
