# 🎵 Suno 음악 자동 생성 에이전트

장르, 무드, 곡 구성을 입력하면 → Suno 프롬프트 자동 생성 → Suno에 자동 제출 → 10~30곡 일괄 생성

---

## 시스템 구조

```
사용자 입력 (장르/무드/구성)
        ↓
[prompt_generator.py]
  ├── Claude API → 창의적 프롬프트 N/2개 생성
  └── 템플릿 엔진 → 빠른 변형 N/2개 생성
        ↓
  프롬프트 미리보기 & 확인
        ↓
[제출 방식 선택]
  ├── API 방식: suno_api_client.py → gcui-art/suno-api → Suno
  └── 브라우저: suno_browser.py   → Playwright → suno.com/create
        ↓
  결과 저장 (output/generation_log.jsonl)
```

---

## 빠른 시작

### 1단계: 패키지 설치

```bash
cd suno_agent
pip install -r requirements.txt
playwright install chromium   # 브라우저 자동화 사용 시
```

### 2단계: .env 파일 설정

```bash
copy .env.example .env   # Windows
# 또는
cp .env.example .env     # Mac/Linux
```

`.env` 파일을 열어서 설정:

```env
# 필수: Claude API 키 (프롬프트 자동 생성용)
ANTHROPIC_API_KEY=sk-ant-api03-...

# API 방식 사용 시: gcui-art/suno-api 서버 URL
SUNO_API_BASE_URL=http://localhost:3000

# Suno 쿠키 (API 방식 또는 브라우저 방식 모두에서 필요)
SUNO_COOKIE=__client=...
```

### 3단계 (API 방식): gcui-art/suno-api 서버 설정

```bash
git clone https://github.com/gcui-art/suno-api
cd suno-api
npm install

# .env 파일에 SUNO_COOKIE, TWOCAPTCHA_KEY 설정 후:
npm run dev   # → http://localhost:3000 에서 실행
```

### 4단계: 에이전트 실행

```bash
python suno_main.py
```

---

## 실행 옵션

```bash
# 대화형 모드 (기본)
python suno_main.py

# 이전 설정으로 즉시 재실행
python suno_main.py --quick

# 제출 방식 강제 선택
python suno_main.py --method api
python suno_main.py --method browser
python suno_main.py --method both

# 곡 수 지정
python suno_main.py --count 20
```

---

## 파일 구조

```
suno_agent/
├── suno_main.py           ← 메인 실행 파일 (여기서 시작)
├── prompt_generator.py    ← Claude API + 템플릿 프롬프트 생성
├── suno_api_client.py     ← gcui-art/suno-api HTTP 클라이언트
├── suno_browser.py        ← Playwright 브라우저 자동화
├── config.py              ← 설정 (환경변수 로딩)
├── music_templates.json   ← 장르/무드 템플릿 데이터베이스
├── requirements.txt
├── .env.example           ← 환경변수 템플릿
├── .env                   ← 실제 API 키 (생성 필요, git 제외)
└── output/
    ├── prompts_YYYYMMDD_HHMMSS.json  ← 생성된 프롬프트 저장
    ├── generation_log.jsonl           ← 생성 결과 로그
    └── last_session.json             ← 마지막 세션 설정
```

---

## Suno 쿠키 가져오는 방법

1. [suno.com/create](https://suno.com/create) 접속 (로그인)
2. `F12` → **Network** 탭
3. 페이지 새로고침
4. `?__clerk_api_version` 포함된 요청 클릭
5. **Headers** 탭 → **Cookie** 값 복사
6. `.env` 파일의 `SUNO_COOKIE=` 뒤에 붙여넣기

---

## 지원 장르

K-Pop, Lo-fi Hip Hop, EDM, R&B, Pop, Jazz, Cinematic, Trap, Rock, Folk, Classical, Reggae, Latin, Metal, Ambient

(직접 입력도 가능)

---

## 주의사항

- Suno 무료 플랜은 하루 10곡 한도 (Pro는 500곡/월)
- 브라우저 자동화 과다 사용 시 계정 제한 가능성 있음
- 생성된 프롬프트는 `output/prompts_*.json`에 저장되어 재사용 가능
- `gcui-art/suno-api`는 비공식 프로젝트 (학습/연구 목적)

---

*Built with Claude API (prompt generation) + gcui-art/suno-api + Playwright*
