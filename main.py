import customtkinter as ctk
import asyncio
import threading
from datetime import date
from browser_automation import NaverNeighborBot

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class NaverNeighborApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("소현이의 서로이웃 자동 신청 후후")
        self.geometry("600x950")
        self.resizable(False, False)

        self.bot = None
        self.is_running = False

        self._create_widgets()

    def _create_widgets(self):
        title_label = ctk.CTkLabel(
            self, text="소현이의 서로이웃 자동 신청 후후",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title_label.pack(pady=15)

        self.tabview = ctk.CTkTabview(self, width=560, height=480)
        self.tabview.pack(padx=20, pady=5)

        self.tabview.add("서로이웃 신청")
        self.tabview.add("서로이웃 댓글")

        self._create_tab1()
        self._create_tab2()

        self.progress_label = ctk.CTkLabel(self, text="대기 중...")
        self.progress_label.pack(pady=5)

        self.progress_bar = ctk.CTkProgressBar(self, width=500)
        self.progress_bar.pack(pady=5)
        self.progress_bar.set(0)

        log_label = ctk.CTkLabel(self, text="실행 로그", font=ctk.CTkFont(weight="bold"))
        log_label.pack(pady=(10, 5))

        self.log_textbox = ctk.CTkTextbox(self, width=550, height=250)
        self.log_textbox.pack(padx=20, pady=10)

    def _create_tab1(self):
        tab = self.tabview.tab("서로이웃 신청")

        input_frame = ctk.CTkFrame(tab)
        input_frame.pack(padx=10, pady=5, fill="x")

        url_label = ctk.CTkLabel(input_frame, text="블로그 URL:")
        url_label.grid(row=0, column=0, padx=10, pady=8, sticky="w")
        self.url_entry = ctk.CTkEntry(input_frame, width=380, placeholder_text="https://blog.naver.com/...")
        self.url_entry.grid(row=0, column=1, padx=10, pady=8)

        id_label = ctk.CTkLabel(input_frame, text="네이버 ID:")
        id_label.grid(row=1, column=0, padx=10, pady=8, sticky="w")
        self.id_entry = ctk.CTkEntry(input_frame, width=380, placeholder_text="lizidemarron")
        self.id_entry.grid(row=1, column=1, padx=10, pady=8)

        pw_label = ctk.CTkLabel(input_frame, text="비밀번호:")
        pw_label.grid(row=2, column=0, padx=10, pady=8, sticky="w")
        self.pw_entry = ctk.CTkEntry(input_frame, width=380, placeholder_text="비밀번호 입력", show="*")
        self.pw_entry.grid(row=2, column=1, padx=10, pady=8)

        neighbor_msg_label = ctk.CTkLabel(input_frame, text="신청 메시지:")
        neighbor_msg_label.grid(row=3, column=0, padx=10, pady=8, sticky="w")
        self.neighbor_msg_entry = ctk.CTkEntry(
            input_frame, width=380,
            placeholder_text="블로그 글 잘 봤습니다. 서로이웃 신청드려요!"
        )
        self.neighbor_msg_entry.grid(row=3, column=1, padx=10, pady=8)

        comment_frame = ctk.CTkFrame(tab)
        comment_frame.pack(padx=10, pady=5, fill="x")

        self.comment_toggle_var = ctk.BooleanVar(value=True)
        self.comment_toggle = ctk.CTkSwitch(
            comment_frame, text="서로이웃 신청 성공 시 최신글에 댓글 남기기",
            variable=self.comment_toggle_var,
            command=self._on_comment_toggle
        )
        self.comment_toggle.grid(row=0, column=0, columnspan=2, padx=10, pady=8, sticky="w")

        comment_text_label = ctk.CTkLabel(comment_frame, text="댓글 내용:")
        comment_text_label.grid(row=1, column=0, padx=10, pady=8, sticky="w")
        self.comment_entry = ctk.CTkEntry(
            comment_frame, width=380,
            placeholder_text="안녕하세요! 글 잘 봤습니다 :)"
        )
        self.comment_entry.grid(row=1, column=1, padx=10, pady=8)

        api_key_label = ctk.CTkLabel(comment_frame, text="Gemini API 키:")
        api_key_label.grid(row=2, column=0, padx=10, pady=8, sticky="w")
        self.api_key_entry = ctk.CTkEntry(
            comment_frame, width=380,
            placeholder_text="Gemini API 키 입력 (필수)"
        )
        self.api_key_entry.grid(row=2, column=1, padx=10, pady=8)

        btn_frame = ctk.CTkFrame(tab, fg_color="transparent")
        btn_frame.pack(pady=10)

        self.start_btn = ctk.CTkButton(
            btn_frame, text="시작", width=150, height=40,
            command=self._on_start, fg_color="green", hover_color="darkgreen"
        )
        self.start_btn.grid(row=0, column=0, padx=10)

        self.stop_btn = ctk.CTkButton(
            btn_frame, text="중지", width=150, height=40,
            command=self._on_stop, fg_color="red", hover_color="darkred",
            state="disabled"
        )
        self.stop_btn.grid(row=0, column=1, padx=10)

    def _create_tab2(self):
        tab = self.tabview.tab("서로이웃 댓글")

        input_frame = ctk.CTkFrame(tab)
        input_frame.pack(padx=10, pady=5, fill="x")

        id_label = ctk.CTkLabel(input_frame, text="네이버 ID:")
        id_label.grid(row=0, column=0, padx=10, pady=8, sticky="w")
        self.t2_id_entry = ctk.CTkEntry(input_frame, width=380, placeholder_text="lizidemarron")
        self.t2_id_entry.grid(row=0, column=1, padx=10, pady=8)

        pw_label = ctk.CTkLabel(input_frame, text="비밀번호:")
        pw_label.grid(row=1, column=0, padx=10, pady=8, sticky="w")
        self.t2_pw_entry = ctk.CTkEntry(input_frame, width=380, placeholder_text="비밀번호 입력", show="*")
        self.t2_pw_entry.grid(row=1, column=1, padx=10, pady=8)

        api_key_label = ctk.CTkLabel(input_frame, text="Gemini API 키:")
        api_key_label.grid(row=2, column=0, padx=10, pady=8, sticky="w")
        self.t2_api_key_entry = ctk.CTkEntry(
            input_frame, width=380,
            placeholder_text="Gemini API 키 입력 (필수)"
        )
        self.t2_api_key_entry.grid(row=2, column=1, padx=10, pady=8)

        group_label = ctk.CTkLabel(input_frame, text="그룹 이름:")
        group_label.grid(row=3, column=0, padx=10, pady=8, sticky="w")
        self.t2_group_entry = ctk.CTkEntry(input_frame, width=380, placeholder_text="이웃1")
        self.t2_group_entry.grid(row=3, column=1, padx=10, pady=8)

        date_label = ctk.CTkLabel(input_frame, text="기준 날짜:")
        date_label.grid(row=4, column=0, padx=10, pady=8, sticky="w")
        self.t2_date_entry = ctk.CTkEntry(input_frame, width=380, placeholder_text="YYYY-MM-DD")
        self.t2_date_entry.insert(0, date.today().strftime("%Y-%m-%d"))
        self.t2_date_entry.grid(row=4, column=1, padx=10, pady=8)

        desc_label = ctk.CTkLabel(
            tab, text="기준 날짜 이후 글을 올린 서로이웃의 최신글에 AI 댓글을 남깁니다.",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        desc_label.pack(pady=5)

        btn_frame = ctk.CTkFrame(tab, fg_color="transparent")
        btn_frame.pack(pady=10)

        self.t2_start_btn = ctk.CTkButton(
            btn_frame, text="시작", width=150, height=40,
            command=self._on_start_buddy_comment, fg_color="green", hover_color="darkgreen"
        )
        self.t2_start_btn.grid(row=0, column=0, padx=10)

        self.t2_stop_btn = ctk.CTkButton(
            btn_frame, text="중지", width=150, height=40,
            command=self._on_stop, fg_color="red", hover_color="darkred",
            state="disabled"
        )
        self.t2_stop_btn.grid(row=0, column=1, padx=10)

    def _log(self, message: str):
        self.log_textbox.insert("end", f"{message}\n")
        self.log_textbox.see("end")

    def _update_progress(self, current: int, total: int):
        self.progress_label.configure(text=f"진행 중: {current}/{total}")
        self.progress_bar.set(current / total if total > 0 else 0)

    def _on_comment_toggle(self):
        if self.comment_toggle_var.get():
            self.comment_entry.configure(state="normal")
            self.api_key_entry.configure(state="normal")
        else:
            self.comment_entry.configure(state="disabled")
            self.api_key_entry.configure(state="disabled")

    def _set_running(self, running: bool):
        self.is_running = running
        state_start = "disabled" if running else "normal"
        state_stop = "normal" if running else "disabled"
        self.start_btn.configure(state=state_start)
        self.stop_btn.configure(state=state_stop)
        self.t2_start_btn.configure(state=state_start)
        self.t2_stop_btn.configure(state=state_stop)

    def _on_start(self):
        blog_url = self.url_entry.get().strip()
        user_id = self.id_entry.get().strip() or "lizidemarron"
        password = self.pw_entry.get()
        enable_comment = self.comment_toggle_var.get()
        comment_text = self.comment_entry.get().strip() or "안녕하세요! 글 잘 봤습니다 :)"
        gemini_api_key = self.api_key_entry.get().strip()
        neighbor_message = self.neighbor_msg_entry.get().strip() or "블로그 글 잘 봤습니다. 서로이웃 신청드려요!"

        if not blog_url or not password:
            self._log("블로그 URL과 비밀번호를 입력해주세요!")
            return

        if enable_comment and not gemini_api_key:
            self._log("댓글 기능을 사용하려면 Gemini API 키를 입력해주세요!")
            return

        self._set_running(True)

        thread = threading.Thread(
            target=self._run_bot,
            args=(blog_url, user_id, password, enable_comment, comment_text, gemini_api_key, neighbor_message)
        )
        thread.daemon = True
        thread.start()

    def _on_start_buddy_comment(self):
        user_id = self.t2_id_entry.get().strip() or "lizidemarron"
        password = self.t2_pw_entry.get()
        gemini_api_key = self.t2_api_key_entry.get().strip()
        group_name = self.t2_group_entry.get().strip() or "이웃1"
        cutoff_date = self.t2_date_entry.get().strip() or date.today().strftime("%Y-%m-%d")

        if not password:
            self._log("비밀번호를 입력해주세요!")
            return

        if not gemini_api_key:
            self._log("Gemini API 키를 입력해주세요!")
            return

        self._set_running(True)

        thread = threading.Thread(
            target=self._run_buddy_comment_bot,
            args=(user_id, password, gemini_api_key, group_name, cutoff_date)
        )
        thread.daemon = True
        thread.start()

    def _run_bot(self, blog_url: str, user_id: str, password: str,
                 enable_comment: bool, comment_text: str, gemini_api_key: str,
                 neighbor_message: str):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        self.bot = NaverNeighborBot(
            log_callback=lambda msg: self.after(0, self._log, msg)
        )

        try:
            loop.run_until_complete(
                self.bot.run(
                    blog_url, user_id, password,
                    progress_callback=lambda c, t: self.after(0, self._update_progress, c, t),
                    enable_comment=enable_comment,
                    comment_text=comment_text,
                    gemini_api_key=gemini_api_key,
                    neighbor_message=neighbor_message
                )
            )
        finally:
            loop.close()
            self.after(0, self._on_complete)

    def _run_buddy_comment_bot(self, user_id: str, password: str,
                                gemini_api_key: str, group_name: str,
                                cutoff_date: str):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        self.bot = NaverNeighborBot(
            log_callback=lambda msg: self.after(0, self._log, msg)
        )

        try:
            loop.run_until_complete(
                self.bot.run_buddy_comment(
                    user_id, password,
                    gemini_api_key=gemini_api_key,
                    group_name=group_name,
                    cutoff_date=cutoff_date,
                    progress_callback=lambda c, t: self.after(0, self._update_progress, c, t),
                )
            )
        finally:
            loop.close()
            self.after(0, self._on_complete)

    def _on_stop(self):
        if self.bot:
            self.bot.stop()
        self._log("중지 요청됨...")

    def _on_complete(self):
        self._set_running(False)
        self.progress_label.configure(text="완료!")

if __name__ == "__main__":
    app = NaverNeighborApp()
    app.mainloop()
