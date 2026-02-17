from base_bot import NaverBaseBot
from utils import HumanDelay, random_sleep, maybe_idle
import asyncio
import re
from typing import Callable, List


class NeighborRequestBot(NaverBaseBot):
    def __init__(self, log_callback: Callable[[str], None] = print):
        super().__init__(log_callback)
        self.sympathy_url = None

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
            await random_sleep(2.0, 4.0)

            main_frame = self._get_main_frame()
            if not main_frame:
                self.log("공감 클릭 실패: mainFrame을 찾지 못함")
                return False

            await main_frame.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            await random_sleep(0.8, 2.0)

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
            await random_sleep(0.8, 2.0)

            like_btn = await main_frame.query_selector('.my_reaction a.u_likeit_list_button._button[data-type="like"]')
            if not like_btn:
                self.log("공감(하트) 옵션을 찾지 못함")
                return False

            aria_pressed = await like_btn.get_attribute('aria-pressed')
            if aria_pressed == 'true':
                self.log("이미 공감한 글입니다 - 스킵")
                return True

            await like_btn.evaluate('el => el.click()')
            await random_sleep(1.5, 3.0)

            self.log("공감 클릭 완료!")
            return True

        except Exception as e:
            self.log(f"공감 클릭 오류: {str(e)[:80]}")
            return False

    async def _init_sympathy_page(self, blog_url: str) -> bool:
        blog_id, log_no = self._parse_blog_url(blog_url)
        if not blog_id or not log_no:
            self.log(f"URL 파싱 실패: {blog_url}")
            return False

        self.sympathy_url = f"https://blog.naver.com/SympathyHistoryList.naver?blogId={blog_id}&logNo={log_no}&categoryId=3"
        self.log(f"공감 목록 페이지 접속: {self.sympathy_url}")

        await self.page.goto(self.sympathy_url)
        await HumanDelay.page_load()
        await random_sleep(3.0, 6.0)
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
        await random_sleep(1.5, 3.0)
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
            await random_sleep(0.8, 2.0)

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
                await random_sleep(1.5, 3.0)

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
                await random_sleep(1.5, 3.0)

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
                await random_sleep(0.8, 2.0)

            if not popup.is_closed():
                await popup.close()
        except:
            pass

    async def _reload_sympathy_page(self):
        if self.sympathy_url:
            await self.page.goto(self.sympathy_url)
            await HumanDelay.page_load()
            await random_sleep(3.0, 6.0)

    async def run(self, blog_url: str, user_id: str,
                  progress_callback: Callable[[int, int], None] = None,
                  neighbor_message: str = "블로그 글 잘 봤습니다. 서로이웃 신청드려요!",
                  max_success: int = 100):
        self.is_running = True

        try:
            await self.start_browser(user_id)
            await self.ensure_login(user_id)

            await self.click_sympathy(blog_url)

            if not await self._init_sympathy_page(blog_url):
                self.log("공감 목록 페이지 접속 실패")
                return

            success_count = 0
            attempted_ids: set = set()
            page_depth = 0
            total_attempted = 0

            self.log(f"서로이웃 신청 시작 (최대 {max_success}명)")

            while success_count < max_success and self.is_running:
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
                    if success_count >= max_success:
                        self.log(f"최대 성공 수 {max_success}명 도달 - 신청 종료")
                        break
                    if not self.is_running:
                        self.log("사용자에 의해 중단됨")
                        break

                    attempted_ids.add(account['user_id'])
                    total_attempted += 1

                    self.log(f"  [{success_count+1}/{max_success}] {account['name']} ({account['user_id']})")

                    if await self.request_neighbor(account, neighbor_message):
                        success_count += 1

                    if progress_callback:
                        progress_callback(success_count, max_success)

                    await HumanDelay.between_requests()
                    await maybe_idle(self.log)

                    await self._reload_sympathy_page()
                    restored = await self._restore_page_depth(page_depth)
                    if restored < page_depth:
                        self.log(f"페이지 depth 복원 불완전 ({restored}/{page_depth}), 현재 depth로 조정")
                        page_depth = restored

                if not self.is_running or success_count >= max_success:
                    break

                if not await self._load_next_page():
                    self.log("더 이상 페이지가 없습니다.")
                    break
                page_depth += 1

            self.log(f"서로이웃 신청 완료! 시도 {total_attempted}명, 성공 {success_count}명")

        except Exception as e:
            self.log(f"실행 오류: {str(e)}")
        finally:
            await self.close_browser()
            self.is_running = False
