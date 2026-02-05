#!/bin/bash

cd "$(dirname "$0")"

if [ ! -d "venv" ]; then
    echo "먼저 install.sh를 실행해주세요!"
    echo "  ./install.sh"
    exit 1
fi

source venv/bin/activate
python main.py
