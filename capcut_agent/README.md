# CapCut 음악 편집 자동화 / Music Compilation Automation

pycapcut을 사용하여 50개 이상의 노래를 하나의 CapCut 프로젝트로 자동 편집합니다.

## 기능

- 음악 폴더의 오디오 파일을 자동으로 스캔하여 순서대로 배치
- 각 노래마다 **2초 fade out** 자동 적용
- 각 노래 사이 **2초 간격** 유지
- 이미지 폴더가 있으면 **슬라이드쇼 배경** 자동 추가 (노래 수에 맞게 순환)
- 각 노래 시작 시 **제목 텍스트** 자동 표시 (5초간)
- 노래 제목과 길이가 담긴 **Word 문서 (.docx)** 자동 생성

## 설치

```bash
pip install -r requirements.txt
```

## 설정

로컬 환경 설정 파일(`.env`)을 통해 경로 및 설정을 수정할 수 있습니다.

1. `capcut_agent` 폴더 내에 있는 `.env.example` 파일을 복사하여 `.env` 파일을 생성합니다.
2. 생성한 `.env` 파일을 편집기에서 열어 환경변수 값을 본인의 경로와 초안 이름에 맞게 수정합니다:
   ```env
   MUSIC_FOLDER=C:\Users\Sung\YouTube-Playlist\Contents\0604
   IMAGES_FOLDER=C:\Users\Sung\YouTube-Playlist\Contents\0604
   CAPCUT_DRAFT_FOLDER=C:\Users\Sung\AppData\Local\CapCut\User Data\Projects\com.lveditor.draft
   DRAFT_NAME=Girl Smile4
   ```

*참고: `.env` 파일은 Git에 의해 추적되지 않으므로 개별 환경설정 사항이 Git에 커밋되지 않습니다.*

### CapCut 초안 폴더 찾기

CapCut 앱에서: **설정 → 초안 위치** 에서 확인하세요.  
기본 경로 예시:
```
C:\Users\<사용자명>\AppData\Local\CapCut\User Data\Projects\com.lveditor.draft
```

## 실행

```bash
python capcut_music_editor.py
```

## 실행 후

1. CapCut을 열거나 재시작합니다
2. 초안 목록에서 설정한 이름(`Music Compilation`)을 찾아 엽니다
3. 음악 폴더에 `노래목록.docx` 파일이 생성됩니다

## 파일 구조

```
capcut_music_editor.py    ← 메인 스크립트
requirements.txt           ← 패키지 목록
README.md                  ← 이 파일
```

## 지원 파일 형식

| 오디오 | 이미지 |
|--------|--------|
| .mp3, .wav, .flac | .jpg, .jpeg, .png |
| .aac, .m4a, .ogg  | .bmp, .webp        |

## 타이밍 설정 변경

`capcut_music_editor.py` CONFIG 섹션:

```python
FADE_OUT_SECONDS  = 2   # 페이드 아웃 길이 (초)
GAP_SECONDS       = 2   # 노래 사이 간격 (초)
TITLE_SHOW_SECONDS = 5  # 제목 표시 시간 (초)
```

---

*Built with [pycapcut](https://github.com/GuanYixuan/pyCapCut)*
