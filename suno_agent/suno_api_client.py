"""
Suno API 클라이언트 (gcui-art/suno-api)
==========================================
gcui-art/suno-api 로컬 서버를 통해 Suno에 곡 생성을 요청합니다.

사전 설정:
  1. git clone https://github.com/gcui-art/suno-api
  2. .env 파일에 SUNO_COOKIE, TWOCAPTCHA_KEY 설정
  3. npm install && npm run dev  →  http://localhost:3000

API 흐름:
  POST /api/custom_generate  →  [{id, status, ...}, ...]
  GET  /api/get?ids=id1,id2  →  [{status, audio_url, ...}, ...]
"""

import time
import json
import requests
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from config import SUNO_API_BASE_URL, POLL_INTERVAL_SECONDS, MAX_POLL_ATTEMPTS, LOG_FILE
from prompt_generator import SunoPrompt


# ─────────────────────────────────────────────────────────
#  결과 데이터 클래스
# ─────────────────────────────────────────────────────────

@dataclass
class SunoResult:
    """단일 곡 생성 결과"""
    song_id: str
    title: str
    status: str                  # "pending" | "queued" | "streaming" | "complete" | "error"
    audio_url: Optional[str] = None
    video_url: Optional[str] = None
    image_url: Optional[str] = None
    duration: Optional[float] = None
    style_tags: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    prompt_source: str = ""
    error: Optional[str] = None

    @property
    def is_done(self) -> bool:
        return self.status in ("streaming", "complete")

    @property
    def is_error(self) -> bool:
        return self.status == "error" or self.error is not None

    def to_dict(self) -> dict:
        return {
            "song_id": self.song_id,
            "title": self.title,
            "status": self.status,
            "audio_url": self.audio_url,
            "video_url": self.video_url,
            "image_url": self.image_url,
            "duration": self.duration,
            "style_tags": self.style_tags,
            "created_at": self.created_at,
            "prompt_source": self.prompt_source,
            "error": self.error,
        }


# ─────────────────────────────────────────────────────────
#  API 클라이언트
# ─────────────────────────────────────────────────────────

class SunoAPIClient:
    """gcui-art/suno-api HTTP 클라이언트"""

    def __init__(self, base_url: str = ""):
        self.base_url = (base_url or SUNO_API_BASE_URL).rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    def _post(self, endpoint: str, payload: dict) -> dict | list:
        url = f"{self.base_url}{endpoint}"
        resp = self.session.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _get(self, endpoint: str, params: dict = None) -> dict | list:
        url = f"{self.base_url}{endpoint}"
        resp = self.session.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def check_server(self) -> dict:
        """서버 상태 및 크레딧 확인"""
        try:
            result = self._get("/api/get_limit")
            return result
        except requests.ConnectionError:
            raise ConnectionError(
                f"suno-api 서버에 연결할 수 없습니다: {self.base_url}\n"
                "  → 서버가 실행 중인지 확인하세요: npm run dev"
            )

    def generate_song(self, prompt: SunoPrompt) -> list[SunoResult]:
        """
        단일 프롬프트로 곡 생성 요청.
        Suno는 한 번에 2개 버전을 생성합니다.
        """
        payload = {
            "prompt": prompt.prompt,
            "tags": prompt.style_tags,
            "title": prompt.title,
            "make_instrumental": prompt.make_instrumental,
            "wait_audio": False,
        }

        try:
            data = self._post("/api/custom_generate", payload)
        except requests.HTTPError as e:
            return [SunoResult(
                song_id="error",
                title=prompt.title,
                status="error",
                error=str(e),
                style_tags=prompt.style_tags,
                prompt_source=prompt.source,
            )]

        results = []
        for item in data:
            results.append(SunoResult(
                song_id=item.get("id", "unknown"),
                title=item.get("title", prompt.title),
                status=item.get("status", "pending"),
                audio_url=item.get("audio_url"),
                video_url=item.get("video_url"),
                image_url=item.get("image_url"),
                style_tags=prompt.style_tags,
                prompt_source=prompt.source,
            ))
        return results

    def get_status(self, song_ids: list[str]) -> dict[str, SunoResult]:
        """여러 곡의 상태를 한번에 조회합니다."""
        ids_str = ",".join(song_ids)
        data = self._get("/api/get", params={"ids": ids_str})

        results = {}
        for item in data:
            sid = item.get("id", "")
            results[sid] = SunoResult(
                song_id=sid,
                title=item.get("title", ""),
                status=item.get("status", "pending"),
                audio_url=item.get("audio_url"),
                video_url=item.get("video_url"),
                image_url=item.get("image_url"),
                duration=item.get("duration"),
            )
        return results


# ─────────────────────────────────────────────────────────
#  배치 생성 오케스트레이터
# ─────────────────────────────────────────────────────────

class SunoAPIBatch:
    """여러 프롬프트를 순차 제출하고 모두 완료될 때까지 폴링"""

    def __init__(self, client: SunoAPIClient):
        self.client = client
        self.all_results: dict[str, SunoResult] = {}  # song_id → result
        self.prompt_map: dict[str, SunoPrompt] = {}    # song_id → original prompt

    def submit_all(
        self,
        prompts: list[SunoPrompt],
        delay_between: float = 3.0,
    ) -> None:
        """프롬프트 목록을 순차 제출합니다."""
        print(f"\n📤 총 {len(prompts)}개 프롬프트 Suno에 제출 중...\n")

        for i, prompt in enumerate(prompts):
            print(f"  [{i+1:2d}/{len(prompts)}] 제출: {prompt.title}")
            results = self.client.generate_song(prompt)

            for r in results:
                self.all_results[r.song_id] = r
                self.prompt_map[r.song_id] = prompt
                status_icon = "✅" if not r.is_error else "❌"
                print(f"         {status_icon} ID: {r.song_id[:8]}... | 상태: {r.status}")

            if i < len(prompts) - 1:
                time.sleep(delay_between)

        print(f"\n  총 {len(self.all_results)}개 트랙 제출 완료 (각 프롬프트당 2곡 생성)\n")

    def poll_until_done(
        self,
        on_progress=None,
    ) -> list[SunoResult]:
        """모든 곡이 완료될 때까지 폴링합니다."""
        pending_ids = [
            sid for sid, r in self.all_results.items()
            if not r.is_done and not r.is_error
        ]

        if not pending_ids:
            return list(self.all_results.values())

        print(f"⏳ {len(pending_ids)}개 트랙 생성 대기 중 (최대 {MAX_POLL_ATTEMPTS * POLL_INTERVAL_SECONDS // 60}분)...\n")

        for attempt in range(MAX_POLL_ATTEMPTS):
            if not pending_ids:
                break

            time.sleep(POLL_INTERVAL_SECONDS)

            try:
                status_map = self.client.get_status(pending_ids)
            except Exception as e:
                print(f"  ⚠️  상태 조회 실패 (재시도): {e}")
                continue

            newly_done = []
            for sid, updated in status_map.items():
                self.all_results[sid].status = updated.status
                if updated.audio_url:
                    self.all_results[sid].audio_url = updated.audio_url
                if updated.video_url:
                    self.all_results[sid].video_url = updated.video_url
                if updated.image_url:
                    self.all_results[sid].image_url = updated.image_url
                if updated.duration:
                    self.all_results[sid].duration = updated.duration

                if updated.is_done or updated.is_error:
                    newly_done.append(sid)

            for sid in newly_done:
                pending_ids.remove(sid)
                r = self.all_results[sid]
                icon = "🎵" if r.is_done else "❌"
                print(f"  {icon} 완료: {r.title[:30]} | {r.audio_url or r.error or ''}")

            done_count = len(self.all_results) - len(pending_ids)
            total = len(self.all_results)
            elapsed = (attempt + 1) * POLL_INTERVAL_SECONDS
            print(f"  진행: {done_count}/{total} 완료 | 경과: {elapsed}초")

            if on_progress:
                on_progress(done_count, total)

        if pending_ids:
            print(f"\n  ⚠️  타임아웃: {len(pending_ids)}개 트랙 미완료")

        return list(self.all_results.values())

    def save_log(self) -> None:
        """결과를 JSONL 로그 파일에 저장합니다."""
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            for r in self.all_results.values():
                f.write(json.dumps(r.to_dict(), ensure_ascii=False) + "\n")
        print(f"\n📝 결과 저장: {LOG_FILE}")

    def print_summary(self) -> None:
        """최종 결과 요약 출력"""
        results = list(self.all_results.values())
        done = [r for r in results if r.is_done]
        errors = [r for r in results if r.is_error]
        pending = [r for r in results if not r.is_done and not r.is_error]

        print("\n" + "=" * 55)
        print(f"  📊 생성 결과 요약")
        print("=" * 55)
        print(f"  ✅ 완료: {len(done)}곡")
        print(f"  ❌ 오류: {len(errors)}곡")
        print(f"  ⏳ 미완료: {len(pending)}곡")
        print()

        if done:
            print("  완료된 곡 목록:")
            for i, r in enumerate(done):
                dur = f"{r.duration:.0f}초" if r.duration else "?"
                print(f"    {i+1:2d}. {r.title} [{dur}]")
                if r.audio_url:
                    print(f"        🔗 {r.audio_url}")
        print("=" * 55)


# ─────────────────────────────────────────────────────────
#  빠른 사용 함수
# ─────────────────────────────────────────────────────────

def run_api_batch(
    prompts: list[SunoPrompt],
    base_url: str = "",
) -> list[SunoResult]:
    """프롬프트 목록을 API로 제출하고 결과를 반환합니다."""
    client = SunoAPIClient(base_url)

    # 서버 확인
    print("🔍 suno-api 서버 확인 중...")
    quota = client.check_server()
    credits = quota.get("credits_left", "?")
    print(f"  크레딧 잔여: {credits}")
    print()

    batch = SunoAPIBatch(client)
    batch.submit_all(prompts)
    results = batch.poll_until_done()
    batch.print_summary()
    batch.save_log()

    return results
