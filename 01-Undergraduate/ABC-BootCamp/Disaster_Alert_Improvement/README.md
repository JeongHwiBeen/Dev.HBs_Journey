# Disaster Alert Improvement

**데이터 기반 재난·실종경보문자 분석 및 개선 방안 제안**  
ABC 부트캠프 4기 미니 프로젝트 코드를 기능별 Python 모듈로 정리한 아카이브입니다.

## 프로젝트 개요

재난안전데이터 공유플랫폼에서 경보문자 목록을 수집하고, **기존에 수집된** 실종경보·재난경보 관련 YouTube 댓글 데이터를 키워드 빈도와 감성사전 점수로 분석합니다. 분석 결과를 바탕으로 경보문자에 실용적인 정보와 구체적인 행동 지침을 제공하는 개선 방향을 제안했던 팀 프로젝트입니다.

**분석 흐름**: 재난문자 목록 크롤링 → (별도로 확보한) YouTube 댓글 CSV 읽기 → Okt 명사 추출 및 키워드 분석 → KNU SentiWord 사전 기반 감성점수 계산 → 시각화 → 개선 방안 제안

> 참고: 이 저장소의 코드에는 **YouTube 댓글 자체를 수집하는 크롤러가 포함되어 있지 않습니다.** 원본 Notebook도 로컬 CSV를 로드해 분석합니다. 또한 개선 방안은 발표자료에 기술된 **제안 사항**이며, 개선된 문자 발송 시스템을 구현·검증한 결과가 아닙니다.

## 폴더 구조

```text
Disaster-Alert-Improvement/
├── main.py                           # 실행 CLI
├── requirements.txt
├── src/disaster_alert_improvement/
│   ├── disaster_crawler.py           # 재난문자 목록 크롤링
│   ├── preprocessing.py              # 댓글 CSV 읽기/컬럼 표준화
│   ├── keyword_analysis.py           # Okt 명사 추출/빈도
│   ├── sentiment_analysis.py         # KNU 감성사전 점수 계산
│   ├── visualization.py              # Plotly/WordCloud
│   └── pipeline.py                   # 데이터 분석 실행/결과 저장
├── data/raw/                         # 원본 입력 파일(공개 제외)
├── assets/                           # 선택적 폰트/마스크(공개 제외)
├── outputs/                          # 실행 결과(공개 제외)
├── docs/source-mapping.md            # 원본 파일과 모듈 대응표
└── tests/                             # 오프라인 단위 테스트
```

## 설치

Python 3.10 이상, 분석에는 **Java 런타임(KoNLPy Okt)**, 크롤링에는 **Chrome 브라우저**가 필요합니다.

```bash
python -m venv .venv
source .venv/bin/activate             # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py --help
```

## 입력 데이터 준비

제공된 소스코드는 다음 외부 자료를 참조합니다. 자료의 원본은 **이번 배포물에 포함되지 않았습니다.**

| 필요한 자료 | 저장 권장 위치 | 기대 열/형식 |
| --- | --- | --- |
| 실종경보 YouTube 댓글 CSV | `data/raw/missing_alert_comments.csv` | `댓글내용` 또는 `댓글 내용` |
| 재난경보 YouTube 댓글 CSV | `data/raw/disaster_alert_comments.csv` | `댓글 내용` 또는 `댓글내용` |
| KNU SentiWord 감성사전 | `data/raw/SentiWord_info.json` | 각 원소에 `word_root`, `polarity` 포함 |
| 한글 폰트 | 임의의 로컬 경로 | 한글을 지원하는 TTF/OTF 파일(선택) |
| 마스크 이미지 | 임의의 로컬 경로 | PNG 이미지(선택) |

사용 데이터의 공개 가능 여부·개인정보·라이선스를 확인한 뒤 관리하세요. `.gitignore` 기본 설정은 원본 데이터, 폰트, 이미지 및 생성 결과의 실수로 인한 업로드를 막습니다.

## 실행 예시

### 1) 재난문자 목록 수집

```bash
# 우선 3페이지를 대상으로 시도
python main.py crawl --headless --max-pages 3

# 전체 페이지 수집
python main.py crawl --headless
```

기본 저장 파일: `data/raw/disaster_messages.csv` (`제목`, `등록일`). 사이트 구조 변경/접속 정책에 따라 실행이 실패할 수 있습니다. 서버 정책과 이용약관을 준수하세요.

### 2) 실종경보 댓글 분석

```bash
python main.py analyze \
  --kind missing \
  --comments data/raw/missing_alert_comments.csv \
  --lexicon data/raw/SentiWord_info.json
```

### 3) 재난경보 댓글 분석

```bash
python main.py analyze \
  --kind disaster \
  --comments data/raw/disaster_alert_comments.csv \
  --lexicon data/raw/SentiWord_info.json
```

### 4) 한글 워드클라우드 포함

```bash
python main.py analyze \
  --kind disaster \
  --comments data/raw/disaster_alert_comments.csv \
  --lexicon data/raw/SentiWord_info.json \
  --font /path/to/korean-font.ttf
```

`--font`를 지정하면 전체·긍정·부정 워드클라우드 PNG가 생성됩니다. 마스크 이미지는 `--positive-mask`, `--negative-mask` 옵션으로 추가할 수 있습니다. 한글 폰트 파일은 저장소에 포함하지 않습니다.

## 생성 결과

`outputs/missing/`, `outputs/disaster/` 폴더별로 다음 파일이 만들어집니다.

| 파일 | 설명 |
| --- | --- |
| `sentiment_scores.csv` | 댓글별 KNU 감성점수 |
| `comments_all.csv`, `comments_positive.csv`, `comments_negative.csv`, `comments_middle.csv` | 전체/긍정/부정/중간 구간 댓글 |
| `keywords_all.csv`, `keywords_positive.csv`, `keywords_negative.csv` | 명사 빈도수 |
| `keywords_*.html` | Plotly 인터랙티브 상위 키워드 막대그래프(데이터가 있을 때) |
| `wordcloud_*.png` | 한글 폰트를 지정한 경우 생성하는 워드클라우드 |

**원본 기준:** 긍정 `점수 >= 0`, 부정 `점수 <= -20`, 그 사이 `-20 < 점수 < 0`은 `middle`로 따로 저장합니다. 이 경계값은 원본 실습 코드의 선택이며 통계적·임상적 기준이 아닙니다. 점수는 문맥을 해석하는 모델이 아니라 **사전의 단어 부분 문자열 포함 여부를 합산**한 값입니다.

## 검증 및 주의사항

```bash
python -m pytest -q
```

- HTML 분석, 감성점수, 키워드 빈도, 입력 CSV 표준화를 오프라인 테스트합니다.
- **실제 사이트 접속 및 원본 CSV·감성사전 기반 전체 실행은 검증하지 않았습니다.** 해당 자료가 필요합니다.
- 데이터와 발표 결과의 동일성(실종/재난 비율, 감성평가)은 원본 입력과 환경 없이는 보장할 수 없습니다.
- 팀 프로젝트에서 본인의 담당 업무와 공동 작업은 사실대로 구분하여 소개하세요.

원본 Notebook별 코드 배치와 수정 내용은 [docs/source-mapping.md](docs/source-mapping.md)에 기록했습니다.
