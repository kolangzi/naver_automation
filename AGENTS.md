<!-- Generated: 2026-03-30 | Updated: 2026-03-30 -->

# naver_automation

## Purpose
네이버 블로그 서로이웃 관리 자동화 도구. Playwright 기반 브라우저 자동화와 Gemini AI를 결합하여 서로이웃 신청, AI 댓글 작성, 대댓글 작성을 수행하는 CustomTkinter GUI 데스크톱 애플리케이션.

## Key Files

| File | Description |
|------|-------------|
| `main.py` | GUI 엔트리포인트. CustomTkinter 기반 3탭 UI (서로이웃 신청 / 서로이웃 댓글 / 대댓글). 각 기능을 별도 스레드에서 asyncio 루프로 실행 |
| `base_bot.py` | `NaverBaseBot` 베이스 클래스. Playwright persistent context 브라우저 관리, 로그인 상태 확인/대기, stealth 모드, iframe 탐색 (`PostView`, `papermain`) |
| `neighbor_request.py` | `NeighborRequestBot` — 기능1: 특정 블로그 글의 공감 목록에서 사용자를 찾아 서로이웃 신청. 팝업 기반 신청 플로우 처리 |
| `buddy_comment.py` | `BuddyCommentBot` — 기능2: 이웃 관리 페이지에서 서로이웃 목록 수집 후, 각 이웃의 최신 글에 AI 댓글 작성. 2-Phase (수집 → 댓글) |
| `reply_bot.py` | `ReplyBot` — 기능3: 내 블로그 글의 댓글에 AI 대댓글 작성. PostList에서 글 수집 후 댓글 페이지네이션 처리. dry-run 모드 지원 |
| `blog_actions.py` | 블로그 DOM 조작 함수 모음: 공감 클릭, 최신글 logNo 추출, 글 내용 파싱, 댓글 존재 확인, 댓글/대댓글 작성 |
| `comment_ai.py` | `CommentGenerator` — Gemini 2.5 Flash API로 댓글/대댓글 생성. Rate limit 보호, 재시도 로직, 30대 여성 블로거 페르소나 프롬프트 |
| `utils.py` | `HumanDelay`, `random_sleep`, `maybe_idle`, `simulate_reading`, `DAILY_ACTION_LIMIT` — 자동화 탐지 회피용 인간적 딜레이 및 일일 액션 제한 유틸리티 |
| `requirements.txt` | 의존성: playwright, customtkinter, google-genai, playwright-stealth |
| `install.sh` | 설치 스크립트 |
| `run.sh` | 실행 스크립트 |

## Architecture

```
main.py (GUI - CustomTkinter)
├── NeighborRequestBot (neighbor_request.py)  ← 기능1: 서로이웃 신청
├── BuddyCommentBot (buddy_comment.py)        ← 기능2: 서로이웃 댓글
└── ReplyBot (reply_bot.py)                   ← 기능3: 대댓글
    │
    ├── NaverBaseBot (base_bot.py)            ← 공통 브라우저/로그인
    ├── blog_actions.py                       ← DOM 조작 유틸
    ├── comment_ai.py                         ← Gemini AI 댓글 생성
    └── utils.py                              ← 딜레이/제한 유틸
```

## For AI Agents

### Working In This Directory
- 모든 봇 클래스는 `NaverBaseBot`을 상속. 브라우저 관련 변경은 `base_bot.py`에서 시작
- 네이버 DOM 셀렉터가 핵심 — 네이버 UI 변경 시 셀렉터 업데이트 필요
- GUI(`main.py`)와 봇 로직은 스레드로 분리됨. GUI 업데이트는 `self.after(0, callback)` 패턴 사용
- `log_callback` 패턴으로 모든 봇이 GUI에 로그 전달
- `blog_actions.py`는 stateless 함수 모음이고, iframe(`main_frame`) 참조를 받아 동작

### Testing Requirements
- Playwright 브라우저 기반이므로 단위 테스트보다 수동 테스트 위주
- `ReplyBot`의 `dry_run=True` 모드로 대댓글 기능 검증 가능
- Gemini API 키 필요 (기능2, 기능3)

### Common Patterns
- **2-Phase 패턴**: Phase 1에서 대상 수집, Phase 2에서 액션 실행 (buddy_comment, reply_bot)
- **보류(deferred) 재시도**: AI 생성 실패 시 보류 목록에 추가 후 마지막에 재시도
- **일일 액션 제한**: `DAILY_ACTION_LIMIT=50` — 계정당 실행 당 댓글/대댓글 최대 수. 안티봇 탐지 회피 목적. 제거 시 계정 잠금 위험
- **Human-like delay**: `HumanDelay`, `random_sleep`, `maybe_idle`로 탐지 회피
- **iframe 탐색**: 네이버 블로그는 iframe 구조 — `_get_main_frame()` (PostView), `_get_papermain_frame()` (관리페이지)
- **persistent context**: `~/.naver_automation/profiles/{user_id}`에 브라우저 프로필 저장하여 로그인 세션 유지

## Dependencies

### External
- `playwright` >= 1.40.0 — 브라우저 자동화
- `playwright-stealth` >= 1.0.0 — 자동화 탐지 회피
- `customtkinter` >= 5.2.0 — 다크모드 GUI
- `google-genai` >= 1.0.0 — Gemini AI API 클라이언트

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
