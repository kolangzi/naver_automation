from base_bot import NaverBaseBot
from blog_actions import get_post_content, load_comments, write_reply
from comment_ai import CommentGenerator
from utils import HumanDelay, random_sleep, maybe_idle, DAILY_ACTION_LIMIT, simulate_reading
import asyncio
import re
from datetime import date, timedelta
from typing import Callable, List, Optional


class ReplyBot(NaverBaseBot):

    def _parse_post_date(self, date_str: str) -> Optional[str]:
        date_str = date_str.strip().rstrip(".")

        # "2026. 2. 10." 형식
        m = re.match(r"(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})", date_str)
        if m:
            return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

        # "N시간 전", "N분 전" → 오늘
        if "시간 전" in date_str or "분 전" in date_str:
            return date.today().strftime("%Y-%m-%d")

        # "N일 전"
        m_days = re.match(r"(\d+)일\s*전", date_str)
        if m_days:
            d = date.today() - timedelta(days=int(m_days.group(1)))
            return d.strftime("%Y-%m-%d")

        return None

    async def _collect_posts_from_postlist(self, blog_id: str, cutoff_date: str) -> List[dict]:
        posts = []
        page_num = 1

        while self.is_running:
            url = (
                f"https://blog.naver.com/PostList.naver?"
                f"blogId={blog_id}&categoryNo=0&from=postList&currentPage={page_num}"
            )
            self.log(f"PostList 페이지 {page_num} 접속...")
            await self.page.goto(url)
            await HumanDelay.page_load()
            await random_sleep(2.0, 4.0)

            rows = await self.page.query_selector_all("table.blog2_categorylist tr")
            if not rows:
                self.log("  글 목록 테이블 없음")
                break

            found_old = False
            new_posts = 0

            for row in rows:
                title_td = await row.query_selector("td.title")
                date_td = await row.query_selector("td.date")
                if not title_td or not date_td:
                    continue

                date_span = await date_td.query_selector("span.date")
                if not date_span:
                    continue
                raw_date = (await date_span.inner_text()).strip()
                parsed_date = self._parse_post_date(raw_date)

                if not parsed_date:
                    continue

                if parsed_date < cutoff_date:
                    found_old = True
                    break

                links = await title_td.query_selector_all("a[href*='PostView']")
                if not links:
                    continue
                link = links[-1]
                href = await link.get_attribute("href") or ""
                m = re.search(r"logNo=(\d+)", href)
                if not m:
                    continue

                log_no = m.group(1)
                title_text = (await link.inner_text()).strip()

                posts.append({
                    "log_no": log_no,
                    "title": title_text,
                    "date": parsed_date,
                })
                new_posts += 1

            self.log(f"  {new_posts}개 글 수집 (날짜 ≥ {cutoff_date})")

            if found_old:
                self.log(f"기준일({cutoff_date})보다 오래된 글 발견 → 수집 종료")
                break

            next_links = await self.page.query_selector_all("div.blog2_paginate a._goPageTop")
            next_page_found = False
            for nl in next_links:
                nl_class = await nl.get_attribute("class") or ""
                param_match = re.search(r"_param\((\d+)\)", nl_class)
                if param_match and int(param_match.group(1)) == page_num + 1:
                    next_page_found = True
                    break

            if not next_page_found:
                self.log("마지막 페이지 도달")
                break

            page_num += 1

        return posts

    async def _parse_data_info(self, comment_el) -> dict:
        data_info = await comment_el.get_attribute("data-info") or ""
        info = {}
        for kv in data_info.split(","):
            kv = kv.strip()
            if ":" in kv:
                key, val = kv.split(":", 1)
                info[key.strip()] = val.strip().strip("'")
        return info

    async def _check_already_replied(self, main_frame, comment_no: str, my_blog_id: str) -> bool:
        comments = await main_frame.query_selector_all("li.u_cbox_comment")
        for c in comments:
            info = await self._parse_data_info(c)
            if info.get("replyLevel") != "2":
                continue
            if info.get("parentCommentNo") != comment_no:
                continue

            # 블로그주인 배지 확인
            editor_badge = await c.query_selector(".u_cbox_ico_editor")
            if editor_badge:
                return True

            # blog_id 링크 확인
            author_link = await c.query_selector(".u_cbox_name")
            if author_link:
                href = await author_link.get_attribute("href") or ""
                if my_blog_id.lower() in href.lower():
                    return True

        return False

    async def _process_comments_on_page(self, main_frame, my_blog_id: str,
                                         post_content: dict, log_no: str,
                                         ai_generator: CommentGenerator,
                                         deferred: list,
                                         current_total: int = 0) -> tuple:
        reply_count = 0
        skip_count = 0

        comments = await main_frame.query_selector_all("li.u_cbox_comment")
        for c in comments:
            if not self.is_running:
                break

            if (current_total + reply_count) >= DAILY_ACTION_LIMIT:
                self.log(f"    일일 액션 제한({DAILY_ACTION_LIMIT}건) 도달 → 중단")
                break

            info = await self._parse_data_info(c)
            if info.get("replyLevel") != "1":
                continue

            comment_no = info.get("commentNo", "")
            if not comment_no:
                continue

            nick_el = await c.query_selector(".u_cbox_nick")
            nick = comment_no
            if nick_el:
                nick = (await nick_el.inner_text()).strip()

            already = await self._check_already_replied(main_frame, comment_no, my_blog_id)
            if already:
                self.log(f"    [{nick}] 이미 답글 있음 - skip")
                skip_count += 1
                continue

            content_el = await c.query_selector(".u_cbox_contents")
            if not content_el:
                skip_count += 1
                continue
            comment_text = (await content_el.inner_text()).strip()

            if not comment_text:
                skip_count += 1
                continue

            generated = await ai_generator.generate_reply(
                post_content["title"], post_content["body"], comment_text
            )

            if not generated:
                self.log(f"    [{nick}] AI 대댓글 생성 실패 - 보류")
                deferred.append({
                    "comment_no": comment_no,
                    "nick": nick,
                    "comment_text": comment_text,
                    "post_content": post_content,
                    "log_no": log_no,
                    "blog_id": my_blog_id,
                })
                continue

            self.log(f"    [{nick}] AI 대댓글: '{generated}'")

            result = await write_reply(main_frame, comment_no, generated, self.log)
            if result:
                reply_count += 1
            else:
                skip_count += 1

            await HumanDelay.between_requests()

        return reply_count, skip_count

    async def run_reply(self, user_id: str, password: str,
                        gemini_api_key: str, blog_id: str = "",
                        cutoff_date: str = "",
                        progress_callback: Callable[[int, int], None] = None):
        self.is_running = True
        ai_generator = CommentGenerator(gemini_api_key)
        self.log("AI 대댓글 생성 모드 (Gemini - gemini-3-flash-preview)")

        if not blog_id:
            blog_id = user_id

        if not cutoff_date:
            cutoff_date = date.today().strftime("%Y-%m-%d")

        try:
            await self.start_browser(user_id)
            await self.ensure_login(user_id, password)

            self.log("=" * 50)
            self.log("Phase 1: 내 블로그 글 수집")
            self.log(f"블로그: {blog_id} | 기준일: {cutoff_date}")
            self.log("=" * 50)

            posts = await self._collect_posts_from_postlist(blog_id, cutoff_date)
            self.log(f"\nPhase 1 완료: {len(posts)}개 글 수집됨")

            if not posts:
                self.log("대상 글 없음. 종료.")
                return

            self.log("\n" + "=" * 50)
            self.log("Phase 2: 대댓글 작성 시작")
            self.log("=" * 50)

            total_posts = len(posts)
            total_replies = 0
            total_skips = 0
            all_deferred = []

            for i, post in enumerate(posts):
                if not self.is_running:
                    self.log("사용자에 의해 중단됨")
                    break

                if total_replies >= DAILY_ACTION_LIMIT:
                    self.log(f"\n일일 액션 제한({DAILY_ACTION_LIMIT}건) 도달 → 중단")
                    break

                log_no = post["log_no"]
                self.log(f"\n[{i+1}/{total_posts}] {post['title'][:50]} ({post['date']})")

                if progress_callback:
                    progress_callback(i + 1, total_posts)

                content, main_frame = await get_post_content(
                    self.page, blog_id, log_no, self.log, self._get_main_frame
                )

                if not main_frame:
                    self.log(f"  mainFrame 못 찾음 - skip")
                    total_skips += 1
                    continue

                body_len = len(content.get("body", "")) if content else 0
                await simulate_reading(body_len, self.log)

                await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await random_sleep(0.8, 2.0)
                await main_frame.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await random_sleep(1.5, 3.0)

                loaded = await load_comments(main_frame, self.log)
                if not loaded:
                    total_skips += 1
                    continue

                # 댓글 첫 페이지로 이동
                first_page_btn = await main_frame.query_selector(
                    ".u_cbox_paginate a.u_cbox_page[data-param='1']"
                )
                if first_page_btn:
                    await first_page_btn.evaluate("el => el.click()")
                    await random_sleep(1.5, 3.0)

                comment_page = 1
                while self.is_running:
                    self.log(f"  댓글 페이지 {comment_page}")

                    replies, skips = await self._process_comments_on_page(
                        main_frame, blog_id, content, log_no, ai_generator, all_deferred,
                        current_total=total_replies
                    )
                    total_replies += replies
                    total_skips += skips

                    next_page_btn = await main_frame.query_selector(
                        f".u_cbox_paginate a.u_cbox_page[data-param='{comment_page + 1}']"
                    )
                    if not next_page_btn:
                        break

                    await next_page_btn.evaluate("el => el.click()")
                    await random_sleep(1.5, 3.0)
                    comment_page += 1

                await HumanDelay.between_requests()
                await maybe_idle(self.log)

            # 보류 목록 재시도
            if all_deferred and self.is_running and total_replies < DAILY_ACTION_LIMIT:
                self.log(f"\n{'=' * 50}")
                self.log(f"보류 목록 재시도: {len(all_deferred)}건")
                self.log("=" * 50)

                for i, item in enumerate(all_deferred):
                    if not self.is_running:
                        break

                    if total_replies >= DAILY_ACTION_LIMIT:
                        self.log(f"\n일일 액션 제한({DAILY_ACTION_LIMIT}건) 도달 → 중단")
                        break

                    self.log(f"\n[보류 {i+1}/{len(all_deferred)}] {item['nick']} (댓글#{item['comment_no']})")

                    content, main_frame = await get_post_content(
                        self.page, item["blog_id"], item["log_no"],
                        self.log, self._get_main_frame
                    )

                    if not main_frame:
                        self.log(f"  mainFrame 못 찾음 - skip")
                        total_skips += 1
                        continue

                    body_len = len(content.get("body", "")) if content else 0
                    await simulate_reading(body_len, self.log)

                    await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await random_sleep(0.8, 2.0)
                    await main_frame.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await random_sleep(1.5, 3.0)

                    loaded = await load_comments(main_frame, self.log)
                    if not loaded:
                        total_skips += 1
                        continue

                    already = await self._check_already_replied(
                        main_frame, item["comment_no"], item["blog_id"]
                    )
                    if already:
                        self.log(f"  이미 답글 있음 - skip")
                        total_skips += 1
                        continue

                    generated = await ai_generator.generate_reply(
                        item["post_content"]["title"],
                        item["post_content"]["body"],
                        item["comment_text"],
                    )
                    if not generated:
                        self.log(f"  AI 대댓글 재시도 실패 - skip")
                        total_skips += 1
                        continue

                    self.log(f"  AI 대댓글: '{generated}'")

                    result = await write_reply(main_frame, item["comment_no"], generated, self.log)
                    if result:
                        total_replies += 1
                    else:
                        total_skips += 1

                    await HumanDelay.between_requests()

            self.log(f"\n{'=' * 50}")
            self.log(f"완료! 글 {total_posts}개 | 대댓글: {total_replies}개 | 스킵: {total_skips}개")
            self.log("=" * 50)

        except Exception as e:
            self.log(f"실행 오류: {str(e)}")
        finally:
            await self.close_browser()
            self.is_running = False
