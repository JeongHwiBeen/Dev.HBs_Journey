"""KNU SentiWord 감성사전을 사용하는 규칙 기반 댓글 감성분석.

원본 로직: 사전의 word_root가 댓글에 포함되면 해당 polarity를 1회 가산.
긍정 >= 0, 부정 <= -20 경계값은 원본에서 사용한 실험 기준입니다.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def load_sentiment_lexicon(path: str | Path) -> list[tuple[str, float]]:
    """KNU SentiWord_info.json의 word_root, polarity 필드를 읽습니다."""
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"감성사전 파일이 없습니다: {source}")
    with source.open("r", encoding="utf-8-sig") as stream:
        records = json.load(stream)
    if not isinstance(records, list):
        raise ValueError("감성사전은 객체 목록(JSON array)이어야 합니다.")
    entries: list[tuple[str, float]] = []
    for index, item in enumerate(records):
        if not isinstance(item, dict) or "word_root" not in item or "polarity" not in item:
            raise ValueError(f"감성사전 {index}번 항목에 word_root/polarity가 없습니다.")
        root = str(item["word_root"]).strip() if item["word_root"] is not None else ""
        polarity = item["polarity"]
        if not root or polarity is None or str(polarity).strip() == "":
            continue
        try:
            score = float(polarity)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"감성사전 {index}번 polarity가 숫자가 아닙니다: {polarity!r}") from exc
        entries.append((root, score))
    return entries


def sentiment_score_per_comment(comment: object, lexicon: list[tuple[str, float]]) -> float:
    """원본 Notebook처럼 댓글에 포함된 각 사전 표제어의 점수를 더합니다."""
    if not isinstance(comment, str):
        return 0.0
    return sum(score for root, score in lexicon if root in comment)


def score_comments(comments: pd.DataFrame, lexicon: list[tuple[str, float]]) -> pd.DataFrame:
    """원본 컬럼명에 맞춰 댓글별 감성점수를 반환합니다."""
    if "댓글 내용" not in comments.columns:
        raise ValueError("댓글 데이터에 '댓글 내용' 열이 없습니다.")
    texts = comments["댓글 내용"].fillna("").astype(str).reset_index(drop=True)
    return pd.DataFrame(
        {"댓글 내용": texts, "감성점수 총합": texts.map(lambda text: sentiment_score_per_comment(text, lexicon))}
    )


def split_sentiments(
    scores: pd.DataFrame, *, positive_min: float = 0, negative_max: float = -20
) -> dict[str, pd.DataFrame]:
    """긍정·부정·중간 구간을 구분합니다.

    0점은 원본과 동일하게 긍정에 포함됩니다. -20 < x < 0은 별도 '중간'으로 저장합니다.
    """
    if negative_max >= positive_min:
        raise ValueError("부정 상한은 긍정 하한보다 작아야 합니다.")
    col = scores["감성점수 총합"]
    return {
        "positive": scores.loc[col >= positive_min].copy(),
        "negative": scores.loc[col <= negative_max].copy(),
        "middle": scores.loc[(col > negative_max) & (col < positive_min)].copy(),
    }
