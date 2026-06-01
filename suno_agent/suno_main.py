"""
Suno 음악 자동 생성 에이전트
==============================
메인 진입점. 대화형 CLI로 실행합니다.

사용법:
  python suno_main.py                      # 대화형 모드
  python suno_main.py --quick              # 이전 설정으로 즉시 실행
  python suno_main.py --method api         # API 방식 강제
  python suno_main.py --method browser     # 브라우저 방식 강제

흐름:
  1. 장르/무드/구성/곡 수 입력
  2. Claude API + 템플릿으로 Suno 프롬프트 N개 생성
  3. gcui-art/suno-api (API 방식) 또는 Playwright (브라우저 방식)로 제출
  4. 결과 요약 및 로그 저장
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

# ─────────────────────────────────────────────────────────
#  Config & 의존성 확인
# ─────────────────────────────────────────────────────────

def check_and_setup():
    """의존성 확인 및 .env 파일 안내"""
    missing = []
    for pkg in ["anthropic", "requests", "dotenv"]:
        try:
            __import__(pkg.replace("-", "_"))
        except ImportError:
            missing.append(pkg)

    if missing:
        print("❌ 아래 패키지가 필요합니다. 설치 후 다시 실행하세요:")
        print(f"   pip install {' '.join(missing)}")
        sys.exit(1)

    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        example = Path(__file__).parent / ".env.example"
        print("⚠️  .env 파일이 없습니다.")
        if example.exists():
            print(f"   .env.example을 복사하여 .env를 만들고 API 키를 입력하세요:")
            print(f"   copy .env.example .env")
        print()


# ─────────────────────────────────────────────────────────
#  대화형 입력
# ─────────────────────────────────────────────────────────

GENRE_LIST = [
    "K-Pop", "Lo-fi Hip Hop", "EDM", "R&B", "Pop",
    "Jazz", "Cinematic", "Trap", "Rock", "Folk",
    "Classical", "Reggae", "Latin", "Metal", "Ambient"
]

MOOD_LIST = [
    "upbeat / energetic", "melancholic / emotional", "dark / intense",
    "romantic / sensual", "peaceful / relaxing", "mysterious / atmospheric",
    "empowering / anthemic", "nostalgic / dreamy", "aggressive / hype",
    "epic / cinematic"
]

STRUCTURE_LIST = [
    "verse-chorus-bridge (일반적)",
    "verse-chorus (단순)",
    "instrumental (가사 없음, 연주곡)",
    "verse-prechorus-chorus-bridge (풀 팝 구조)",
    "A-B-A-B-C-B (재즈/팝 형식)",
]


def _prompt_choice(question: str, choices: list[str], allow_custom: bool = True) -> str:
    """번호 선택 프롬프트"""
    print(f"\n{question}")
    for i, c in enumerate(choices, 1):
        print(f"  {i:2d}. {c}")
    if allow_custom:
        print(f"   0. 직접 입력")

    while True:
        raw = input("\n  선택 (번호 또는 텍스트): ").strip()
        if raw.isdigit():
            idx = int(raw)
            if idx == 0 and allow_custom:
                return input("  직접 입력: ").strip()
            elif 1 <= idx <= len(choices):
                return choices[idx - 1]
        elif raw:
            return raw
        print("  ❌ 올바른 번호를 입력하세요")


def _prompt_int(question: str, default: int, min_val: int, max_val: int) -> int:
    """정수 입력 프롬프트"""
    while True:
        raw = input(f"\n{question} [{default}]: ").strip()
        if not raw:
            return default
        if raw.isdigit() and min_val <= int(raw) <= max_val:
            return int(raw)
        print(f"  ❌ {min_val}~{max_val} 사이의 숫자를 입력하세요")


def gather_user_input() -> dict:
    """사용자로부터 음악 생성 파라미터를 수집합니다."""
    print()
    print("━" * 55)
    print("  🎵 Suno 음악 생성 에이전트")
    print("━" * 55)
    print("  원하는 음악의 장르, 무드, 구성을 입력하면")
    print("  자동으로 Suno 프롬프트를 만들고 곡을 생성합니다.")
    print("━" * 55)

    genre = _prompt_choice("① 장르를 선택하세요:", GENRE_LIST)
    mood = _prompt_choice("② 무드/분위기를 선택하세요:", MOOD_LIST)
    structure = _prompt_choice("③ 곡 구성을 선택하세요:", STRUCTURE_LIST)

    print("\n④ 추가 지시사항 (없으면 Enter):")
    print("   예: '한국어 가사', 'BPM 130 이상', '여성 보컬만', '광고음악 스타일'")
    extra = input("   입력: ").strip()

    count = _prompt_int(
        "⑤ 생성할 곡 수를 입력하세요 (1~30):",
        default=10, min_val=1, max_val=30
    )

    print("\n⑥ 프롬프트 생성 방식:")
    gen_mode = _prompt_choice("", [
        "both  — Claude API + 템플릿 혼합 (권장)",
        "claude — Claude API만 (창의적, API 키 필요)",
        "template — 템플릿만 (빠름, API 키 불필요)",
    ], allow_custom=False)
    gen_mode = gen_mode.split()[0]  # "both", "claude", "template"

    print("\n⑦ Suno 제출 방식:")
    submit_mode = _prompt_choice("", [
        "api     — gcui-art/suno-api 서버 (빠름, 서버 설정 필요)",
        "browser — Playwright 브라우저 자동화 (서버 불필요)",
        "both    — API 시도, 실패 시 브라우저 폴백",
    ], allow_custom=False)
    submit_mode = submit_mode.split()[0]

    return {
        "genre": genre,
        "mood": mood,
        "structure": structure,
        "extra_instructions": extra,
        "count": count,
        "gen_mode": gen_mode,
        "submit_mode": submit_mode,
    }


# ─────────────────────────────────────────────────────────
#  프롬프트 미리보기 & 확인
# ─────────────────────────────────────────────────────────

def preview_and_confirm(prompts) -> bool:
    """생성된 프롬프트를 미리보고 확인합니다."""
    print(f"\n{'━'*55}")
    print(f"  📋 생성된 Suno 프롬프트 미리보기 ({len(prompts)}개)")
    print(f"{'━'*55}\n")

    for i, p in enumerate(prompts):
        print(f"  ── [{i+1:2d}] ──────────────────────────")
        print(f"  🎵 제목: {p.title}")
        print(f"  🏷️  태그: {p.style_tags[:80]}{'...' if len(p.style_tags)>80 else ''}")
        print(f"  🎤 연주곡: {'예' if p.make_instrumental else '아니오'}")
        print(f"  📌 출처: {p.source}")
        first_lines = p.prompt.strip().split('\n')[:4]
        print("  📝 프롬프트 앞부분:")
        for line in first_lines:
            print(f"     {line}")
        print()

    while True:
        ans = input("Suno에 제출하시겠습니까? (y/n/edit): ").strip().lower()
        if ans in ("y", "yes", "예"):
            return True
        elif ans in ("n", "no", "아니오"):
            print("취소되었습니다.")
            return False
        elif ans == "edit":
            # 간단한 편집: 특정 프롬프트 제거
            remove = input("제거할 번호 (쉼표 구분, Enter=건너뜀): ").strip()
            if remove:
                to_remove = {int(x.strip())-1 for x in remove.split(",") if x.strip().isdigit()}
                prompts[:] = [p for i, p in enumerate(prompts) if i not in to_remove]
                print(f"  {len(prompts)}개 프롬프트 남음")
            return True
        else:
            print("  y(예) / n(아니오) / edit(편집) 중 선택하세요")


# ─────────────────────────────────────────────────────────
#  제출 실행
# ─────────────────────────────────────────────────────────

def submit_prompts(prompts, submit_mode: str) -> None:
    """프롬프트를 선택된 방식으로 Suno에 제출합니다."""

    if submit_mode in ("api", "both"):
        print("\n🚀 [방식 1] gcui-art/suno-api 서버로 제출 시도...")
        try:
            from suno_api_client import run_api_batch
            run_api_batch(prompts)
            return
        except ConnectionError as e:
            if submit_mode == "api":
                print(f"\n❌ API 서버 연결 실패:\n   {e}")
                return
            else:
                print(f"\n  ⚠️  API 실패 → 브라우저 폴백으로 전환\n  {e}")

    if submit_mode in ("browser", "both"):
        print("\n🌐 [방식 2] Playwright 브라우저 자동화로 제출...")
        print("  ℹ️  브라우저가 열립니다. Suno에 로그인되어 있어야 합니다.")
        print("  ℹ️  처음 실행 시 로그인이 필요할 수 있습니다.\n")

        headless_input = input("  백그라운드 실행? (y=백그라운드 / n=화면 표시, 권장): ").strip().lower()
        headless = headless_input in ("y", "yes")

        from suno_browser import run_browser_batch
        results = run_browser_batch(prompts, headless=headless)

        success = sum(1 for r in results if r.success)
        print(f"\n  브라우저 완료: {success}/{len(results)}개 성공")


# ─────────────────────────────────────────────────────────
#  세션 저장/로드 (--quick 모드용)
# ─────────────────────────────────────────────────────────

SESSION_FILE = Path(__file__).parent / "output" / "last_session.json"


def save_session(params: dict) -> None:
    SESSION_FILE.parent.mkdir(exist_ok=True)
    with open(SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump(params, f, ensure_ascii=False, indent=2)


def load_session() -> dict | None:
    if SESSION_FILE.exists():
        with open(SESSION_FILE, encoding="utf-8") as f:
            return json.load(f)
    return None


# ─────────────────────────────────────────────────────────
#  메인
# ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Suno 음악 자동 생성 에이전트")
    parser.add_argument("--quick", action="store_true", help="이전 설정으로 즉시 실행")
    parser.add_argument("--method", choices=["api", "browser", "both"], help="제출 방식 강제 선택")
    parser.add_argument("--count", type=int, help="생성 곡 수 오버라이드")
    args = parser.parse_args()

    check_and_setup()

    # ── 파라미터 수집 ────────────────────────────────────
    if args.quick:
        params = load_session()
        if not params:
            print("⚠️  저장된 세션이 없습니다. 대화형 모드로 시작합니다.")
            params = gather_user_input()
        else:
            print(f"  ✅ 이전 세션 로드: {params['genre']} / {params['mood']} / {params['count']}곡")
    else:
        params = gather_user_input()

    if args.method:
        params["submit_mode"] = args.method
    if args.count:
        params["count"] = min(args.count, 30)

    save_session(params)

    print(f"\n{'━'*55}")
    print(f"  설정 요약")
    print(f"{'━'*55}")
    print(f"  장르:     {params['genre']}")
    print(f"  무드:     {params['mood']}")
    print(f"  구성:     {params['structure']}")
    print(f"  곡 수:    {params['count']}개")
    print(f"  생성방식: {params['gen_mode']}")
    print(f"  제출방식: {params['submit_mode']}")
    if params.get('extra_instructions'):
        print(f"  추가:     {params['extra_instructions']}")
    print(f"{'━'*55}\n")

    # ── 프롬프트 생성 ─────────────────────────────────────
    print("🎼 Suno 프롬프트 생성 중...\n")
    from config import ANTHROPIC_API_KEY
    from prompt_generator import generate_prompts

    prompts = generate_prompts(
        genre=params["genre"],
        mood=params["mood"],
        structure=params["structure"],
        count=params["count"],
        mode=params["gen_mode"],
        extra_instructions=params.get("extra_instructions", ""),
        api_key=ANTHROPIC_API_KEY,
    )

    if not prompts:
        print("❌ 프롬프트 생성 실패")
        sys.exit(1)

    # 프롬프트를 JSON으로 저장
    from config import OUTPUT_DIR
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    prompts_file = OUTPUT_DIR / f"prompts_{ts}.json"
    with open(prompts_file, "w", encoding="utf-8") as f:
        json.dump([p.to_dict() for p in prompts], f, ensure_ascii=False, indent=2)
    print(f"  💾 프롬프트 저장: {prompts_file}\n")

    # ── 미리보기 및 확인 ──────────────────────────────────
    if not preview_and_confirm(prompts):
        sys.exit(0)

    # ── Suno 제출 ─────────────────────────────────────────
    submit_prompts(prompts, params["submit_mode"])

    print(f"\n{'━'*55}")
    print(f"  🎉 완료! 로그 파일: output/generation_log.jsonl")
    print(f"  📂 프롬프트 파일: {prompts_file}")
    print(f"{'━'*55}\n")


if __name__ == "__main__":
    main()
