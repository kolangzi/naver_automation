from base_bot import NaverBaseBot
from blog_actions import (
    click_sympathy_on_frame,
    get_latest_post_log_no,
    get_post_content,
    check_my_comment_exists,
    write_comment,
)
from comment_ai import CommentGenerator
from utils import HumanDelay, random_sleep, maybe_idle, DAILY_ACTION_LIMIT
import asyncio
import re
from typing import Callable


class BuddyCommentBot(NaverBaseBot):
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
        await random_sleep(3.0, 6.0)

    async def _select_buddy_group(self, frame, group_name: str) -> bool:
        self.log(f"그룹 선택: '{group_name}'")
        group_box = await frame.query_selector("#buddysel_groupall .selectbox-box")
        if not group_box:
            self.log("  그룹 드롭다운 못 찾음")
            return False
        await group_box.click()
        await random_sleep(0.8, 2.0)
        items = await frame.query_selector_all("#buddysel_groupall .selectbox-list li")
        for item in items:
            text = (await item.inner_text()).strip()
            if group_name in text:
                await item.click()
                self.log(f"  '{group_name}' 선택 완료")
                await random_sleep(2.0, 4.0)
                return True
        self.log(f"  '{group_name}' 못 찾음")
        return False

    async def _change_sort_order(self, frame, sort_order: str = "업데이트순") -> bool:
        self.log(f"정렬 → {sort_order}")
        sort_box = await frame.query_selector("#buddysel_order .selectbox-box")
        if not sort_box:
            self.log("  정렬 드롭다운 못 찾음")
            return False
        current_label = await frame.query_selector("#buddysel_order .selectbox-label")
        if current_label:
            current_text = (await current_label.inner_text()).strip()
            if sort_order == "업데이트순" and "업데이트" in current_text:
                self.log("  이미 업데이트순")
                return True
            if sort_order == "이웃추가순" and "이웃추가" in current_text:
                self.log("  이미 이웃추가순")
                return True
        await sort_box.click()
        await random_sleep(0.8, 2.0)
        items = await frame.query_selector_all("#buddysel_order .selectbox-list li")
        target_keyword = "업데이트" if sort_order == "업데이트순" else "이웃추가"
        for item in items:
            text = (await item.inner_text()).strip()
            if target_keyword in text:
                await item.click()
                self.log(f"  '{sort_order}' 선택 완료")
                await random_sleep(2.0, 4.0)
                return True
        self.log(f"  '{sort_order}' 못 찾음")
        return False

    async def _extract_buddy_list(self, frame, sort_order: str = "업데이트순") -> list:
        rows = await frame.query_selector_all("table.tbl_buddymanage tbody tr")
        buddies = []
        date_col_index = 5 if sort_order == "업데이트순" else 6
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
                date_td = tds[date_col_index]
                date_text = (await date_td.inner_text()).strip()
                parsed_date = self._parse_naver_date(date_text)
                buddies.append({
                    "blog_id": blog_id,
                    "nick": nick,
                    "update_date": parsed_date,
                    "raw_date": date_text,
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
                await random_sleep(2.0, 4.0)
                self.log(f"  페이지 {next_page} 이동 완료")
                return True
        next_btn = await frame.query_selector('.paginate a:has-text("다음"), a.next')
        if next_btn:
            await next_btn.click()
            await random_sleep(2.0, 4.0)
            self.log("  '다음' 버튼으로 이동")
            return True
        self.log("  더 이상 다음 페이지 없음")
        return False

    async def run_buddy_comment(self, user_id: str, password: str,
                                gemini_api_key: str = "",
                                group_name: str = "이웃1",
                                cutoff_date: str = "",
                                sort_order: str = "업데이트순",
                                progress_callback: Callable[[int, int], None] = None):
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
            await self.ensure_login(user_id, password)

            blog_id = user_id

            self.log("=" * 50)
            self.log("Phase 1: 이웃 목록 수집 시작")
            self.log(f"그룹: {group_name} | 기준일: {cutoff_date} | 정렬: {sort_order}")
            self.log("=" * 50)

            await self._navigate_to_buddy_page(blog_id)
            frame = self._get_papermain_frame()
            if not frame:
                self.log("papermain 프레임 못 찾음")
                return

            await self._select_buddy_group(frame, group_name)
            await self._change_sort_order(frame, sort_order)

            all_targets = []
            page_num = 1

            while self.is_running:
                self.log(f"\n── 수집 페이지 {page_num} ──")
                frame = self._get_papermain_frame()
                if not frame:
                    self.log("papermain 프레임 없음")
                    break

                buddies = await self._extract_buddy_list(frame, sort_order)
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

            self.log("\n" + "=" * 50)
            self.log("Phase 2: 댓글 작성 시작")
            self.log("=" * 50)

            total = len(all_targets)
            comment_count = 0
            skip_count = 0
            deferred = []

            for i, buddy in enumerate(all_targets):
                if not self.is_running:
                    self.log("사용자에 의해 중단됨")
                    break

                if comment_count >= DAILY_ACTION_LIMIT:
                    self.log(f"\n일일 액션 제한({DAILY_ACTION_LIMIT}건) 도달 → 중단")
                    break

                target_id = buddy["blog_id"]
                nick = buddy["nick"]
                self.log(f"\n[{i+1}/{total}] {nick} ({target_id})")

                if progress_callback:
                    progress_callback(i + 1, total)

                log_no = await get_latest_post_log_no(self.page, target_id, self.log)
                if not log_no:
                    self.log(f"  logNo 못 찾음 - skip")
                    skip_count += 1
                    continue

                content, main_frame = await get_post_content(
                    self.page, target_id, log_no, self.log, self._get_main_frame
                )

                if not main_frame:
                    self.log(f"  [{target_id}] mainFrame 못 찾음 - skip")
                    skip_count += 1
                    continue

                await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await random_sleep(0.8, 2.0)
                await main_frame.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await random_sleep(1.5, 3.0)

                await click_sympathy_on_frame(main_frame, self.log)

                already = await check_my_comment_exists(main_frame, blog_id)
                if already:
                    self.log(f"  [{target_id}] 이미 내 댓글 존재 - skip")
                    skip_count += 1
                    continue

                comment = None
                if ai_generator and (content["title"] or content["body"]):
                    generated = await ai_generator.generate(content["title"], content["body"])
                    if generated:
                        comment = generated
                        self.log(f"  AI 댓글: '{comment}'")
                    else:
                        self.log(f"  AI 댓글 생성 3회 시도 모두 실패 - 보류")
                        deferred.append(buddy)
                        continue
                else:
                    self.log(f"  글 내용 없음 - skip")
                    skip_count += 1
                    continue

                if not comment:
                    skip_count += 1
                    continue

                result = await write_comment(main_frame, target_id, comment, self.log)
                if result:
                    comment_count += 1
                else:
                    skip_count += 1

                await HumanDelay.between_requests()
                await maybe_idle(self.log)

            if deferred and self.is_running and comment_count < DAILY_ACTION_LIMIT:
                self.log(f"\n{'=' * 50}")
                self.log(f"보류 목록 재시도: {len(deferred)}건")
                self.log("=" * 50)

                for i, buddy in enumerate(deferred):
                    if not self.is_running:
                        self.log("사용자에 의해 중단됨")
                        break

                    if comment_count >= DAILY_ACTION_LIMIT:
                        self.log(f"\n일일 액션 제한({DAILY_ACTION_LIMIT}건) 도달 → 중단")
                        break

                    target_id = buddy["blog_id"]
                    nick = buddy["nick"]
                    self.log(f"\n[보류 {i+1}/{len(deferred)}] {nick} ({target_id})")

                    log_no = await get_latest_post_log_no(self.page, target_id, self.log)
                    if not log_no:
                        self.log(f"  logNo 못 찾음 - skip")
                        skip_count += 1
                        continue

                    content, main_frame = await get_post_content(
                        self.page, target_id, log_no, self.log, self._get_main_frame
                    )

                    if not main_frame:
                        self.log(f"  [{target_id}] mainFrame 못 찾음 - skip")
                        skip_count += 1
                        continue

                    await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await random_sleep(0.8, 2.0)
                    await main_frame.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await random_sleep(1.5, 3.0)

                    already = await check_my_comment_exists(main_frame, blog_id)
                    if already:
                        self.log(f"  [{target_id}] 이미 내 댓글 존재 - skip")
                        skip_count += 1
                        continue

                    comment = None
                    if ai_generator and (content["title"] or content["body"]):
                        generated = await ai_generator.generate(content["title"], content["body"])
                        if generated:
                            comment = generated
                            self.log(f"  AI 댓글: '{comment}'")
                        else:
                            self.log(f"  AI 댓글 생성 재시도 실패 - skip")
                            skip_count += 1
                            continue
                    else:
                        self.log(f"  글 내용 없음 - skip")
                        skip_count += 1
                        continue

                    if not comment:
                        skip_count += 1
                        continue

                    result = await write_comment(main_frame, target_id, comment, self.log)
                    if result:
                        comment_count += 1
                    else:
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
