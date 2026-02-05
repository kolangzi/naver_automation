import random
import asyncio

class HumanDelay:
    """자동화 탐지 회피를 위한 인간적인 딜레이"""

    @staticmethod
    async def page_load():
        """페이지 로드 후 대기 (2~4초)"""
        await asyncio.sleep(random.uniform(2.0, 4.0))

    @staticmethod
    async def before_click():
        """클릭 전 대기 (0.5~1.5초)"""
        await asyncio.sleep(random.uniform(0.5, 1.5))

    @staticmethod
    async def after_popup():
        """팝업 처리 후 대기 (1~2초)"""
        await asyncio.sleep(random.uniform(1.0, 2.0))

    @staticmethod
    async def between_requests():
        """이웃 신청 간 대기 (1.5~3초)"""
        await asyncio.sleep(random.uniform(1.5, 3.0))

    @staticmethod
    async def type_char():
        """글자 입력 간 대기 (50~150ms)"""
        await asyncio.sleep(random.uniform(0.05, 0.15))

async def human_type(page, selector: str, text: str):
    """인간처럼 타이핑하는 함수"""
    element = await page.wait_for_selector(selector)
    await element.click()
    for char in text:
        await element.type(char, delay=random.randint(50, 150))
