import re
from typing import Callable, Optional
from utils import random_sleep


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
        await random_sleep(0.8, 2.0)

        like_btn = await main_frame.query_selector('.my_reaction a.u_likeit_list_button._button[data-type="like"]')
        if not like_btn:
            log("  공감(하트) 옵션을 찾지 못함 - 스킵")
            return False

        aria_pressed = await like_btn.get_attribute('aria-pressed')
        if aria_pressed == 'true':
            log("  이미 공감한 글 - 스킵")
            return True

        await like_btn.evaluate('el => el.click()')
        await random_sleep(1.5, 3.0)

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
    await random_sleep(2.0, 4.0)

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
    await random_sleep(2.0, 4.0)

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
            await random_sleep(2.0, 4.0)

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


async def load_comments(main_frame, log: Callable[[str], None]) -> bool:
    """댓글 영역 lazy-load 트리거. 이미 로드됐으면 스킵."""
    existing = await main_frame.query_selector_all("li.u_cbox_comment")
    if existing:
        return True

    comment_btn = await main_frame.query_selector("a._cmtList")
    if comment_btn:
        await comment_btn.evaluate("el => el.click()")
        await random_sleep(2.0, 4.0)
        loaded = await main_frame.query_selector_all("li.u_cbox_comment")
        if loaded:
            log("  댓글 영역 로드 완료")
            return True

    log("  댓글을 찾지 못함")
    return False


async def _find_comment_element(main_frame, comment_no: str):
    """data-info에서 commentNo가 일치하는 li.u_cbox_comment 요소를 찾는다.
    따옴표 유무, 공백 등에 관계없이 매칭한다."""
    comments = await main_frame.query_selector_all("li.u_cbox_comment")
    for c in comments:
        data_info = await c.get_attribute("data-info") or ""
        # 다양한 포맷 대응: commentNo:'12345', commentNo: '12345', commentNo:12345
        for kv in data_info.split(","):
            kv = kv.strip()
            if ":" not in kv:
                continue
            key, val = kv.split(":", 1)
            if key.strip() == "commentNo" and val.strip().strip("'\"") == comment_no:
                return c
    return None


async def write_reply(main_frame, comment_no: str, reply_text: str,
                      log: Callable[[str], None],
                      dry_run: bool = False) -> bool:
    """특정 댓글(comment_no)에 대댓글을 작성한다.
    dry_run=True이면 요소 찾기/답글 버튼/입력 필드 검증만 하고 실제 등록은 스킵."""
    try:
        target_comment = await _find_comment_element(main_frame, comment_no)

        if not target_comment:
            await random_sleep(1.0, 2.0)
            target_comment = await _find_comment_element(main_frame, comment_no)

        if not target_comment:
            log(f"  댓글 #{comment_no} 요소 못 찾음")
            return False

        # 답글 버튼 클릭
        reply_btn = await target_comment.query_selector(".u_cbox_btn_reply")
        if not reply_btn:
            log(f"  댓글 #{comment_no} 답글 버튼 없음")
            return False

        await reply_btn.evaluate("el => el.click()")
        await random_sleep(1.5, 3.0)

        # 대댓글 입력 필드 찾기 (reply_textarea_{commentNo} 포함하는 id)
        reply_input = await main_frame.query_selector(
            f'div[contenteditable="true"][id*="reply_textarea_{comment_no}"]'
        )
        if not reply_input:
            # fallback: 답글 버튼 클릭 후 나타난 write_box 내 contenteditable
            write_boxes = await main_frame.query_selector_all(".u_cbox_write_box")
            for wb in write_boxes:
                inp = await wb.query_selector('div[contenteditable="true"].u_cbox_text')
                if inp:
                    inp_id = await inp.get_attribute("id") or ""
                    if "reply_textarea" in inp_id:
                        reply_input = inp
                        break

        if not reply_input:
            log(f"  댓글 #{comment_no} 대댓글 입력 필드 못 찾음")
            return False

        if dry_run:
            log(f"  [DRY-RUN] 댓글 #{comment_no} 검증 OK (요소/답글버튼/입력필드 모두 확인)")
            reply_btn_again = await target_comment.query_selector(".u_cbox_btn_reply")
            if reply_btn_again:
                await reply_btn_again.evaluate("el => el.click()")
                await random_sleep(0.5, 1.0)
            return True

        await reply_input.evaluate('''(el, text) => {
            el.focus();
            el.innerText = text;
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
            el.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true }));
        }''', reply_text)
        await random_sleep(0.8, 2.0)

        register_btn = await main_frame.evaluate_handle('''(el) => {
            const writeBox = el.closest('.u_cbox_write_box');
            if (writeBox) {
                return writeBox.querySelector('button.u_cbox_btn_upload');
            }
            return null;
        }''', reply_input)

        btn_element = register_btn.as_element()
        if not btn_element:
            all_upload_btns = await main_frame.query_selector_all("button.u_cbox_btn_upload")
            if len(all_upload_btns) > 1:
                btn_element = all_upload_btns[-1]
            elif all_upload_btns:
                btn_element = all_upload_btns[0]

        if not btn_element:
            log(f"  댓글 #{comment_no} 등록 버튼 못 찾음")
            return False

        await btn_element.evaluate("el => el.click()")
        await random_sleep(2.0, 4.0)
        log(f"  대댓글 등록 완료: '{reply_text[:30]}'")
        return True

    except Exception as e:
        log(f"  대댓글 작성 오류: {str(e)[:80]}")
        return False


async def write_comment(main_frame, target_id: str, comment: str,
                        log: Callable[[str], None]) -> bool:
    try:
        comment_write_btn = await main_frame.query_selector('a:has-text("댓글 쓰기")')
        if not comment_write_btn:
            comment_write_btn = await main_frame.query_selector('a:has-text("댓글")')
        if comment_write_btn:
            await comment_write_btn.evaluate("el => el.click()")
            await random_sleep(2.0, 4.0)

        placeholder = await main_frame.query_selector(".u_cbox_guide")
        if placeholder:
            await placeholder.evaluate("el => el.click()")
            await random_sleep(0.8, 2.0)

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
        await random_sleep(0.8, 2.0)

        register_btn = await main_frame.query_selector(".u_cbox_btn_upload")
        if not register_btn:
            register_btn = await main_frame.query_selector('button:has-text("등록")')
        if not register_btn:
            log(f"  [{target_id}] 등록 버튼 못 찾음 - skip")
            return False

        await register_btn.evaluate("el => el.click()")
        await random_sleep(2.0, 4.0)
        log(f"  [{target_id}] 댓글 등록 완료: '{comment[:30]}'")
        return True

    except Exception as e:
        log(f"  [{target_id}] 댓글 오류: {str(e)[:80]}")
        return False
