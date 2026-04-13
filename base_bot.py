from playwright.async_api import async_playwright, Page, BrowserContext
from playwright_stealth import Stealth
from utils import HumanDelay
import asyncio
import os
import random
from typing import Callable, Optional

_USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
]


def _get_or_create_user_agent(profile_dir: str) -> str:
    """프로필 디렉토리의 ua.txt에서 UA를 읽거나, 없으면 랜덤 선택 후 저장.
    같은 프로필(쿠키·localStorage)은 항상 같은 UA를 사용해야 지문 불일치로 탐지되지 않음."""
    ua_path = os.path.join(profile_dir, "ua.txt")
    if os.path.exists(ua_path):
        try:
            with open(ua_path, "r", encoding="utf-8") as f:
                saved = f.read().strip()
            if saved:
                return saved
        except OSError:
            pass
    ua = random.choice(_USER_AGENTS)
    try:
        with open(ua_path, "w", encoding="utf-8") as f:
            f.write(ua)
    except OSError:
        pass
    return ua


class NaverBaseBot:
    def __init__(self, log_callback: Callable[[str], None] = print):
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.playwright = None
        self.log = log_callback
        self.is_running = False
        self._stealth: Optional[Stealth] = None

    async def _apply_stealth_to_page(self, page: Page):
        """새로 열리는 모든 페이지(팝업 포함)에 stealth 적용."""
        if self._stealth is None:
            return
        try:
            await self._stealth.apply_stealth_async(page)
        except Exception as e:
            self.log(f"  [stealth] 팝업 stealth 적용 실패: {str(e)[:80]}")

    def _on_new_page(self, page: Page):
        """context.on('page') 동기 콜백. 비동기 stealth 적용을 태스크로 예약."""
        asyncio.create_task(self._apply_stealth_to_page(page))

    async def start_browser(self, user_id: str = "default"):
        profile_dir = os.path.join(
            os.path.expanduser("~"), ".naver_automation", "profiles", user_id
        )
        os.makedirs(profile_dir, exist_ok=True)

        self.playwright = await async_playwright().start()
        user_agent = _get_or_create_user_agent(profile_dir)
        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
            ],
            viewport={'width': 1280, 'height': 900},
            user_agent=user_agent,
            locale='ko-KR',
            timezone_id='Asia/Seoul',
        )

        self._stealth = Stealth()
        # 팝업(context.expect_page로 여는 서로이웃 신청창 등)에도 stealth 자동 적용
        self.context.on("page", self._on_new_page)

        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
        await self._apply_stealth_to_page(self.page)

        self.log(f"브라우저 시작됨 (프로필: {user_id})")
        self.log("⚠️  주의: 실행 중 Cmd+W / Ctrl+W를 누르지 마세요. 브라우저가 종료됩니다.")

    async def close_browser(self):
        if self.context:
            await self.context.close()
        if self.playwright:
            await self.playwright.stop()
        self.log("브라우저 종료됨")

    async def check_login_status(self) -> bool:
        await self.page.goto('https://www.naver.com')
        await HumanDelay.page_load()
        login_btn = await self.page.query_selector('a.MyView-module__link_login___HpHMW')
        return login_btn is None

    async def ensure_login(self, user_id: str):
        if await self.check_login_status():
            self.log("로그인 상태 확인됨 (기존 세션 유지)")
            return

        self.log("로그인이 필요합니다. 브라우저에서 직접 로그인해주세요.")
        await self.page.goto('https://nid.naver.com/nidlogin.login')
        await HumanDelay.page_load()

        id_input = await self.page.query_selector('#id')
        if id_input:
            await id_input.evaluate('(el, uid) => { el.value = uid; el.dispatchEvent(new Event("input", {bubbles:true})); }', user_id)
            self.log(f"아이디 자동 입력됨: {user_id}")
        self.log("비밀번호를 입력하고 3분 이내에 로그인을 완료해주세요.")

        max_wait = 180
        poll_interval = 5
        elapsed = 0
        while elapsed < max_wait:
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
            current_url = self.page.url
            if 'nidlogin.login' not in current_url:
                if await self.check_login_status():
                    self.log("로그인 성공!")
                    return
                else:
                    await self.page.goto('https://nid.naver.com/nidlogin.login')
                    await HumanDelay.page_load()
            remaining = max_wait - elapsed
            if remaining > 0 and elapsed % 15 == 0:
                self.log(f"로그인 대기 중... (남은 시간: {remaining}초)")

        raise Exception("로그인 시간 초과 (3분). 다시 시도해주세요.")

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
