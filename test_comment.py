import asyncio
import re
from playwright.async_api import async_playwright
from utils import HumanDelay, human_type

async def test_comment():
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(
        headless=False,
        args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
    )
    context = await browser.new_context(
        viewport={'width': 1280, 'height': 900},
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    )
    page = await context.new_page()
    await page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    """)

    print("=" * 60)
    print("[1] 로그인 시도...")
    await page.goto('https://nid.naver.com/nidlogin.login')
    await HumanDelay.page_load()
    await human_type(page, '#id', 'test_wang')
    await HumanDelay.before_click()
    await human_type(page, '#pw', 'a0215620$$')
    await HumanDelay.before_click()
    await page.click('#log\\.login')
    await HumanDelay.page_load()

    await page.goto('https://www.naver.com')
    await HumanDelay.page_load()
    login_btn = await page.query_selector('a.MyView-module__link_login___HpHMW')
    if login_btn is None:
        print("[1] 로그인 성공!")
    else:
        print("[1] 로그인 실패 - 30초 내 수동 로그인 해주세요")
        await asyncio.sleep(30)

    target_id = 'lizidemarron'
    post_list_url = f'https://blog.naver.com/PostList.naver?blogId={target_id}&categoryNo=0&from=postList'
    print(f"\n{'=' * 60}")
    print(f"[2] 최신글 목록에서 logNo 추출: {post_list_url}")
    await page.goto(post_list_url)
    await HumanDelay.page_load()
    await asyncio.sleep(3)

    log_nos = []
    for f in page.frames:
        match = re.search(r'sympathyFrm(\d+)', f.name)
        if match:
            log_nos.append(match.group(1))

    if not log_nos:
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
        log_nos = js_log_nos

    if not log_nos:
        print("[2] logNo를 찾지 못함 - 종료")
        await browser.close()
        await playwright.stop()
        return

    latest_log_no = log_nos[0]
    print(f"[2] logNo 발견: {latest_log_no}")

    post_url = f'https://blog.naver.com/{target_id}/{latest_log_no}'
    print(f"\n{'=' * 60}")
    print(f"[3] 최신 글 접속: {post_url}")
    await page.goto(post_url)
    await HumanDelay.page_load()
    await asyncio.sleep(3)

    main_frame = None
    for f in page.frames:
        if 'PostView' in f.url:
            main_frame = f
            break

    if not main_frame:
        print("[3] mainFrame을 찾지 못함 - 종료")
        await browser.close()
        await playwright.stop()
        return

    print(f"[3] mainFrame 발견")

    print(f"\n{'=' * 60}")
    print("[4] 댓글 작성 시도...")

    await main_frame.evaluate('window.scrollTo(0, document.body.scrollHeight)')
    await asyncio.sleep(2)

    comment_trigger_selectors = [
        '.btn_comment',
        'a:has-text("첫 댓글을 남겨보세요")',
        'a:has-text("댓글을 입력하세요")',
        'a:has-text("댓글 쓰기")',
        '.area_comment a',
        'p.write_txt',
        '.comment_inbox',
    ]

    clicked = False
    for sel in comment_trigger_selectors:
        try:
            el = await main_frame.query_selector(sel)
            if el:
                text = ''
                try:
                    text = await el.inner_text()
                except:
                    pass
                print(f"    댓글 트리거 발견: '{sel}' -> '{text[:40]}'")
                await HumanDelay.before_click()
                await el.click()
                clicked = True
                print(f"    댓글 트리거 클릭 완료")
                await asyncio.sleep(2)
                break
        except Exception as e:
            print(f"    셀렉터 '{sel}' 실패: {str(e)[:50]}")
            continue

    if not clicked:
        print("    댓글 트리거를 찾지 못함, .area_comment 내부 HTML 확인...")
        area_html = await main_frame.evaluate("""
            () => {
                const area = document.querySelector('.area_comment');
                return area ? area.innerHTML.substring(0, 2000) : 'NOT FOUND';
            }
        """)
        print(area_html[:1500])

    print(f"\n[5] 댓글 입력 필드 탐색...")
    input_selectors = [
        'textarea',
        'div[contenteditable="true"]',
        '.u_cbox_text',
        'textarea.u_cbox_text',
        '#cmtinput',
        '.comment_inbox textarea',
        'textarea[placeholder]',
    ]

    comment_input = None
    for sel in input_selectors:
        try:
            el = await main_frame.query_selector(sel)
            if el:
                tag = await el.evaluate('el => el.tagName')
                cls = await el.evaluate('el => el.className')
                print(f"    입력 필드 발견: '{sel}' tag={tag} class={cls[:60]}")
                comment_input = el
                break
        except:
            continue

    if not comment_input:
        print("    mainFrame에서 못 찾음, 전체 프레임 탐색...")
        for f in page.frames:
            for sel in input_selectors:
                try:
                    el = await f.query_selector(sel)
                    if el:
                        tag = await el.evaluate('el => el.tagName')
                        cls = await el.evaluate('el => el.className')
                        print(f"    입력 필드 발견 (frame: {f.name[:20]}): '{sel}' tag={tag} class={cls[:60]}")
                        comment_input = el
                        main_frame = f
                        break
                except:
                    continue
            if comment_input:
                break

    if not comment_input:
        print("    댓글 입력 필드를 찾지 못함")
        print("    현재 .area_comment 상태 확인...")
        area_state = await main_frame.evaluate("""
            () => {
                const areas = document.querySelectorAll('.area_comment');
                const result = [];
                areas.forEach((a, i) => {
                    result.push({
                        index: i,
                        innerHTML: a.innerHTML.substring(0, 1000),
                        childCount: a.children.length,
                    });
                });
                return result;
            }
        """)
        for a in area_state:
            print(f"    area_comment[{a['index']}] children={a['childCount']}")
            print(f"    {a['innerHTML'][:800]}")

        await asyncio.sleep(60)
        await browser.close()
        await playwright.stop()
        return

    print(f"\n[6] 댓글 텍스트 입력: '안녕'")

    placeholder = await main_frame.query_selector('.u_cbox_guide')
    if placeholder:
        print("    placeholder(u_cbox_guide) 발견 - 클릭하여 활성화...")
        await placeholder.click(force=True)
        await asyncio.sleep(1)

    tag = await comment_input.evaluate('el => el.tagName')
    if tag == 'TEXTAREA':
        await comment_input.fill('안녕')
    else:
        await comment_input.evaluate('el => { el.focus(); }')
        await asyncio.sleep(0.3)
        await page.keyboard.type('안녕', delay=100)

    await asyncio.sleep(1)

    current_value = await comment_input.evaluate('el => el.value || el.textContent || el.innerText')
    print(f"    현재 입력값: '{current_value}'")

    print(f"\n[7] 등록 버튼 탐색...")
    register_selectors = [
        '.u_cbox_btn_upload',
        'button:has-text("등록")',
        'a:has-text("등록")',
        'button.btn_register',
        'a.btn_register',
        'button[class*="submit"]',
        'button[class*="write"]',
        '.comment_write_btn',
        'input[type="submit"]',
    ]

    register_btn = None
    for sel in register_selectors:
        try:
            el = await main_frame.query_selector(sel)
            if el:
                text = ''
                try:
                    text = await el.inner_text()
                except:
                    pass
                print(f"    등록 버튼 발견: '{sel}' -> '{text[:20]}'")
                register_btn = el
                break
        except:
            continue

    if register_btn:
        print(f"\n[8] 등록 버튼 클릭!")
        await HumanDelay.before_click()
        await register_btn.click()
        await asyncio.sleep(3)
        print("[8] 등록 버튼 클릭 완료! 댓글이 달렸는지 확인하세요.")
    else:
        print("    등록 버튼을 찾지 못함")
        comment_area_html = await main_frame.evaluate("""
            () => {
                const area = document.querySelector('.area_comment');
                return area ? area.innerHTML.substring(0, 3000) : 'NOT FOUND';
            }
        """)
        print(f"    area_comment HTML:\n{comment_area_html[:2000]}")

    print(f"\n{'=' * 60}")
    print("브라우저를 60초간 유지합니다. 댓글 확인하세요.")
    await asyncio.sleep(60)

    await browser.close()
    await playwright.stop()

asyncio.run(test_comment())
