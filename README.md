# 네이버 서로이웃 자동 신청 도구

네이버 블로그 공감 계정 중 이웃추가 가능한 계정에 자동으로 서로이웃 신청하는 GUI 도구

## 요구사항

- macOS 10.15 (Catalina) 이상
- Python 3.8 이상
- 인터넷 연결

## 설치 및 실행

```bash
# 1. 설치 (최초 1회)
./install.sh

# 2. 실행
./run.sh
```

### 수동 설치 (install.sh가 안 될 경우)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
python main.py
```

## 사용법

1. 블로그 URL: 공감 계정을 추출할 네이버 블로그 글 주소 입력
   - 예: `https://blog.naver.com/username/123456789`
2. 네이버 ID: 로그인할 네이버 아이디 입력
3. 비밀번호: 비밀번호 입력 (화면에 *** 표시)
4. [시작] 버튼 클릭

## 동작 방식

1. 네이버 로그인 (캡차 발생 시 30초 내 수동 로그인)
2. 블로그 글의 공감 히스토리 페이지 접속
3. 이웃추가 가능한 계정 추출
4. 각 계정에 서로이웃 신청 (자동 메시지 포함)

## 주의사항

- 네이버 이용약관을 준수하여 사용하세요
- 과도한 사용 시 계정 제재가 있을 수 있습니다
- 캡차 발생 시 30초 내 수동 처리가 필요합니다
- 사람처럼 보이도록 랜덤 딜레이가 포함되어 있습니다
