# HANDOFF — Anti-bot Detection Hardening

> Claude Code 세션 핸드오프 문서. 다른 PC 또는 새 대화에서 작업을 이어갈 때 이 파일을 첫 컨텍스트로 사용.
>
> **새 대화에서**: "HANDOFF.md를 읽고 진행 상황 파악한 다음, 다음 단계 논의하자"라고 지시하면 됨.

---

## 한 줄 요약
네이버 서로이웃 봇 계정이 DAILY_ACTION_LIMIT=50 환경에서도 안티봇 탐지로 **간헐적으로 잠김**(영구 밴 아니고 본인인증으로 해제 가능). 원인 후보를 식별해 Bucket 단위로 incremental 패치 중. **Bucket 1·2 적용 완료**, Bucket 3·4·5·0 대기.

---

## 작업 브랜치 & 커밋
- 브랜치: `feat/anti-bot-detection-hardening`
- 베이스: `main`
- **push 정책**: 사용자가 수동 (commit은 Claude가 진행)

### 커밋 규칙 (사용자 합의)
- `git commit -s` 사용 (Signed-off-by 자동)
- **AI 도구·에이전트 레퍼런스 금지** (Claude/Copilot/GPT 등 일체 언급 X)
- **`Co-Authored-By` 라인 금지**
- 메시지 형식: `type: 한국어 제목` + 본문 불릿. 제목은 `~/.gitmessage.txt` 템플릿 참고

### 누적 커밋
| 커밋 | 메시지 |
|---|---|
| `b950a23` | feat: 안티봇 탐지 회피 — UA 프로필 고정 및 팝업 stealth 적용 |
| `e12ca29` | feat: 안티봇 탐지 회피 — 일일 한도 통합 및 전환율 랜덤화 |
| `7020a91` | fix: 공감을 댓글 등록 성공 후로 이동 — 공감만 누르는 케이스 제거 |

---

## 진단 (원인 가설 정리)

### 영향도 高 — 거의 확실
1. **UA 매 실행 랜덤 로테이션 + 영구 프로필** → 같은 쿠키·지문에 다른 UA 매칭. 강한 봇 시그널. **(Bucket 1로 해결)**
2. **`evaluate('el => el.click()')` — trusted event 부재**. `MouseEvent.isTrusted === false`로 서버에서 태깅 가능. **(Bucket 3 대기)**
3. **댓글 본문 `innerText` 주입** — 한국어 IME composition 이벤트 0개. 한글 댓글 즉시 생성은 인간적으로 불가능. **(Bucket 3 대기)**
4. **3탭 합산 실질 액션 150+/일 가능** (탭별 50건 + 공감 별도). **(Bucket 2로 해결)**

### 영향도 中
5. **100% 공감·댓글 전환율** — 방문 = 무조건 engage. 휴리스틱으로 즉시 잡힘. **(Bucket 2로 해결)**
6. **AI 댓글 구조적 균질성** — 같은 프롬프트, 25자, `~요`, 이모지 항상. **(Bucket 4 대기)**
7. **팝업(서로이웃 신청창)에 stealth 미적용** — 가장 민감한 폼이 raw Playwright 지문 노출. **(Bucket 1로 해결)**

### 영향도 低
8. 시간대 윈도우 없음 (새벽 동작 가능)
9. 행동 리듬 uniform 분포 (long-tail이 더 인간적)
10. 같은 페이지 빠른 재로드, deferred 재시도로 같은 블로그 2회 방문

---

## 완료된 Bucket

### ✅ Bucket 1 — 지문 누수 차단 (`b950a23`)
**파일**: `base_bot.py`

- **UA 프로필 고정**:
  - `_get_or_create_user_agent(profile_dir)` 신규 함수
  - `~/.naver_automation/profiles/{user_id}/ua.txt`에 UA 저장 → 같은 프로필은 영구 동일 UA 사용
- **팝업 stealth 자동 적용**:
  - `self._stealth = Stealth()` 인스턴스 보존
  - `self.context.on("page", self._on_new_page)` 이벤트 리스너로 새 페이지(팝업·탭)에 자동 적용
  - `_on_new_page`는 동기 콜백, `asyncio.create_task`로 비동기 stealth 예약

### ✅ Bucket 2 — 행동 볼륨 (`e12ca29` + `7020a91`)
**파일**: `utils.py`, `neighbor_request.py`, `buddy_comment.py`, `reply_bot.py`

- **일일 한도**:
  - `DAILY_ACTION_LIMIT = 30` (기존 50)
  - `load_daily_count(user_id)` / `increment_daily_count(user_id)` / `daily_limit_reached(user_id)` — `~/.naver_automation/profiles/{user_id}/daily_actions.json`에 합산 카운트 영속화
  - 자정 넘어가면 날짜 비교로 자동 리셋, JSON 손상 시 0 복구
- **3탭 합산**:
  - 댓글·대댓글·이웃신청은 같은 카운터 공유
  - **공감은 카운트 X** (패시브 액션, 카운터 부담 최소화)
- **dry_run 보호**:
  - 대댓글 탭 dry_run 모드는 한도 체크 우회 + 카운터 미반영
- **전환율 랜덤화** (`buddy_comment.py`):
  - `should_engage(probability)` 헬퍼
  - 댓글 **85%** 확률 진행 (15%는 "그냥 읽고 지나감")
  - 공감 **75%** 확률
- **공감-댓글 순서 변경** (`7020a91`):
  - 기존: 공감 → 검증 → 댓글 (실패해도 공감은 남음)
  - 변경: **댓글 등록 성공 직후에만** 75% 확률로 공감
  - 보장: "공감만 누르고 댓글 없는 케이스"는 모든 분기에서 발생 안 함

---

## 남은 작업

### 🟠 Bucket 3 — Trusted Event 입력 (영향도 中, 리스크 中)
**의심 효과**: 매우 강한 시그널 제거. 단 거의 모든 interaction 코드 재작성 필요 → 회귀 위험 있음.

- **합성 클릭 → 실제 클릭**:
  - `element.evaluate('el => el.click()')` → `await element.click()` (Playwright native)
  - 적용: 공감 버튼, 댓글 등록, 답글 등록, 페이지네이션 등
  - hidden/overlay 요소는 evaluate fallback 유지
- **댓글 본문 입력**:
  - `el.innerText = text` → `await page.keyboard.type(text, delay=random.uniform(50, 150))`
  - 한국어 IME 시뮬: composition 이벤트 수동 발사 또는 `insertText` 검토
  - 적용: `write_comment`, `write_reply`, 이웃 신청 메시지

### 🟡 Bucket 4 — AI 댓글 다양화 (영향도 中, 리스크 低)
- 길이 분포 **8~60자** (현재 20~30자 고정), 가끔 단어 1개 ("좋네요", "이쁘다")
- 이모지 사용 **100%→60%**
- 표현 변주: 같은 계정 페르소나 안에서 짧게/길게/질문형/감탄형 랜덤
- ⚠️ **GPT가 제안했지만 거부한 항목**: 댓글마다 페르소나 변경. 한 계정 어조 변동은 더 강한 봇 시그널이라 적용 X

### 🟢 Bucket 5 — 시간·리듬 (영향도 中, 리스크 低)
- `between_requests` 분포 변경: `uniform(2, 5)` → `gauss(8, 3) + 15% long-tail(20~180s)`
- `maybe_idle` 확률 10%→30%, 범위 30초~3분으로 확대
- 시간대 윈도우: 01~08시 자동 중단
- 10~20% 확률 decoy 동작 (네이버 메인/내 블로그/이웃새글 들르기)

### 🔵 Bucket 0 — 관측 가능성 (옵션, 디버깅용)
- `~/.naver_automation/logs/{user_id}-YYYYMMDD.log`에 액션 타임라인 저장
- 잠금 발생 시 직전 N분간 액션 패턴 후행 분석 가능
- Bucket 2 효과가 모호할 때 우선 도입 권장

---

## 다음 단계 분기 로직 (사용자 합의)

Bucket 2 적용 후 며칠~1주일 운영 → 잠금 빈도 변화에 따라:

| 관찰 결과 | 다음 진행 |
|---|---|
| 잠금 **눈에 띄게 감소** | 행동 볼륨이 주요 원인이었음. **Bucket 4(저리스크)** 가볍게 보강하고 종료 |
| 잠금 **유지/소폭** | 기술 시그널이 진짜 원인. **Bucket 3 (trusted event)** 진행 |
| 잠금 **변화 없음 / 진단 모호** | **Bucket 0 (로깅)** 먼저 도입해 패턴 확보 후 결정 |

---

## 의사결정 원칙 (대화에서 합의된 룰)

1. **Incremental 적용**. 한 번에 다 고치지 않음. Bucket 단위로 며칠 관찰 → 다음. 한 번에 묶으면 어느 게 효과 있었는지 진단 불가.
2. **Push는 사용자 수동**. Claude는 commit까지만. 작업 끝마다 사용자 확인 대기.
3. **테스트는 별도 PC에서**. 로컬에서는 정적 검증만 수행:
   - `./venv/bin/python -m py_compile <files>` 통과 필수
   - 격리된 user_id로 daily counter / should_engage 단위 테스트
   - dead reference grep (`current_total`, `comment_count >=` 등)
4. **회귀 위험 최소화**. 사용자 명시 요청: "기능 개선보다 오동작·오류 방지가 더 중요". 코드 변경 후 항상 신중하게 정적 검증.

---

## 환경 정보
- 플랫폼: macOS (Darwin)
- Python: 3.13 (venv at `./venv/`)
- 패키지: pip (`requirements.txt`)
- 실행: `./run.sh` 또는 `./venv/bin/python main.py`
- UI: customtkinter
- 의존성 핵심: `playwright`, `playwright-stealth`, `google-genai`

## 파일 구조 (변경 후 기준)
| 파일 | 역할 |
|---|---|
| `base_bot.py` | 공통 브라우저/로그인. UA 영속화 + 팝업 stealth (Bucket 1) |
| `utils.py` | HumanDelay, 일일 카운터, `should_engage` (Bucket 2) |
| `neighbor_request.py` | Tab 1 — 서로이웃 신청 |
| `buddy_comment.py` | Tab 2 — 서로이웃 댓글 (전환율 랜덤화 Bucket 2) |
| `reply_bot.py` | Tab 3 — 대댓글 (dry_run 모드 보호) |
| `blog_actions.py` | 댓글/공감 등 공용 페이지 조작 |
| `comment_ai.py` | Gemini AI 댓글 생성 |
| `main.py` | customtkinter UI |

## 사용자 프로필별 영속 데이터
경로: `~/.naver_automation/profiles/{user_id}/`
- `ua.txt` — Bucket 1, 고정 UA 문자열
- `daily_actions.json` — Bucket 2, `{"date": "YYYY-MM-DD", "count": N}`
- 기타 Playwright persistent context 파일 (쿠키, localStorage 등)

수동 리셋이 필요한 경우 (예: 카운터 잘못 증가, UA 변경 원할 때):
```bash
rm ~/.naver_automation/profiles/<user_id>/daily_actions.json
rm ~/.naver_automation/profiles/<user_id>/ua.txt
```

---

## 새 PC 작업 재개 절차

1. repo clone + 브랜치 체크아웃
   ```bash
   git clone <repo-url> ~/Works/neighbor/naver_automation
   cd ~/Works/neighbor/naver_automation
   git fetch origin
   git checkout feat/anti-bot-detection-hardening   # push된 후
   ```
2. venv 재설정
   ```bash
   ./install.sh   # 또는
   python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
   ```
3. Claude Code 새 대화 시작 후 첫 메시지:
   > HANDOFF.md를 읽고 진행 상황을 파악한 다음, 다음 단계 논의하자.
4. 사용자가 잠금 빈도 변화 보고
5. 위 "다음 단계 분기 로직"에 따라 진행
