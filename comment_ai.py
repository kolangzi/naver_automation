import time
from google import genai
from typing import Optional


class CommentGenerator:
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)
        self.model = 'gemini-2.5-flash'

    def generate(self, title: str, body: str) -> Optional[str]:
        prompt = (
            "너는 30대 여성 네이버 블로거야.\n"
            "아래 블로그 글을 읽고, 글 내용에 맞는 자연스러운 댓글을 15자 내외로 작성해.\n"
            "규칙:\n"
            "- 15자 내외 (10~20자)\n"
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
                if '429' in error_msg and attempt < 2:
                    wait = (attempt + 1) * 15
                    print(f"Gemini API 할당량 초과 - {wait}초 후 재시도 ({attempt+1}/3)")
                    time.sleep(wait)
                    continue
                print(f"Gemini API 오류: {e}")
                return None
        return None
