import customtkinter as ctk
import asyncio
import threading
from browser_automation import NaverNeighborBot

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class NaverNeighborApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("소현이의 서로이웃 자동 신청 후후")
        self.geometry("600x850")
        self.resizable(False, False)

        self.bot = None
        self.is_running = False

        self._create_widgets()

    def _create_widgets(self):
        # 제목
        title_label = ctk.CTkLabel(
            self, text="소현이의 서로이웃 자동 신청 후후",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title_label.pack(pady=20)

        # 입력 프레임
        input_frame = ctk.CTkFrame(self)
        input_frame.pack(padx=20, pady=10, fill="x")

        # 블로그 URL
        url_label = ctk.CTkLabel(input_frame, text="블로그 URL:")
        url_label.grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.url_entry = ctk.CTkEntry(input_frame, width=400, placeholder_text="https://blog.naver.com/...")
        self.url_entry.grid(row=0, column=1, padx=10, pady=10)

        # 네이버 ID
        id_label = ctk.CTkLabel(input_frame, text="네이버 ID:")
        id_label.grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.id_entry = ctk.CTkEntry(input_frame, width=400, placeholder_text="lizidemarron")
        self.id_entry.grid(row=1, column=1, padx=10, pady=10)

        # 비밀번호
        pw_label = ctk.CTkLabel(input_frame, text="비밀번호:")
        pw_label.grid(row=2, column=0, padx=10, pady=10, sticky="w")
        self.pw_entry = ctk.CTkEntry(input_frame, width=400, placeholder_text="비밀번호 입력", show="*")
        self.pw_entry.grid(row=2, column=1, padx=10, pady=10)

        neighbor_msg_label = ctk.CTkLabel(input_frame, text="신청 메시지:")
        neighbor_msg_label.grid(row=3, column=0, padx=10, pady=10, sticky="w")
        self.neighbor_msg_entry = ctk.CTkEntry(
            input_frame, width=400,
            placeholder_text="블로그 글 잘 봤습니다. 서로이웃 신청드려요!"
        )
        self.neighbor_msg_entry.grid(row=3, column=1, padx=10, pady=10)

        comment_frame = ctk.CTkFrame(self)
        comment_frame.pack(padx=20, pady=10, fill="x")

        self.comment_toggle_var = ctk.BooleanVar(value=True)
        self.comment_toggle = ctk.CTkSwitch(
            comment_frame, text="서로이웃 신청 성공 시 최신글에 댓글 남기기",
            variable=self.comment_toggle_var,
            command=self._on_comment_toggle
        )
        self.comment_toggle.grid(row=0, column=0, columnspan=2, padx=10, pady=10, sticky="w")

        comment_text_label = ctk.CTkLabel(comment_frame, text="댓글 내용:")
        comment_text_label.grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.comment_entry = ctk.CTkEntry(
            comment_frame, width=400,
            placeholder_text="안녕하세요! 글 잘 봤습니다 :)"
        )
        self.comment_entry.grid(row=1, column=1, padx=10, pady=10)

        api_key_label = ctk.CTkLabel(comment_frame, text="Gemini API 키:")
        api_key_label.grid(row=2, column=0, padx=10, pady=10, sticky="w")
        self.api_key_entry = ctk.CTkEntry(
            comment_frame, width=400,
            placeholder_text="비워두면 고정 댓글 사용"
        )
        self.api_key_entry.grid(row=2, column=1, padx=10, pady=10)

        # 버튼 프레임
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=20)

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

        # 진행률
        self.progress_label = ctk.CTkLabel(self, text="대기 중...")
        self.progress_label.pack(pady=5)

        self.progress_bar = ctk.CTkProgressBar(self, width=500)
        self.progress_bar.pack(pady=5)
        self.progress_bar.set(0)

        # 로그 영역
        log_label = ctk.CTkLabel(self, text="실행 로그", font=ctk.CTkFont(weight="bold"))
        log_label.pack(pady=(20, 5))

        self.log_textbox = ctk.CTkTextbox(self, width=550, height=300)
        self.log_textbox.pack(padx=20, pady=10)

    def _log(self, message: str):
        """로그 추가"""
        self.log_textbox.insert("end", f"{message}\n")
        self.log_textbox.see("end")

    def _update_progress(self, current: int, total: int):
        """진행률 업데이트"""
        self.progress_label.configure(text=f"진행 중: {current}/{total}")
        self.progress_bar.set(current / total)

    def _on_comment_toggle(self):
        if self.comment_toggle_var.get():
            self.comment_entry.configure(state="normal")
            self.api_key_entry.configure(state="normal")
        else:
            self.comment_entry.configure(state="disabled")
            self.api_key_entry.configure(state="disabled")

    def _on_start(self):
        blog_url = self.url_entry.get().strip()
        user_id = self.id_entry.get().strip() or "lizidemarron"
        password = self.pw_entry.get()
        enable_comment = self.comment_toggle_var.get()
        comment_text = self.comment_entry.get().strip() or "안녕하세요! 글 잘 봤습니다 :)"
        gemini_api_key = self.api_key_entry.get().strip()
        neighbor_message = self.neighbor_msg_entry.get().strip() or "블로그 글 잘 봤습니다. 서로이웃 신청드려요!"

        if not blog_url or not password:
            self._log("모든 필드를 입력해주세요!")
            return

        self.is_running = True
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")

        thread = threading.Thread(
            target=self._run_bot,
            args=(blog_url, user_id, password, enable_comment, comment_text, gemini_api_key, neighbor_message)
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

    def _on_stop(self):
        """중지 버튼 클릭"""
        if self.bot:
            self.bot.stop()
        self._log("중지 요청됨...")

    def _on_complete(self):
        """실행 완료"""
        self.is_running = False
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.progress_label.configure(text="완료!")

if __name__ == "__main__":
    app = NaverNeighborApp()
    app.mainloop()
