"""실종경보·재난경보 YouTube 댓글 CSV 입력값 정규화."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

# 원본 실종경보 Notebook은 '댓글내용', 재난경보 Notebook은 '댓글 내용' 사용.
COMMENT_COLUMNS = ("댓글 내용", "댓글내용")

# 원본 Notebook별로 불용어 목록이 조금 다르므로 각각 유지합니다.
STOPWORDS = {
    "missing": frozenset(
        ("문제", "생각", "그냥", "진짜", "지금", "정도", "때문", "이제", "하나", "모든", "더", "거", "정말", "요")
    ),
    "disaster": frozenset(
        ("문제", "생각", "그냥", "진짜", "지금", "정도", "때문", "이제", "하나", "모든", "것", "뭐")
    ),
}


def load_comments(csv_path: str | Path, *, column: str | None = None) -> pd.DataFrame:
    """입력 CSV를 읽고 댓글 열을 '댓글 내용'으로 통일합니다."""
    source = Path(csv_path)
    if not source.is_file():
        raise FileNotFoundError(f"댓글 CSV가 없습니다: {source}")
    data = pd.read_csv(source, encoding="utf-8-sig")
    candidates = (column,) if column else COMMENT_COLUMNS
    matched = next((candidate for candidate in candidates if candidate in data.columns), None)
    if matched is None:
        raise ValueError(f"댓글 열이 없습니다. 예상 열: {list(candidates)} / 실제 열: {list(data.columns)}")
    return pd.DataFrame({"댓글 내용": data[matched].fillna("").astype(str)})
