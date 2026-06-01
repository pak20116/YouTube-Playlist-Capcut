"""
Suno Agent 설정
================
.env 파일에서 환경변수를 로드합니다.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# .env 파일 로드 (suno_agent 폴더 기준)
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

# ─────────────────────────────────────────────
#  API 키
# ─────────────────────────────────────────────

# Claude API 키 (프롬프트 자동 생성용)
# https://console.anthropic.com 에서 발급
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# gcui-art/suno-api 로컬 서버 URL
# npm run dev 로 실행 후 http://localhost:3000
SUNO_API_BASE_URL = os.getenv("SUNO_API_BASE_URL", "http://localhost:3000")

# Suno 계정 쿠키 (브라우저 자동화 폴백용)
# suno.com 에서 개발자 도구 > Network > Cookie 값
SUNO_COOKIE = os.getenv("SUNO_COOKIE", "")

# ─────────────────────────────────────────────
#  생성 설정
# ─────────────────────────────────────────────

# 기본 생성 곡 수
DEFAULT_SONG_COUNT = 10

# 최대 생성 곡 수 (Suno 플랜 한도 고려)
MAX_SONG_COUNT = 30

# API 폴링 간격 (초)
POLL_INTERVAL_SECONDS = 10

# 최대 폴링 시도 횟수 (= 최대 대기 시간 / POLL_INTERVAL)
MAX_POLL_ATTEMPTS = 72  # 12분

# 생성 결과 저장 폴더
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# 로그 파일
LOG_FILE = OUTPUT_DIR / "generation_log.jsonl"
