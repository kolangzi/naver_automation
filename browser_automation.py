from playwright.async_api import async_playwright, Page, Browser
from utils import HumanDelay, human_type
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

    async def run(self, blog_url: str, user_id: str, password: str,
                  progress_callback: Callable[[int, int], None] = None):
        self.is_running = True

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
            self.log(f"이웃추가 가능 계정 {total}개 발견")

            for i, account in enumerate(accounts):
                if not self.is_running:
                    self.log("사용자에 의해 중단됨")
                    break

                self.log(f"  [{i+1}/{total}] {account['name']} ({account['user_id']})")

            for i, account in enumerate(accounts):
                if not self.is_running:
                    self.log("사용자에 의해 중단됨")
                    break

                if await self.request_neighbor(account):
                    success_count += 1

                if progress_callback:
                    progress_callback(i + 1, total)

                if i < total - 1:
                    await HumanDelay.between_requests()
                    await self._reload_sympathy_page()

            self.log(f"완료! 총 {total}개 중 {success_count}개 신청 성공")

        except Exception as e:
            self.log(f"실행 오류: {str(e)}")
        finally:
            await self.close_browser()
            self.is_running = False

    def stop(self):
        self.is_running = False
        self.log("중단 요청됨...")
