"""분석 모듈을 연결하여 CSV 및 시각화 파일로 저장."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .keyword_analysis import extract_keywords
from .preprocessing import STOPWORDS, load_comments
from .sentiment_analysis import load_sentiment_lexicon, score_comments, split_sentiments
from .visualization import save_keyword_bar, save_wordcloud


def analyze_comments(
    *,
    kind: str,
    comments_csv: str | Path,
    lexicon_json: str | Path,
    output_dir: str | Path,
    font_path: str | Path | None = None,
    positive_mask: str | Path | None = None,
    negative_mask: str | Path | None = None,
    top_n: int = 20,
    positive_min: float = 0,
    negative_max: float = -20,
) -> dict[str, int]:
    """카테고리별 명사 빈도, 감성점수, 긍·부정 워드클라우드 생성."""
    if kind not in STOPWORDS:
        raise ValueError(f"분석 유형은 {list(STOPWORDS)} 중 하나여야 합니다.")
    if top_n < 1:
        raise ValueError("top_n은 1 이상이어야 합니다.")

    dest = Path(output_dir) / kind
    dest.mkdir(parents=True, exist_ok=True)
    comments = load_comments(comments_csv)
    scores = score_comments(comments, load_sentiment_lexicon(lexicon_json))
    scores.to_csv(dest / "sentiment_scores.csv", index=False, encoding="utf-8-sig")
    groups = split_sentiments(scores, positive_min=positive_min, negative_max=negative_max)

    # 하나의 Okt 인스턴스를 공통 사용(원본 Notebook의 초기화 중복 제거).
    from konlpy.tag import Okt

    okt = Okt()
    segments: dict[str, pd.DataFrame] = {"all": scores, **groups}
    for segment, frame in segments.items():
        # 중간 구간도 별도 CSV로 저장하지만, 시각화 대상은 원본과 동일하게 전체/긍정/부정입니다.
        frame.to_csv(dest / f"comments_{segment}.csv", index=False, encoding="utf-8-sig")
        if segment == "middle":
            continue
        freq = extract_keywords(frame["댓글 내용"], stopwords=STOPWORDS[kind], okt=okt)
        freq.to_csv(dest / f"keywords_{segment}.csv", index=False, encoding="utf-8-sig")
        save_keyword_bar(freq, dest / f"keywords_{segment}.html", top_n=top_n, title=f"{kind} - {segment}")
        if font_path is not None:
            mask = positive_mask if segment == "positive" else negative_mask if segment == "negative" else None
            save_wordcloud(freq, dest / f"wordcloud_{segment}.png", font_path=font_path, mask_path=mask)

    return {"all": len(scores), **{name: len(frame) for name, frame in groups.items()}}
