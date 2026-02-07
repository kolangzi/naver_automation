from playwright.async_api import async_playwright, Page, Browser
from utils import HumanDelay, human_type
from comment_ai import CommentGenerator
import asyncio
import re
from typing import Callable, List, Optional

class NaverNeighborBot:
    def __init__(self, log_callback: Callable[[str], None] = print):
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.playwright = None
        self.log = log_callback
        self.is_running = False
        self.sympathy_url = None

    async def start_browser(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
            ]
        )
        context = await self.browser.new_context(
            viewport={'width': 1280, 'height': 900},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        self.page = await context.new_page()

        await self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        self.log("브라우저 시작됨")

    async def close_browser(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        self.log("브라우저 종료됨")

    async def check_login_status(self) -> bool:
        await self.page.goto('https://www.naver.com')
        await HumanDelay.page_load()
        login_btn = await self.page.query_selector('a.MyView-module__link_login___HpHMW')
        return login_btn is None

    async def login(self, user_id: str, password: str) -> bool:
        try:
            self.log("로그인 시도 중...")
            await self.page.goto('https://nid.naver.com/nidlogin.login')
            await HumanDelay.page_load()

            await HumanDelay.before_click()
            await human_type(self.page, '#id', user_id)

            await HumanDelay.before_click()
            await human_type(self.page, '#pw', password)

            await HumanDelay.before_click()
            await self.page.click('#log\\.login')

            await HumanDelay.page_load()

            if await self.check_login_status():
                self.log("로그인 성공!")
                return True
            else:
                self.log("로그인 실패 - 캡차 또는 인증 필요할 수 있음")
                return False

        except Exception as e:
            self.log(f"로그인 오류: {str(e)}")
            return False

    def _parse_blog_url(self, blog_url: str) -> tuple:
        patterns = [
            r'blog\.naver\.com/([^/]+)/(\d+)',
            r'blogId=([^&]+).*logNo=(\d+)',
            r'blog\.naver\.com/PostView\.naver\?blogId=([^&]+)&logNo=(\d+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, blog_url)
            if match:
                return match.group(1), match.group(2)
        return None, None

    async def extract_like_accounts(self, blog_url: str) -> List[dict]:
        blog_id, log_no = self._parse_blog_url(blog_url)
        if not blog_id or not log_no:
            self.log(f"URL 파싱 실패: {blog_url}")
            return []

        self.sympathy_url = f"https://blog.naver.com/SympathyHistoryList.naver?blogId={blog_id}&logNo={log_no}&categoryId=3"
        self.log(f"공감 목록 페이지 접속: {self.sympathy_url}")
        
        await self.page.goto(self.sympathy_url)
        await HumanDelay.page_load()
        await asyncio.sleep(2)

        return await self._get_available_accounts()

    async def _get_available_accounts(self) -> List[dict]:
        accounts = []
        
        add_buddy_btns = await self.page.query_selector_all('a.btn_buddy._addBuddyPop')

        for btn in add_buddy_btns:
            try:
                cls = await btn.get_attribute('class') or ''
                param_match = re.search(r'_param\(([^)]+)\)', cls)
                if not param_match:
                    continue
                
                user_id = param_match.group(1)
                
                parent_li = await btn.evaluate_handle('el => el.closest("li")')
                name_el = await parent_li.as_element().query_selector('.nick a, .author, [class*="name"]')
                
                display_name = user_id
                if name_el:
                    display_name = await name_el.inner_text()
                    display_name = display_name.strip() or user_id

                accounts.append({
                    'user_id': user_id,
                    'name': display_name,
                })
                
            except Exception as e:
                continue

        return accounts

    async def _find_button_for_user(self, user_id: str):
        selector = f'a.btn_buddy._addBuddyPop._param\\({user_id}\\)'
        btn = await self.page.query_selector(selector)
        if btn:
            return btn
        
        add_buddy_btns = await self.page.query_selector_all('a.btn_buddy._addBuddyPop')
        for btn in add_buddy_btns:
            cls = await btn.get_attribute('class') or ''
            if f'_param({user_id})' in cls:
                return btn
        return None

    async def request_neighbor(self, account: dict) -> bool:
        try:
            name = account['name']
            user_id = account['user_id']
            context = self.page.context

            self.log(f"[{name}] 이웃추가 클릭...")

            btn = await self._find_button_for_user(user_id)
            if not btn:
                self.log(f"[{name}] 버튼 없음 - 스킵")
                return False

            await HumanDelay.before_click()
            
            try:
                async with context.expect_page(timeout=5000) as new_page_info:
                    await btn.click()
                popup = await new_page_info.value
            except Exception:
                self.log(f"[{name}] 팝업 안 열림 (이미 이웃/신청중) - 스킵")
                return False
            
            await popup.wait_for_load_state('domcontentloaded')
            await asyncio.sleep(1)
            
            self.log(f"[{name}] 팝업 열림")

            mutual_label = await popup.query_selector('label[for="each_buddy_add"]:not(.disabled)')
            if mutual_label:
                is_disabled = await mutual_label.evaluate('el => el.classList.contains("disabled") || el.closest(".disabled") !== null')
                if is_disabled:
                    self.log(f"[{name}] 서로이웃 비활성화 - 스킵")
                    await self._handle_popup_close(popup)
                    return False
                
                await HumanDelay.before_click()
                try:
                    await mutual_label.click(timeout=3000)
                    self.log(f"[{name}] 서로이웃 선택 완료")
                except Exception:
                    self.log(f"[{name}] 서로이웃 클릭 실패 - 스킵")
                    await self._handle_popup_close(popup)
                    return False
                await asyncio.sleep(0.5)
            else:
                self.log(f"[{name}] 서로이웃 옵션 없음 - 스킵")
                await self._handle_popup_close(popup)
                return False

            next_btn = await popup.query_selector('a.button_next, a._buddyAddNext, a:has-text("다음")')
            if next_btn:
                await HumanDelay.before_click()
                await next_btn.click()
                self.log(f"[{name}] 다음 버튼 클릭")
                await asyncio.sleep(2)
                
                if popup.is_closed():
                    self.log(f"[{name}] 이미 신청 완료/진행중 - 완료 처리")
                    return True

            if popup.is_closed():
                self.log(f"[{name}] 팝업 닫힘 - 완료 처리")
                return True

            message_input = await popup.query_selector('textarea')
            if message_input:
                await message_input.fill('블로그 글 잘 봤습니다. 서로이웃 신청드려요!')
                self.log(f"[{name}] 메시지 입력 완료")
                await asyncio.sleep(0.5)

            submit_btn = await popup.query_selector(
                'a.button_next, a.button_ok, a:has-text("확인"), a:has-text("신청"), button:has-text("확인")'
            )
            if submit_btn:
                await HumanDelay.before_click()
                await submit_btn.click()
                self.log(f"[{name}] 신청 버튼 클릭")
                await asyncio.sleep(2)

            await self._handle_popup_close(popup)

            self.log(f"[{name}] 서로이웃 신청 완료!")
            return True

        except Exception as e:
            self.log(f"[{account.get('name', '알수없음')}] 오류 - 스킵: {str(e)[:50]}")
            return False

    async def _handle_popup_close(self, popup):
        try:
            if popup.is_closed():
                return
            
            confirm_btn = await popup.query_selector('a:has-text("확인"), button:has-text("확인")')
            if confirm_btn:
                await confirm_btn.click()
                await asyncio.sleep(1)
            
            if not popup.is_closed():
                await popup.close()
        except:
            pass

    async def _reload_sympathy_page(self):
        if self.sympathy_url:
            await self.page.goto(self.sympathy_url)
            await HumanDelay.page_load()
            await asyncio.sleep(1)

    def _get_main_frame(self):
        for f in self.page.frames:
            if 'PostView' in f.url:
                return f
        return None

    async def get_latest_post_log_no(self, target_id: str) -> Optional[str]:
        post_list_url = f'https://blog.naver.com/PostList.naver?blogId={target_id}&categoryNo=0&from=postList'
        self.log(f"[{target_id}] 최신글 목록 접속...")
        await self.page.goto(post_list_url)
        await HumanDelay.page_load()
        await asyncio.sleep(3)

        for f in self.page.frames:
            match = re.search(r'sympathyFrm(\d+)', f.name)
            if match:
                log_no = match.group(1)
                self.log(f"[{target_id}] 최신 글 logNo: {log_no}")
                return log_no

        js_log_nos = await self.page.evaluate("""
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
            self.log(f"[{target_id}] 최신 글 logNo: {js_log_nos[0]}")
            return js_log_nos[0]

        self.log(f"[{target_id}] logNo를 찾지 못함")
        return None

    async def get_post_content(self, target_id: str, log_no: str) -> dict:
        post_url = f'https://blog.naver.com/{target_id}/{log_no}'
        self.log(f"[{target_id}] 글 접속: {post_url}")
        await self.page.goto(post_url)
        await HumanDelay.page_load()
        await asyncio.sleep(3)

        main_frame = self._get_main_frame()
        if not main_frame:
            return {'title': '', 'body': ''}

        title = ''
        title_el = await main_frame.query_selector('.se-title-text')
        if title_el:
            title = await title_el.inner_text()

        body = ''
        body_el = await main_frame.query_selector('.se-main-container')
        if body_el:
            body = await body_el.inner_text()

        self.log(f"[{target_id}] 제목: {title[:50]}")
        return {'title': title.strip(), 'body': body.strip()[:1000]}

    async def write_comment(self, target_id: str, log_no: str, comment_text: str) -> bool:
        post_url = f'https://blog.naver.com/{target_id}/{log_no}'

        self.log(f"[{target_id}] 댓글 작성을 위해 글 페이지 이동...")
        await self.page.goto(post_url)
        await HumanDelay.page_load()
        await asyncio.sleep(3)

        main_frame = self._get_main_frame()
        if not main_frame:
            self.log(f"[{target_id}] mainFrame을 찾지 못함")
            return False

        try:
            await self.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            await asyncio.sleep(1)
            await main_frame.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            await asyncio.sleep(2)

            comment_write_btn = await main_frame.query_selector('a:has-text("댓글 쓰기")')
            if not comment_write_btn:
                comment_write_btn = await main_frame.query_selector('.btn_comment')
            if comment_write_btn:
                self.log(f"[{target_id}] 댓글 쓰기 버튼 발견")
                await comment_write_btn.evaluate('el => el.click()')
                await asyncio.sleep(2)

            placeholder = await main_frame.query_selector('.u_cbox_guide')
            if placeholder:
                await placeholder.evaluate('el => el.click()')
                await asyncio.sleep(1)

            comment_input = await main_frame.query_selector('div[contenteditable="true"].u_cbox_text')
            if not comment_input:
                comment_input = await main_frame.query_selector('div[contenteditable="true"]')
            if not comment_input:
                comment_input = await main_frame.query_selector('textarea')

            if not comment_input:
                self.log(f"[{target_id}] 댓글 입력 필드를 찾지 못함")
                return False

            self.log(f"[{target_id}] 댓글 입력 필드 발견, 텍스트 입력 중...")
            await comment_input.evaluate('''(el, text) => {
                el.focus();
                el.innerText = text;
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
                el.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true }));
            }''', comment_text)
            await asyncio.sleep(1)

            register_btn = await main_frame.query_selector('.u_cbox_btn_upload')
            if not register_btn:
                register_btn = await main_frame.query_selector('button:has-text("등록")')

            if not register_btn:
                self.log(f"[{target_id}] 등록 버튼을 찾지 못함")
                return False

            self.log(f"[{target_id}] 등록 버튼 클릭...")
            await register_btn.evaluate('el => el.click()')
            await asyncio.sleep(3)

            self.log(f"[{target_id}] 댓글 작성 완료: '{comment_text[:30]}'")
            return True

        except Exception as e:
            self.log(f"[{target_id}] 댓글 작성 오류: {str(e)[:80]}")
            return False

    async def run(self, blog_url: str, user_id: str, password: str,
                  progress_callback: Callable[[int, int], None] = None,
                  enable_comment: bool = True, comment_text: str = "안녕하세요! 글 잘 봤습니다 :)",
                  gemini_api_key: str = ""):
        self.is_running = True
        ai_generator = None
        if enable_comment and gemini_api_key:
            ai_generator = CommentGenerator(gemini_api_key)
            self.log("AI 댓글 생성 모드 (Gemini 2.5 Flash)")
        elif enable_comment:
            self.log(f"고정 댓글 모드: '{comment_text[:30]}'")

        try:
            await self.start_browser()

            if not await self.check_login_status():
                if not await self.login(user_id, password):
                    self.log("로그인에 실패했습니다. 수동으로 로그인해주세요.")
                    self.log("30초 내에 수동 로그인을 완료해주세요...")
                    await asyncio.sleep(30)
                    if not await self.check_login_status():
                        raise Exception("로그인 실패")

            accounts = await self.extract_like_accounts(blog_url)

            if not accounts:
                self.log("이웃추가 가능한 계정이 없습니다.")
                return

            total = len(accounts)
            success_count = 0
            comment_count = 0
            self.log(f"이웃추가 가능 계정 {total}개 발견")

            for i, account in enumerate(accounts):
                if not self.is_running:
                    self.log("사용자에 의해 중단됨")
                    break

                self.log(f"  [{i+1}/{total}] {account['name']} ({account['user_id']})")

            succeeded_accounts = []

            for i, account in enumerate(accounts):
                if not self.is_running:
                    self.log("사용자에 의해 중단됨")
                    break

                if await self.request_neighbor(account):
                    success_count += 1
                    succeeded_accounts.append(account)

                if progress_callback:
                    progress_callback(i + 1, total)

                if i < total - 1:
                    await HumanDelay.between_requests()
                    await self._reload_sympathy_page()

            self.log(f"서로이웃 신청 완료! {total}개 중 {success_count}개 성공")

            if enable_comment and succeeded_accounts:
                self.log(f"성공한 {len(succeeded_accounts)}개 계정에 댓글 작성 시작...")
                for account in succeeded_accounts:
                    if not self.is_running:
                        self.log("사용자에 의해 중단됨")
                        break

                    target_id = account['user_id']
                    name = account['name']
                    try:
                        log_no = await self.get_latest_post_log_no(target_id)
                        if not log_no:
                            self.log(f"[{name}] 최신글을 찾지 못함 - 댓글 스킵")
                            continue

                        final_comment = comment_text
                        if ai_generator:
                            content = await self.get_post_content(target_id, log_no)
                            generated = ai_generator.generate(content['title'], content['body'])
                            if generated:
                                final_comment = generated
                                self.log(f"[{name}] AI 댓글 생성: '{final_comment[:40]}'")
                            else:
                                self.log(f"[{name}] AI 생성 실패 - 고정 댓글 사용")

                        if await self.write_comment(target_id, log_no, final_comment):
                            comment_count += 1
                    except Exception as e:
                        self.log(f"[{name}] 댓글 오류: {str(e)[:50]}")

                    await HumanDelay.between_requests()

                self.log(f"댓글 {comment_count}개 작성 완료")

        except Exception as e:
            self.log(f"실행 오류: {str(e)}")
        finally:
            await self.close_browser()
            self.is_running = False

    def stop(self):
        self.is_running = False
        self.log("중단 요청됨...")
