import time
from google import genai
from typing import Optional


class CommentGenerator:
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)
        self.model = 'gemini-2.5-flash-lite'
        self._last_request_time = 0.0
        self._min_interval = 4.0  # RPM 15 = 4초/요청

    def _wait_rate_limit(self):
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_interval:
            sleep_time = self._min_interval - elapsed
            print(f"Rate limit 보호: {sleep_time:.1f}초 대기")
            time.sleep(sleep_time)

    def _is_retryable_error(self, error_msg: str) -> bool:
        retryable_codes = ['429', '500', '503', '504',
                           'RESOURCE_EXHAUSTED', 'INTERNAL',
                           'UNAVAILABLE', 'DEADLINE_EXCEEDED']
        return any(code in error_msg for code in retryable_codes)

    def generate(self, title: str, body: str) -> Optional[str]:
        prompt = (
            "너는 30대 여성 네이버 블로거야.\n"
            "아래 블로그 글을 읽고, 글 내용에 맞는 자연스러운 댓글을 작성해.\n"
            "규칙:\n"
            "- 25자 내외 (20~30자)\n"
            "- 30대 여자 말투 (부드럽고 친근한 존댓말, 예: ~요, ~네요, ~좋아요)\n"
            "- 'ㅎㅎㅎ' 또는 내용에 어울리는 표정, 제스처 이모티콘 쓰기 (예:😆,😌,🥹,😠,👍🏻)\n"
            "- 광고성/스팸 금지\n"
            "- 댓글 내용만 출력 (따옴표, 설명 없이)\n\n"
            f"제목: {title}\n"
            f"본문: {body[:500]}\n\n"
            "댓글:"
        )

        for attempt in range(3):
            try:
                self._wait_rate_limit()
                self._last_request_time = time.time()

                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt
                )
                comment = response.text.strip().strip('"').strip("'")
                if len(comment) > 50:
                    comment = comment[:50]
                return comment
            except Exception as e:
                error_msg = str(e)
                if self._is_retryable_error(error_msg) and attempt < 2:
                    # exponential backoff: 15초 → 30초 → 60초
                    wait = 15 * (2 ** attempt)
                    print(f"Gemini API 일시적 오류 - {wait}초 후 재시도 ({attempt+1}/3): {error_msg[:80]}")
                    time.sleep(wait)
                    continue
                print(f"Gemini API 오류 (복구 불가): {e}")
                return None
        return None
