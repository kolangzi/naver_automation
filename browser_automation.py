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

    async def click_sympathy(self, blog_url: str) -> bool:
        try:
            self.log(f"공감 클릭을 위해 글 페이지 이동: {blog_url}")
            await self.page.goto(blog_url)
            await HumanDelay.page_load()
            await asyncio.sleep(3)

            main_frame = self._get_main_frame()
            if not main_frame:
                self.log("공감 클릭 실패: mainFrame을 찾지 못함")
                return False

            await main_frame.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            await asyncio.sleep(1)

            like_face_btn = await main_frame.query_selector('.my_reaction a.u_likeit_button._face')
            if not like_face_btn:
                self.log("공감 버튼을 찾지 못함")
                return False

            btn_class = await like_face_btn.get_attribute('class') or ''
            if ' on' in btn_class or btn_class.endswith(' on'):
                self.log("이미 공감한 글입니다 - 스킵")
                return True

            self.log("공감 버튼 클릭 중...")
            await like_face_btn.evaluate('el => el.click()')
            await asyncio.sleep(1)

            like_btn = await main_frame.query_selector('.my_reaction a.u_likeit_list_button._button[data-type="like"]')
            if not like_btn:
                self.log("공감(하트) 옵션을 찾지 못함")
                return False

            aria_pressed = await like_btn.get_attribute('aria-pressed')
            if aria_pressed == 'true':
                self.log("이미 공감한 글입니다 - 스킵")
                return True

            await like_btn.evaluate('el => el.click()')
            await asyncio.sleep(2)

            self.log("공감 클릭 완료!")
            return True

        except Exception as e:
            self.log(f"공감 클릭 오류: {str(e)[:80]}")
            return False

    MAX_SUCCESS = 100

    async def _init_sympathy_page(self, blog_url: str) -> bool:
        blog_id, log_no = self._parse_blog_url(blog_url)
        if not blog_id or not log_no:
            self.log(f"URL 파싱 실패: {blog_url}")
            return False

        self.sympathy_url = f"https://blog.naver.com/SympathyHistoryList.naver?blogId={blog_id}&logNo={log_no}&categoryId=3"
        self.log(f"공감 목록 페이지 접속: {self.sympathy_url}")
        
        await self.page.goto(self.sympathy_url)
        await HumanDelay.page_load()
        await asyncio.sleep(5)
        return True

    async def _load_next_page(self) -> bool:
        next_btn = await self.page.query_selector('#_loadNext')
        if not next_btn:
            return False
        is_visible = await next_btn.evaluate('el => el.offsetParent !== null')
        if not is_visible:
            return False
        await next_btn.evaluate('el => el.click()')
        await HumanDelay.page_load()
        await asyncio.sleep(2)
        return True

    async def _restore_page_depth(self, depth: int) -> int:
        restored = 0
        for _ in range(depth):
            if await self._load_next_page():
                restored += 1
            else:
                break
        return restored

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

    async def request_neighbor(self, account: dict, neighbor_message: str = "블로그 글 잘 봤습니다. 서로이웃 신청드려요!") -> bool:
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
                await message_input.fill(neighbor_message)
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
            await asyncio.sleep(5)

    async def _click_sympathy_on_frame(self, main_frame) -> bool:
        try:
            like_face_btn = await main_frame.query_selector('.my_reaction a.u_likeit_button._face')
            if not like_face_btn:
                self.log("  공감 버튼을 찾지 못함 - 스킵")
                return False

            btn_class = await like_face_btn.get_attribute('class') or ''
            if ' on' in btn_class or btn_class.endswith(' on'):
                self.log("  이미 공감한 글 - 스킵")
                return True

            await like_face_btn.evaluate('el => el.click()')
            await asyncio.sleep(1)

            like_btn = await main_frame.query_selector('.my_reaction a.u_likeit_list_button._button[data-type="like"]')
            if not like_btn:
                self.log("  공감(하트) 옵션을 찾지 못함 - 스킵")
                return False

            aria_pressed = await like_btn.get_attribute('aria-pressed')
            if aria_pressed == 'true':
                self.log("  이미 공감한 글 - 스킵")
                return True

            await like_btn.evaluate('el => el.click()')
            await asyncio.sleep(2)

            self.log("  공감 클릭 완료!")
            return True

        except Exception as e:
            self.log(f"  공감 클릭 오류: {str(e)[:80]}")
            return False

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
                comment_write_btn = await main_frame.query_selector('a:has-text("댓글")')
            if comment_write_btn:
                self.log(f"[{target_id}] 댓글 쓰기 버튼 발견")
                await comment_write_btn.evaluate('el => el.click()')
                await asyncio.sleep(3)

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
                  enable_comment: bool = True,
                  gemini_api_key: str = "",
                  neighbor_message: str = "블로그 글 잘 봤습니다. 서로이웃 신청드려요!"):
        self.is_running = True
        ai_generator = None
        if enable_comment and gemini_api_key:
            ai_generator = CommentGenerator(gemini_api_key)
            self.log("AI 댓글 생성 모드 (Gemini 2.5 Flash)")

        try:
            await self.start_browser()

            if not await self.check_login_status():
                if not await self.login(user_id, password):
                    self.log("로그인에 실패했습니다. 수동으로 로그인해주세요.")
                    self.log("30초 내에 수동 로그인을 완료해주세요...")
                    await asyncio.sleep(30)
                    if not await self.check_login_status():
                        raise Exception("로그인 실패")

            await self.click_sympathy(blog_url)

            if not await self._init_sympathy_page(blog_url):
                self.log("공감 목록 페이지 접속 실패")
                return

            success_count = 0
            attempted_ids: set = set()
            page_depth = 0
            succeeded_accounts = []
            comment_count = 0
            total_attempted = 0

            self.log(f"서로이웃 신청 시작 (최대 {self.MAX_SUCCESS}명)")

            while success_count < self.MAX_SUCCESS and self.is_running:
                accounts = await self._get_available_accounts()
                new_accounts = [a for a in accounts if a['user_id'] not in attempted_ids]

                if not new_accounts:
                    self.log(f"현재 페이지(depth={page_depth})에 새 계정 없음, 다음 페이지 시도...")
                    if not await self._load_next_page():
                        self.log("더 이상 페이지가 없습니다.")
                        break
                    page_depth += 1
                    continue

                self.log(f"페이지(depth={page_depth}): 신규 계정 {len(new_accounts)}개 발견")

                for account in new_accounts:
                    if success_count >= self.MAX_SUCCESS:
                        self.log(f"최대 성공 수 {self.MAX_SUCCESS}명 도달 - 신청 종료")
                        break
                    if not self.is_running:
                        self.log("사용자에 의해 중단됨")
                        break

                    attempted_ids.add(account['user_id'])
                    total_attempted += 1

                    self.log(f"  [{success_count+1}/{self.MAX_SUCCESS}] {account['name']} ({account['user_id']})")

                    if await self.request_neighbor(account, neighbor_message):
                        success_count += 1
                        succeeded_accounts.append(account)

                    if progress_callback:
                        progress_callback(success_count, self.MAX_SUCCESS)

                    await HumanDelay.between_requests()

                    await self._reload_sympathy_page()
                    restored = await self._restore_page_depth(page_depth)
                    if restored < page_depth:
                        self.log(f"페이지 depth 복원 불완전 ({restored}/{page_depth}), 현재 depth로 조정")
                        page_depth = restored

                if not self.is_running or success_count >= self.MAX_SUCCESS:
                    break

                if not await self._load_next_page():
                    self.log("더 이상 페이지가 없습니다.")
                    break
                page_depth += 1

            self.log(f"서로이웃 신청 완료! 시도 {total_attempted}명, 성공 {success_count}명")

            if enable_comment and succeeded_accounts:
                comment_total = len(succeeded_accounts)
                self.log(f"성공한 {comment_total}개 계정에 댓글 작성 시작...")
                if progress_callback:
                    progress_callback(0, comment_total)

                for ci, account in enumerate(succeeded_accounts):
                    if not self.is_running:
                        self.log("사용자에 의해 중단됨")
                        break

                    target_id = account['user_id']
                    name = account['name']
                    self.log(f"\n[댓글 {ci+1}/{comment_total}] {name} ({target_id})")
                    try:
                        log_no = await self.get_latest_post_log_no(target_id)
                        if not log_no:
                            self.log(f"[{name}] 최신글을 찾지 못함 - 댓글 스킵")
                            if progress_callback:
                                progress_callback(ci + 1, comment_total)
                            continue

                        final_comment = None
                        if ai_generator:
                            content = await self.get_post_content(target_id, log_no)
                            generated = ai_generator.generate(content['title'], content['body'])
                            if generated:
                                final_comment = generated
                                self.log(f"[{name}] AI 댓글 생성: '{final_comment[:40]}'")
                            else:
                                self.log(f"[{name}] AI 댓글 생성 3회 시도 모두 실패")
                                self.log("AI 모델이 정상 동작하지 않습니다. 작업을 종료합니다.")
                                return

                        if final_comment and await self.write_comment(target_id, log_no, final_comment):
                            comment_count += 1
                    except Exception as e:
                        self.log(f"[{name}] 댓글 오류: {str(e)[:50]}")

                    if progress_callback:
                        progress_callback(ci + 1, comment_total)
                    await HumanDelay.between_requests()

                self.log(f"댓글 {comment_count}개 작성 완료")

        except Exception as e:
            self.log(f"실행 오류: {str(e)}")
        finally:
            await self.close_browser()
            self.is_running = False

    # ── 기능 2: 서로이웃 댓글 관련 메서드 ──

    def _get_papermain_frame(self):
        for f in self.page.frames:
            if f.name == "papermain":
                return f
        return None

    def _parse_naver_date(self, date_str: str) -> str:
        date_str = date_str.strip().rstrip(".")
        m = re.match(r"(\d{2})\.(\d{2})\.(\d{2})", date_str)
        if m:
            return f"20{m.group(1)}-{m.group(2)}-{m.group(3)}"
        return ""

    async def _navigate_to_buddy_page(self, blog_id: str):
        url = f"https://admin.blog.naver.com/AdminMain.naver?blogId={blog_id}&Redirect=Buddyinfo"
        self.log(f"이웃 관리 페이지 이동: {url}")
        await self.page.goto(url)
        await asyncio.sleep(5)

    async def _select_buddy_group(self, frame, group_name: str) -> bool:
        self.log(f"그룹 선택: '{group_name}'")
        group_box = await frame.query_selector("#buddysel_groupall .selectbox-box")
        if not group_box:
            self.log("  그룹 드롭다운 못 찾음")
            return False
        await group_box.click()
        await asyncio.sleep(1)
        items = await frame.query_selector_all("#buddysel_groupall .selectbox-list li")
        for item in items:
            text = (await item.inner_text()).strip()
            if group_name in text:
                await item.click()
                self.log(f"  '{group_name}' 선택 완료")
                await asyncio.sleep(3)
                return True
        self.log(f"  '{group_name}' 못 찾음")
        return False

    async def _change_sort_to_update(self, frame) -> bool:
        self.log("정렬 → 업데이트순")
        sort_box = await frame.query_selector("#buddysel_order .selectbox-box")
        if not sort_box:
            self.log("  정렬 드롭다운 못 찾음")
            return False
        current_label = await frame.query_selector("#buddysel_order .selectbox-label")
        if current_label:
            current_text = (await current_label.inner_text()).strip()
            if "업데이트" in current_text:
                self.log("  이미 업데이트순")
                return True
        await sort_box.click()
        await asyncio.sleep(1)
        items = await frame.query_selector_all("#buddysel_order .selectbox-list li")
        for item in items:
            text = (await item.inner_text()).strip()
            if "업데이트" in text:
                await item.click()
                self.log("  '업데이트순' 선택 완료")
                await asyncio.sleep(3)
                return True
        self.log("  '업데이트순' 못 찾음")
        return False

    async def _extract_buddy_list(self, frame) -> list:
        rows = await frame.query_selector_all("table.tbl_buddymanage tbody tr")
        buddies = []
        for row in rows:
            try:
                tds = await row.query_selector_all("td")
                if len(tds) < 7:
                    continue
                blog_link = await row.query_selector("td.buddy a[href*='blog.naver.com']")
                if not blog_link:
                    continue
                href = await blog_link.get_attribute("href") or ""
                m = re.search(r"blog\.naver\.com/([^/?&#]+)", href)
                if not m:
                    continue
                blog_id = m.group(1)
                nick_el = await row.query_selector("td.buddy .nickname")
                nick = blog_id
                if nick_el:
                    nick = (await nick_el.inner_text()).strip()
                recent_post_td = tds[5]
                recent_post_text = (await recent_post_td.inner_text()).strip()
                update_date = self._parse_naver_date(recent_post_text)
                buddies.append({
                    "blog_id": blog_id,
                    "nick": nick,
                    "update_date": update_date,
                    "raw_date": recent_post_text,
                })
            except:
                continue
        return buddies

    async def _go_to_next_buddy_page(self, frame) -> bool:
        current_el = await frame.query_selector(".paginate strong, .page_number strong")
        current_page = 1
        if current_el:
            try:
                current_page = int((await current_el.inner_text()).strip())
            except:
                pass
        next_page = current_page + 1
        self.log(f"  페이지 이동 시도: {current_page} → {next_page}")
        page_links = await frame.query_selector_all(".paginate a, .page_number a")
        for link in page_links:
            text = (await link.inner_text()).strip()
            if text == str(next_page):
                await link.click()
                await asyncio.sleep(3)
                self.log(f"  페이지 {next_page} 이동 완료")
                return True
        next_btn = await frame.query_selector('.paginate a:has-text("다음"), a.next')
        if next_btn:
            await next_btn.click()
            await asyncio.sleep(3)
            self.log("  '다음' 버튼으로 이동")
            return True
        self.log("  더 이상 다음 페이지 없음")
        return False

    async def _check_my_comment_exists(self, main_frame, my_blog_id: str) -> bool:
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

    async def run_buddy_comment(self, user_id: str, password: str,
                                gemini_api_key: str = "",
                                group_name: str = "이웃1",
                                cutoff_date: str = "",
                                progress_callback: Callable[[int, int], None] = None):
        """기능 2: 서로이웃 관리 페이지에서 이웃 수집 → 최신글에 댓글 작성"""
        self.is_running = True
        ai_generator = None
        if gemini_api_key:
            ai_generator = CommentGenerator(gemini_api_key)
            self.log("AI 댓글 생성 모드 (Gemini)")

        from datetime import date
        if not cutoff_date:
            cutoff_date = date.today().strftime("%Y-%m-%d")

        try:
            await self.start_browser()

            if not await self.check_login_status():
                if not await self.login(user_id, password):
                    self.log("로그인에 실패했습니다. 수동으로 로그인해주세요.")
                    self.log("30초 내에 수동 로그인을 완료해주세요...")
                    await asyncio.sleep(30)
                    if not await self.check_login_status():
                        raise Exception("로그인 실패")

            blog_id = user_id

            # ── Phase 1: 이웃 목록 수집 ──
            self.log("=" * 50)
            self.log("Phase 1: 이웃 목록 수집 시작")
            self.log(f"그룹: {group_name} | 기준일: {cutoff_date}")
            self.log("=" * 50)

            await self._navigate_to_buddy_page(blog_id)
            frame = self._get_papermain_frame()
            if not frame:
                self.log("papermain 프레임 못 찾음")
                return

            await self._select_buddy_group(frame, group_name)
            await self._change_sort_to_update(frame)

            all_targets = []
            page_num = 1

            while self.is_running:
                self.log(f"\n── 수집 페이지 {page_num} ──")
                frame = self._get_papermain_frame()
                if not frame:
                    self.log("papermain 프레임 없음")
                    break

                buddies = await self._extract_buddy_list(frame)
                self.log(f"이웃 수: {len(buddies)}")
                if not buddies:
                    break

                found_old = False
                for buddy in buddies:
                    raw_date = buddy["raw_date"]
                    update_date = buddy["update_date"]
                    if raw_date == "-":
                        continue
                    if update_date and update_date < cutoff_date:
                        found_old = True
                        break
                    all_targets.append(buddy)

                if found_old:
                    self.log(f"기준일({cutoff_date})보다 오래된 날짜 발견 → 수집 종료")
                    break

                has_next = await self._go_to_next_buddy_page(frame)
                if not has_next:
                    self.log("마지막 페이지 도달")
                    break
                page_num += 1

            self.log(f"\nPhase 1 완료: {len(all_targets)}명 대상 수집됨")

            if not all_targets:
                self.log("대상 없음. 종료.")
                return

            # ── Phase 2: 블로그 방문 → 댓글 작성 ──
            self.log("\n" + "=" * 50)
            self.log("Phase 2: 댓글 작성 시작")
            self.log("=" * 50)

            total = len(all_targets)
            comment_count = 0
            skip_count = 0

            for i, buddy in enumerate(all_targets):
                if not self.is_running:
                    self.log("사용자에 의해 중단됨")
                    break

                target_id = buddy["blog_id"]
                nick = buddy["nick"]
                self.log(f"\n[{i+1}/{total}] {nick} ({target_id})")

                if progress_callback:
                    progress_callback(i + 1, total)

                log_no = await self.get_latest_post_log_no(target_id)
                if not log_no:
                    self.log(f"  logNo 못 찾음 - skip")
                    skip_count += 1
                    continue

                content = await self.get_post_content(target_id, log_no)

                post_url = f"https://blog.naver.com/{target_id}/{log_no}"
                await self.page.goto(post_url)
                await HumanDelay.page_load()
                await asyncio.sleep(3)

                main_frame = self._get_main_frame()
                if not main_frame:
                    self.log(f"  [{target_id}] mainFrame 못 찾음 - skip")
                    skip_count += 1
                    continue

                await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(1)
                await main_frame.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)

                await self._click_sympathy_on_frame(main_frame)

                already = await self._check_my_comment_exists(main_frame, blog_id)
                if already:
                    self.log(f"  [{target_id}] 이미 내 댓글 존재 - skip")
                    skip_count += 1
                    continue

                comment = None
                if ai_generator and (content["title"] or content["body"]):
                    generated = ai_generator.generate(content["title"], content["body"])
                    if generated:
                        comment = generated
                        self.log(f"  AI 댓글: '{comment}'")
                    else:
                        self.log(f"  AI 댓글 생성 3회 시도 모두 실패")
                        self.log("AI 모델이 정상 동작하지 않습니다. 작업을 종료합니다.")
                        return
                else:
                    self.log(f"  글 내용 없음 - skip")
                    skip_count += 1
                    continue

                if not comment:
                    skip_count += 1
                    continue

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
                        self.log(f"  [{target_id}] 댓글 입력 필드 못 찾음 - skip")
                        skip_count += 1
                        continue

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
                        self.log(f"  [{target_id}] 등록 버튼 못 찾음 - skip")
                        skip_count += 1
                        continue

                    await register_btn.evaluate("el => el.click()")
                    await asyncio.sleep(3)
                    self.log(f"  [{target_id}] 댓글 등록 완료: '{comment[:30]}'")
                    comment_count += 1

                except Exception as e:
                    self.log(f"  [{target_id}] 댓글 오류: {str(e)[:80]}")
                    skip_count += 1

                await HumanDelay.between_requests()

            self.log(f"\n{'=' * 50}")
            self.log(f"완료! 수집 대상: {total}명 | 댓글 등록: {comment_count}개 | 스킵: {skip_count}개")
            self.log(f"{'=' * 50}")

        except Exception as e:
            self.log(f"실행 오류: {str(e)}")
        finally:
            await self.close_browser()
            self.is_running = False

    def stop(self):
        self.is_running = False
        self.log("중단 요청됨...")
