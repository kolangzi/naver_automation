#!/bin/bash

echo "=========================================="
echo "  네이버 서로이웃 자동 신청 도구 설치"
echo "=========================================="
echo ""

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 스크립트 위치로 이동
cd "$(dirname "$0")"

# 1. Python 버전 확인
echo -e "${YELLOW}[1/4] Python 확인 중...${NC}"
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    echo -e "${GREEN}✓ Python $PYTHON_VERSION 발견${NC}"
else
    echo -e "${RED}✗ Python3가 설치되어 있지 않습니다.${NC}"
    echo ""
    echo "Python 설치 방법:"
    echo "  1. https://www.python.org/downloads/ 에서 다운로드"
    echo "  2. 또는 Homebrew로 설치: brew install python3"
    exit 1
fi

# 2. 가상환경 생성
echo ""
echo -e "${YELLOW}[2/4] 가상환경 설정 중...${NC}"
if [ -d "venv" ]; then
    echo -e "${GREEN}✓ 기존 가상환경 발견${NC}"
else
    python3 -m venv venv
    echo -e "${GREEN}✓ 가상환경 생성 완료${NC}"
fi

# 가상환경 활성화
source venv/bin/activate

# 3. 의존성 설치
echo ""
echo -e "${YELLOW}[3/4] 필요한 패키지 설치 중...${NC}"
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo -e "${GREEN}✓ 패키지 설치 완료${NC}"

# 4. Playwright 브라우저 설치
echo ""
echo -e "${YELLOW}[4/4] Chromium 브라우저 설치 중... (시간이 걸릴 수 있습니다)${NC}"
playwright install chromium
echo -e "${GREEN}✓ 브라우저 설치 완료${NC}"

# 완료
echo ""
echo "=========================================="
echo -e "${GREEN}  설치가 완료되었습니다!${NC}"
echo "=========================================="
echo ""
echo "실행 방법:"
echo -e "  ${YELLOW}./run.sh${NC}"
echo ""
echo "또는 수동 실행:"
echo "  source venv/bin/activate"
echo "  python main.py"
echo ""
