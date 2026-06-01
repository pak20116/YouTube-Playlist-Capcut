"""
Suno 브라우저 자동화 (Playwright)
====================================
API 서버 없이 실제 브라우저로 suno.com/create를 조작하여
자동으로 곡을 생성합니다.

사용 조건:
- Chrome 또는 Chromium이 설치되어 있어야 합니다
- Suno 계정으로 로그인된 브라우저 세션 필요
- pip install playwright && playwright install chromium

작동 방식:
  1. suno.com/create 접속
  2. Custom Mode 활성화
  3. 스타일/제목/가사 필드 입력
  4. Create 버튼 클릭
  5. 다음 곡으로 반복

⚠️  주의: 브라우저 자동화는 Suno의 서비스 이용 약관에 따라
         계정이 제한될 수 있습니다. 적절한 딜레이를 사용하세요.
"""

import asyncio
import json
import time
import random
from datetime import datetime
from pathlib import Path
from typing import Optional

from prompt_generator import SunoPrompt
from config import LOG_FILE


# ─────────────────────────────────────────────────────────
#  브라우저 결과 클래스
# ─────────────────────────────────────────────────────────

class BrowserResult:
    def __init__(self, title: str, success: bool, song_url: str = "", error: str = ""):
        self.title = title
        self.success = success
        self.song_url = song_url
        self.error = error
        self.created_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "success": self.success,
            "song_url": self.song_url,
            "error": self.error,
            "created_at": self.created_at,
            "method": "browser",
        }


# ─────────────────────────────────────────────────────────
#  브라우저 자동화 클래스
# ─────────────────────────────────────────────────────────

class SunoBrowserAgent:
    """Playwright 기반 Suno 브라우저 자동화"""

    SUNO_CREATE_URL = "https://suno.com/create"

    def __init__(
        self,
        headless: bool = False,  # False = 브라우저 화면 표시 (디버깅 편의)
        delay_between_songs: float = 8.0,
        user_data_dir: str = "",
    ):
        self.headless = headless
        self.delay_between_songs = delay_between_songs
        # 기존 Chrome 프로필을 사용하면 이미 로그인된 상태로 시작 가능
        self.user_data_dir = user_data_dir or str(
            Path.home() / "AppData/Local/Google/Chrome/User Data"
        )

    async def _type_slowly(self, page, selector: str, text: str, delay: float = 0.05):
        """사람처럼 천천히 텍스트를 입력합니다."""
        await page.click(selector)
        await page.fill(selector, "")  # 기존 내용 지우기
        # 긴 텍스트는 fill로 한번에, 짧은 텍스트는 type으로
        if len(text) > 200:
            await page.fill(selector, text)
        else:
            for char in text:
                await page.type(selector, char, delay=int(delay * 1000))

    async def _wait_random(self, min_sec: float = 1.0, max_sec: float = 3.0):
        """랜덤 딜레이 (봇 감지 방지)"""
        await asyncio.sleep(random.uniform(min_sec, max_sec))

    async def create_one_song(self, page, prompt: SunoPrompt, index: int) -> BrowserResult:
        """단일 곡을 브라우저에서 생성합니다."""
        print(f"\n  [{index}] 브라우저 생성 시작: {prompt.title}")

        try:
            # ── 페이지 이동 ──────────────────────────────────
            await page.goto(self.SUNO_CREATE_URL, wait_until="networkidle", timeout=30000)
            await self._wait_random(2, 4)

            # ── Custom Mode 버튼 클릭 ───────────────────────
            # Suno UI에서 "Custom Mode" 토글 찾기
            custom_mode_selectors = [
                "button:has-text('Custom')",
                "[data-testid='custom-mode-toggle']",
                "button.custom-mode",
                "//button[contains(text(), 'Custom')]",
            ]
            custom_clicked = False
            for sel in custom_mode_selectors:
                try:
                    btn = page.locator(sel).first
                    if await btn.is_visible(timeout=3000):
                        await btn.click()
                        custom_clicked = True
                        print(f"     ✅ Custom Mode 활성화")
                        break
                except Exception:
                    continue

            if not custom_clicked:
                print("     ⚠️  Custom Mode 버튼을 찾지 못했습니다. 계속 진행...")

            await self._wait_random(1, 2)

            # ── 스타일 태그 입력 ────────────────────────────
            style_selectors = [
                "textarea[placeholder*='style']",
                "textarea[placeholder*='Style']",
                "input[placeholder*='style']",
                "[data-testid='style-input']",
                "textarea.style-input",
            ]
            style_filled = False
            for sel in style_selectors:
                try:
                    el = page.locator(sel).first
                    if await el.is_visible(timeout=3000):
                        await el.fill(prompt.style_tags[:120])  # Suno 태그 한도
                        style_filled = True
                        print(f"     ✅ 스타일 태그 입력: {prompt.style_tags[:60]}...")
                        break
                except Exception:
                    continue
            if not style_filled:
                print("     ⚠️  스타일 필드를 찾지 못했습니다")

            await self._wait_random(0.5, 1.5)

            # ── 제목 입력 ────────────────────────────────────
            title_selectors = [
                "input[placeholder*='title']",
                "input[placeholder*='Title']",
                "[data-testid='title-input']",
            ]
            for sel in title_selectors:
                try:
                    el = page.locator(sel).first
                    if await el.is_visible(timeout=3000):
                        await el.fill(prompt.title[:80])
                        print(f"     ✅ 제목 입력: {prompt.title}")
                        break
                except Exception:
                    continue

            await self._wait_random(0.5, 1.5)

            # ── 가사/프롬프트 입력 ───────────────────────────
            lyrics_selectors = [
                "textarea[placeholder*='lyrics']",
                "textarea[placeholder*='Lyrics']",
                "textarea[placeholder*='prompt']",
                "[data-testid='lyrics-input']",
                "textarea.lyrics-input",
            ]
            lyrics_filled = False
            for sel in lyrics_selectors:
                try:
                    el = page.locator(sel).first
                    if await el.is_visible(timeout=3000):
                        # 가사는 길어서 fill 사용
                        await el.fill(prompt.prompt[:3000])
                        lyrics_filled = True
                        print(f"     ✅ 가사 입력 완료 ({len(prompt.prompt)}자)")
                        break
                except Exception:
                    continue
            if not lyrics_filled:
                print("     ⚠️  가사 필드를 찾지 못했습니다")

            await self._wait_random(1, 2)

            # ── Instrumental 토글 ─────────────────────────
            if prompt.make_instrumental:
                instr_selectors = [
                    "button:has-text('Instrumental')",
                    "[data-testid='instrumental-toggle']",
                    "input[type='checkbox'][name*='instrumental']",
                ]
                for sel in instr_selectors:
                    try:
                        el = page.locator(sel).first
                        if await el.is_visible(timeout=2000):
                            await el.click()
                            print("     ✅ Instrumental 모드 활성화")
                            break
                    except Exception:
                        continue

            await self._wait_random(0.5, 1)

            # ── Create 버튼 클릭 ──────────────────────────
            create_selectors = [
                "button:has-text('Create')",
                "button[type='submit']",
                "[data-testid='create-button']",
                "button.create-btn",
            ]
            create_clicked = False
            for sel in create_selectors:
                try:
                    btn = page.locator(sel).first
                    if await btn.is_visible(timeout=3000):
                        await btn.click()
                        create_clicked = True
                        print("     ✅ Create 클릭!")
                        break
                except Exception:
                    continue

            if not create_clicked:
                return BrowserResult(
                    title=prompt.title,
                    success=False,
                    error="Create 버튼을 찾지 못했습니다",
                )

            # ── 생성 시작 확인 (로딩 감지) ────────────────
            await self._wait_random(3, 5)

            # 현재 URL에서 곡 ID 추출 시도
            current_url = page.url
            song_url = current_url if "suno.com" in current_url else self.SUNO_CREATE_URL

            print(f"     ✅ 생성 요청 완료 → {song_url}")
            return BrowserResult(title=prompt.title, success=True, song_url=song_url)

        except Exception as e:
            print(f"     ❌ 오류: {e}")
            return BrowserResult(title=prompt.title, success=False, error=str(e))

    async def run_batch_async(self, prompts: list[SunoPrompt]) -> list[BrowserResult]:
        """모든 프롬프트를 브라우저에서 순차 실행합니다."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise RuntimeError(
                "playwright가 필요합니다:\n"
                "  pip install playwright\n"
                "  playwright install chromium"
            )

        results = []

        async with async_playwright() as pw:
            # 기존 Chrome 프로필 사용 (로그인 세션 유지)
            # launch_persistent_context 사용 시 이미 로그인된 상태
            try:
                context = await pw.chromium.launch_persistent_context(
                    user_data_dir=self.user_data_dir,
                    headless=self.headless,
                    args=[
                        "--no-sandbox",
                        "--disable-blink-features=AutomationControlled",
                    ],
                    ignore_https_errors=True,
                )
                print("  📂 기존 Chrome 프로필 사용 (로그인 세션 유지)")
            except Exception as e:
                print(f"  ⚠️  기존 프로필 사용 실패 ({e}), 새 브라우저로 시작합니다")
                browser = await pw.chromium.launch(headless=self.headless)
                context = await browser.new_context()

            page = await context.new_page()

            # 봇 감지 우회
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
            """)

            print(f"\n🌐 브라우저 자동화 시작: {len(prompts)}개 곡 생성")
            print("  (headless=False 이므로 브라우저 창이 열립니다)\n")

            for i, prompt in enumerate(prompts):
                result = await self.create_one_song(page, prompt, i + 1)
                results.append(result)

                # 로그 저장
                with open(LOG_FILE, "a", encoding="utf-8") as f:
                    f.write(json.dumps(result.to_dict(), ensure_ascii=False) + "\n")

                # 다음 곡 사이 딜레이
                if i < len(prompts) - 1:
                    delay = self.delay_between_songs + random.uniform(-2, 3)
                    print(f"  ⏱️  다음 곡까지 {delay:.1f}초 대기...")
                    await asyncio.sleep(delay)

            await context.close()

        return results

    def run_batch(self, prompts: list[SunoPrompt]) -> list[BrowserResult]:
        """동기 래퍼 — asyncio.run() 호출"""
        return asyncio.run(self.run_batch_async(prompts))


# ─────────────────────────────────────────────────────────
#  빠른 사용 함수
# ─────────────────────────────────────────────────────────

def run_browser_batch(
    prompts: list[SunoPrompt],
    headless: bool = False,
    user_data_dir: str = "",
) -> list[BrowserResult]:
    """
    브라우저 자동화로 Suno에 곡 생성 요청을 제출합니다.

    headless=False: 브라우저 화면 표시 (권장 — 로그인 확인 가능)
    headless=True:  백그라운드 실행
    """
    agent = SunoBrowserAgent(
        headless=headless,
        user_data_dir=user_data_dir,
    )
    results = agent.run_batch(prompts)

    # 요약
    success = sum(1 for r in results if r.success)
    print(f"\n📊 브라우저 자동화 완료: {success}/{len(results)}개 성공")
    return results
