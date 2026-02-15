import random
import asyncio

class HumanDelay:
    """자동화 탐지 회피를 위한 인간적인 딜레이"""

    @staticmethod
    async def page_load():
        """페이지 로드 후 대기 (2~5초)"""
        await asyncio.sleep(random.uniform(2.0, 5.0))

    @staticmethod
    async def before_click():
        """클릭 전 대기 (0.5~2.0초)"""
        await asyncio.sleep(random.uniform(0.5, 2.0))

    @staticmethod
    async def after_popup():
        """팝업 처리 후 대기 (1~3초)"""
        await asyncio.sleep(random.uniform(1.0, 3.0))

    @staticmethod
    async def between_requests():
        """이웃 신청 간 대기 (2.0~5.0초)"""
        await asyncio.sleep(random.uniform(2.0, 5.0))

    @staticmethod
    async def type_char():
        """글자 입력 간 대기 (50~200ms)"""
        await asyncio.sleep(random.uniform(0.05, 0.20))


async def random_sleep(min_sec: float, max_sec: float):
    """고정 sleep 대체용 랜덤 sleep"""
    await asyncio.sleep(random.uniform(min_sec, max_sec))


async def maybe_idle(log=None):
    """10% 확률로 5~15초 idle (사람처럼 잠깐 멈추기)"""
    if random.random() < 0.10:
        wait = random.uniform(5.0, 15.0)
        if log:
            log(f"  [idle] {wait:.1f}초 대기...")
        await asyncio.sleep(wait)


DAILY_ACTION_LIMIT = 50  # 계정당 일일 액션(댓글/대댓글) 최대 수


async def human_type(page, selector: str, text: str):
    """인간처럼 타이핑하는 함수"""
    element = await page.wait_for_selector(selector)
    await element.click()
    for char in text:
        await element.type(char, delay=random.randint(50, 150))
