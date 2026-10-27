import pandas as pd
import pytest
from disaster_alert_improvement.preprocessing import load_comments


def test_comments_columns_for_two_notebooks(tmp_path):
    for name in ("댓글내용", "댓글 내용"):
        source = tmp_path / f"{len(name)}.csv"
        pd.DataFrame({name: ["경보문자 좋아요", None]}).to_csv(source, index=False)
        result = load_comments(source)
        assert result.columns.tolist() == ["댓글 내용"]
        assert result["댓글 내용"].tolist() == ["경보문자 좋아요", ""]


def test_missing_comment_column(tmp_path):
    source = tmp_path / "x.csv"
    pd.DataFrame({"의견": ["abc"]}).to_csv(source, index=False)
    with pytest.raises(ValueError, match="댓글 열이 없습니다"):
        load_comments(source)
