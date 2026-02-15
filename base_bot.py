from playwright.async_api import async_playwright, Page, Browser
from playwright_stealth import Stealth
from utils import HumanDelay, human_type
import asyncio
import random
from typing import Callable, Optional

_USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
]


class NaverBaseBot:
    def __init__(self, log_callback: Callable[[str], None] = print):
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.playwright = None
        self.log = log_callback
        self.is_running = False

    async def start_browser(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-accelerator-table',
            ]
        )
        user_agent = random.choice(_USER_AGENTS)
        context = await self.browser.new_context(
            viewport={'width': 1280, 'height': 900},
            user_agent=user_agent,
            locale='ko-KR',
            timezone_id='Asia/Seoul',
        )
        self.page = await context.new_page()

        stealth = Stealth()
        await stealth.apply_stealth_async(self.page)

        await self.page.add_init_script("""
            window.addEventListener('beforeunload', function(e) {
                e.preventDefault();
                e.returnValue = '';
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

    async def ensure_login(self, user_id: str, password: str):
        if not await self.check_login_status():
            if not await self.login(user_id, password):
                self.log("로그인에 실패했습니다. 수동으로 로그인해주세요.")
                self.log("30초 내에 수동 로그인을 완료해주세요...")
                await asyncio.sleep(30)
                if not await self.check_login_status():
                    raise Exception("로그인 실패")

    def _get_main_frame(self):
        for f in self.page.frames:
            if 'PostView' in f.url:
                return f
        return None

    def _get_papermain_frame(self):
        for f in self.page.frames:
            if f.name == "papermain":
                return f
        return None

    def stop(self):
        self.is_running = False
        self.log("중단 요청됨...")
