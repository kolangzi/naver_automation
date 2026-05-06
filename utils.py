import random
import asyncio
import json
import os
from datetime import date


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
    async def between_requests():
        """이웃 신청 간 대기 (2.0~5.0초)"""
        await asyncio.sleep(random.uniform(2.0, 5.0))


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


# 댓글·대댓글·이웃신청을 합산한 일일 한도. 공감(좋아요)은 별도 패시브 액션으로
# 카운트하지 않는다. 50→30으로 낮춰 계정 보호 마진 확보.
DAILY_ACTION_LIMIT = 30


def _profile_dir(user_id: str) -> str:
    return os.path.join(
        os.path.expanduser("~"), ".naver_automation", "profiles", user_id
    )


def _daily_actions_path(user_id: str) -> str:
    return os.path.join(_profile_dir(user_id), "daily_actions.json")


def _today_str() -> str:
    return date.today().strftime("%Y-%m-%d")


def load_daily_count(user_id: str) -> int:
    """오늘 누적된 액션 수. 날짜가 바뀌었으면 0 반환(파일은 다음 increment 때 갱신)."""
    path = _daily_actions_path(user_id)
    if not os.path.exists(path):
        return 0
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return 0
    if data.get("date") != _today_str():
        return 0
    try:
        return int(data.get("count", 0))
    except (TypeError, ValueError):
        return 0


def increment_daily_count(user_id: str, n: int = 1) -> int:
    """오늘 카운트를 n만큼 증가시키고 갱신된 값을 반환."""
    os.makedirs(_profile_dir(user_id), exist_ok=True)
    current = load_daily_count(user_id)
    new_count = current + n
    payload = {"date": _today_str(), "count": new_count}
    try:
        with open(_daily_actions_path(user_id), "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
    except OSError:
        pass
    return new_count


def daily_limit_reached(user_id: str, limit: int = DAILY_ACTION_LIMIT) -> bool:
    return load_daily_count(user_id) >= limit


def should_engage(probability: float) -> bool:
    """주어진 확률로 True. 100% 전환율 패턴을 깨기 위한 헬퍼."""
    return random.random() < probability


async def simulate_reading(body_length: int = 0, log=None):
    if body_length > 1000:
        wait = random.uniform(8.0, 15.0)
    elif body_length > 300:
        wait = random.uniform(5.0, 10.0)
    else:
        wait = random.uniform(3.0, 7.0)
    if log:
        log(f"  [읽는 중] {wait:.1f}초 체류...")
    await asyncio.sleep(wait)
