"""KoNLPy Okt 명사 추출과 빈도수 집계(실종·재난 공통)."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

import pandas as pd


def extract_keywords(
    comments: Iterable[object],
    *,
    stopwords: frozenset[str] | set[str] = frozenset(),
    min_length: int = 2,
    okt=None,
) -> pd.DataFrame:
    """댓글에서 명사를 추출하고 실제 등장 횟수로 집계합니다.

    원본의 '단어 길이를 count에 기록한 뒤 groupby count' 중복 과정을 단순화했습니다.
    원본 감성분석의 min_length > 1 기준을 기본값으로 사용합니다.
    """
    if min_length < 1:
        raise ValueError("min_length는 1 이상이어야 합니다.")
    if okt is None:
        from konlpy.tag import Okt

        okt = Okt()
    text = " ".join(str(value) for value in comments if isinstance(value, str))
    nouns = okt.nouns(text)
    count = Counter(word for word in nouns if len(word) >= min_length and word not in stopwords)
    return pd.DataFrame(
        sorted(count.items(), key=lambda item: (-item[1], item[0])), columns=["word", "count"]
    )
