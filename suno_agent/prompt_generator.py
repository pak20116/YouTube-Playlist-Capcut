"""
Suno 프롬프트 생성기
====================
두 가지 방식으로 Suno 최적화 프롬프트를 생성합니다:

1. Claude API 방식 (창의적 생성)
   - 장르/무드/구성 입력 → Claude가 다양한 Suno 프롬프트 N개 생성
   - 각 프롬프트마다 제목, 스타일 태그, 가사 구조 포함

2. 템플릿 방식 (빠른 변형 생성)
   - music_templates.json 기반
   - 변수 조합으로 대량의 변형 버전 생성
"""

import json
import random
import re
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict

# ─────────────────────────────────────────────────────────
#  데이터 클래스
# ─────────────────────────────────────────────────────────

@dataclass
class SunoPrompt:
    """Suno 생성 요청 단위"""
    title: str               # 곡 제목
    style_tags: str          # 스타일/장르 태그 (쉼표 구분)
    prompt: str              # 메인 프롬프트 (가사 또는 설명)
    make_instrumental: bool  # True = 가사 없음 (연주곡)
    source: str              # "claude" 또는 "template"
    metadata: dict           # 생성 메타데이터 (장르, 무드 등)

    def to_dict(self) -> dict:
        return asdict(self)

    def preview(self) -> str:
        lines = [
            f"🎵 제목: {self.title}",
            f"🏷️  태그: {self.style_tags}",
            f"🎤 연주곡: {'예' if self.make_instrumental else '아니오'}",
            f"📝 프롬프트 (앞 120자): {self.prompt[:120]}...",
            f"📌 출처: {self.source}",
        ]
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────
#  1. Claude API 기반 생성기
# ─────────────────────────────────────────────────────────

CLAUDE_SYSTEM_PROMPT = """
당신은 Suno AI 음악 생성 플랫폼 전문가입니다.
사용자가 원하는 음악의 장르, 무드, 구성을 설명하면,
Suno에서 최적의 결과를 내는 프롬프트를 생성해야 합니다.

Suno 프롬프트 작성 규칙:
- style_tags: 장르, 악기, 보컬 스타일, 무드를 영어 쉼표 구분 태그로 (예: "k-pop, upbeat, female vocal, synth, bright")
- prompt: 가사 구조를 [Verse], [Chorus], [Bridge], [Pre-Chorus], [Outro] 섹션으로 나누어 실제 가사 작성
           (연주곡이면 [Intro], [Build], [Drop], [Outro] 같은 악기 방향 설명)
- title: 곡 분위기를 반영한 영어 또는 한국어 제목
- make_instrumental: 가사 없는 연주곡이면 true

반드시 다양한 변형을 만들어야 합니다:
- 각 곡마다 다른 BPM, 다른 악기 조합, 다른 보컬 스타일
- 같은 장르라도 서브장르를 다양하게
- 가사 내용/주제를 매번 다르게

출력 형식 (JSON 배열):
[
  {
    "title": "곡 제목",
    "style_tags": "태그1, 태그2, 태그3",
    "prompt": "실제 가사 또는 곡 설명",
    "make_instrumental": false
  },
  ...
]

JSON만 출력하고 다른 텍스트는 포함하지 마세요.
"""

def generate_with_claude(
    genre: str,
    mood: str,
    structure: str,
    count: int,
    extra_instructions: str = "",
    api_key: str = "",
) -> list[SunoPrompt]:
    """Claude API를 사용하여 Suno 프롬프트를 생성합니다."""
    try:
        import anthropic
    except ImportError:
        raise RuntimeError("anthropic 패키지가 필요합니다: pip install anthropic")

    if not api_key:
        from config import ANTHROPIC_API_KEY
        api_key = ANTHROPIC_API_KEY

    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")

    client = anthropic.Anthropic(api_key=api_key)

    user_message = f"""
다음 조건으로 Suno 음악 프롬프트를 정확히 {count}개 생성해주세요:

장르: {genre}
무드/분위기: {mood}
곡 구성: {structure}
{f"추가 지시사항: {extra_instructions}" if extra_instructions else ""}

{count}개의 프롬프트를 만들되, 각각 충분히 다양하게 변형해주세요.
"""

    print(f"  🤖 Claude API로 {count}개 프롬프트 생성 중...")

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8000,
        system=CLAUDE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    raw = response.content[0].text.strip()

    # JSON 파싱 (마크다운 코드블록 처리)
    if "```" in raw:
        raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("```").strip()

    try:
        items = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Claude 응답을 파싱할 수 없습니다: {e}\n원문:\n{raw[:500]}")

    prompts = []
    for item in items[:count]:
        prompts.append(SunoPrompt(
            title=item.get("title", "Untitled"),
            style_tags=item.get("style_tags", genre),
            prompt=item.get("prompt", ""),
            make_instrumental=item.get("make_instrumental", False),
            source="claude",
            metadata={"genre": genre, "mood": mood, "structure": structure},
        ))

    print(f"  ✅ Claude가 {len(prompts)}개 프롬프트 생성 완료\n")
    return prompts


# ─────────────────────────────────────────────────────────
#  2. 템플릿 기반 생성기
# ─────────────────────────────────────────────────────────

def _load_templates() -> dict:
    """music_templates.json 로드"""
    tmpl_path = Path(__file__).parent / "music_templates.json"
    with open(tmpl_path, encoding="utf-8") as f:
        return json.load(f)


LYRIC_THEMES = [
    ("falling in love", "처음 만남, 설레는 감정, 눈 맞춤"),
    ("heartbreak", "이별 후 슬픔, 그리움, 빈 방"),
    ("chasing dreams", "목표를 향한 열정, 포기하지 않는 의지"),
    ("late night city", "도시의 밤, 네온 불빛, 고독한 걷기"),
    ("summer memories", "여름날의 추억, 친구들, 바닷가"),
    ("self growth", "나 자신을 찾아가는 여정, 성장, 치유"),
    ("rebellion", "규칙에 맞서는 반항, 자유, 진정한 나"),
    ("nostalgia", "어린 시절 추억, 돌아갈 수 없는 시간"),
    ("midnight confession", "새벽의 고백, 숨겨온 감정, 솔직함"),
    ("road trip", "떠남, 새로운 시작, 바람을 가르며"),
    ("power & confidence", "자신감, 무대 위의 나, 빛나는 존재"),
    ("loss & grief", "소중한 것을 잃음, 기억, 추모"),
    ("toxic love", "나쁜 줄 알면서 떠나지 못하는 사랑"),
    ("new beginning", "새벽의 시작, 희망, 첫날"),
    ("inner demons", "내면의 갈등, 어두운 생각과의 싸움"),
]

LYRIC_TEMPLATES = {
    "verse": [
        "Walking through the {setting}, feeling {emotion}\nEvery step I take is {action}\n{detail}",
        "In the {time_of_day}, I {action}\nThinking about {memory}\n{emotion} fills my heart",
        "Staring at the {object}, wondering {question}\n{feeling} runs through my veins",
    ],
    "chorus": [
        "And I {strong_emotion}, yeah I {strong_emotion}\nNothing can stop me now\nWatching the world {movement}\nThis is my {declaration}",
        "Hold on, {imperative}\nWe're {collective_action}\nFeeling {peak_emotion}\nUnder the {symbol}",
        "Take me {destination}\nWhere {desire}\nI've been {searching_action}\nFor this {abstract_noun}",
    ],
    "bridge": [
        "Maybe I was wrong, maybe I was right\nBut {realization}\nAnd now I {decision}",
        "All this time I {past_action}\nNever knowing {truth}\nNow I {present_state}",
    ]
}


def generate_with_templates(
    genre: str,
    mood: str,
    count: int,
    instrumental_ratio: float = 0.2,
) -> list[SunoPrompt]:
    """템플릿 기반으로 Suno 프롬프트를 빠르게 생성합니다."""
    templates = _load_templates()
    genres_data = templates.get("genres", {})
    vocal_styles = templates.get("vocal_styles", [])
    tempo_tags = templates.get("tempo_tags", {})

    # 장르 매칭 (대소문자 무시)
    genre_key = next((k for k in genres_data if k.lower() == genre.lower()), None)
    genre_data = genres_data.get(genre_key, {}) if genre_key else {}
    base_tags = genre_data.get("tags", f"{genre.lower()}, {mood.lower()}")

    # 무드 매칭
    mood_key = next(
        (k for k in genre_data.get("mood_map", {}) if k.lower() in mood.lower()),
        None
    )
    mood_desc = genre_data.get("mood_map", {}).get(mood_key, f"{mood} {genre}")

    prompts = []
    themes = random.sample(LYRIC_THEMES, min(count, len(LYRIC_THEMES)))
    if count > len(LYRIC_THEMES):
        themes += random.choices(LYRIC_THEMES, k=count - len(LYRIC_THEMES))

    tempos = list(tempo_tags.values())
    vocals = [v for v in vocal_styles if "instrumental" not in v]
    instrumental_vocals = ["no vocals (instrumental)"]

    for i in range(count):
        theme_en, theme_kr = themes[i]
        is_instrumental = random.random() < instrumental_ratio

        # 스타일 태그 조합
        tempo = random.choice(tempos)
        vocal = random.choice(instrumental_vocals if is_instrumental else vocals)
        extra_tags = random.choice([
            "reverb, lush production",
            "dry mix, raw sound",
            "atmospheric, layered",
            "minimal, stripped back",
            "studio quality, polished",
        ])
        style_tags = f"{base_tags}, {vocal}, {tempo}, {extra_tags}"

        # 제목 생성
        title_templates = [
            f"{theme_en.title()}",
            f"Lost in {genre_key or genre}",
            f"{mood.title()} Night",
            f"Song #{i+1:02d} — {theme_en.split(',')[0].title()}",
            f"The {genre_key or genre} Feeling",
        ]
        title = random.choice(title_templates)

        # 프롬프트/가사 생성
        if is_instrumental:
            structure_hints = genre_data.get("structure_hints", ["intro", "main theme", "outro"])
            prompt_lines = [f"[{hint.title()}]" for hint in structure_hints]
            prompt_lines.insert(0, f"# {mood_desc}")
            prompt_lines.append(f"# Theme: {theme_en}")
            prompt = "\n".join(prompt_lines)
        else:
            prompt = (
                f"[Verse 1]\n"
                f"(A song about {theme_en}. {theme_kr})\n"
                f"Feeling the {mood.lower()} of {genre_key or genre}\n"
                f"Every moment feels like {random.choice(['forever', 'a dream', 'the last time', 'something new'])}\n\n"
                f"[Pre-Chorus]\n"
                f"And I can feel it {random.choice(['rising', 'falling', 'building', 'fading'])}\n"
                f"This {mood.lower()} I {random.choice(['cannot hide', 'refuse to lose', 'carry alone', 'want to share'])}\n\n"
                f"[Chorus]\n"
                f"Take me to the {random.choice(['edge', 'top', 'place', 'moment'])} where {theme_en.split(',')[0]}\n"
                f"Let this {genre_key or genre} feeling {random.choice(['never end', 'wash over me', 'carry us away', 'set us free'])}\n"
                f"{mood.title()} and {random.choice(['alive', 'burning', 'breaking free', 'finding peace'])}\n"
                f"This is what it means to be {random.choice(['alive', 'free', 'real', 'here'])}\n\n"
                f"[Verse 2]\n"
                f"({theme_kr})\n"
                f"Looking back at {random.choice(['yesterday', 'who I was', 'the beginning', 'all of it'])}\n"
                f"Everything {random.choice(['has changed', 'feels different now', 'makes sense', 'starts again'])}\n\n"
                f"[Chorus]\n"
                f"Take me to the {random.choice(['edge', 'top', 'place', 'moment'])} where {theme_en.split(',')[0]}\n"
                f"Let this {genre_key or genre} feeling {random.choice(['never end', 'wash over me', 'carry us away', 'set us free'])}\n\n"
                f"[Bridge]\n"
                f"(Emotional peak — {mood_desc})\n"
                f"{random.choice(['Maybe', 'Perhaps', 'I know', 'I feel'])} {theme_en.split(',')[0]} is all I need\n"
                f"To {random.choice(['find my way', 'carry on', 'let it go', 'keep believing'])}\n\n"
                f"[Final Chorus]\n"
                f"(Full production, powerful)\n"
            )

        prompts.append(SunoPrompt(
            title=title,
            style_tags=style_tags,
            prompt=prompt,
            make_instrumental=is_instrumental,
            source="template",
            metadata={"genre": genre, "mood": mood, "theme": theme_en},
        ))

    print(f"  📋 템플릿으로 {len(prompts)}개 프롬프트 생성 완료\n")
    return prompts


# ─────────────────────────────────────────────────────────
#  3. 통합 생성기 (Claude + 템플릿 혼합)
# ─────────────────────────────────────────────────────────

def generate_prompts(
    genre: str,
    mood: str,
    structure: str,
    count: int,
    mode: str = "both",          # "claude" | "template" | "both"
    extra_instructions: str = "",
    api_key: str = "",
) -> list[SunoPrompt]:
    """
    통합 프롬프트 생성기.

    mode:
      "claude"   — Claude API만 사용
      "template" — 템플릿만 사용
      "both"     — Claude로 절반, 템플릿으로 나머지 생성 후 섞기
    """
    prompts: list[SunoPrompt] = []

    if mode == "claude":
        prompts = generate_with_claude(genre, mood, structure, count, extra_instructions, api_key)

    elif mode == "template":
        prompts = generate_with_templates(genre, mood, count)

    elif mode == "both":
        claude_count = max(1, count // 2)
        template_count = count - claude_count
        try:
            claude_prompts = generate_with_claude(
                genre, mood, structure, claude_count, extra_instructions, api_key
            )
        except Exception as e:
            print(f"  ⚠️  Claude API 실패 ({e}), 템플릿으로 대체합니다.")
            claude_prompts = generate_with_templates(genre, mood, claude_count)

        template_prompts = generate_with_templates(genre, mood, template_count)
        prompts = claude_prompts + template_prompts
        random.shuffle(prompts)

    return prompts[:count]


# ─────────────────────────────────────────────────────────
#  CLI 테스트
# ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== 프롬프트 생성 테스트 ===\n")
    results = generate_prompts(
        genre="K-Pop",
        mood="upbeat and energetic",
        structure="verse-chorus-bridge",
        count=3,
        mode="template",
    )
    for i, p in enumerate(results):
        print(f"─── 프롬프트 {i+1} ───")
        print(p.preview())
        print()
