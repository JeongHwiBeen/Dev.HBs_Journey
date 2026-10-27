import json

import pandas as pd
import pytest

from disaster_alert_improvement.sentiment_analysis import (
    load_sentiment_lexicon,
    score_comments,
    sentiment_score_per_comment,
    split_sentiments,
)


def test_lexicon_parsing_and_legacy_substring_scoring(tmp_path):
    source = tmp_path / "SentiWord_info.json"
    source.write_text(json.dumps([{"word_root": "좋", "polarity": "2"}, {"word_root": "불편", "polarity": "-3"}], ensure_ascii=False), encoding="utf-8")
    lexicon = load_sentiment_lexicon(source)
    assert sentiment_score_per_comment("좋지만 불편", lexicon) == -1
    assert sentiment_score_per_comment(None, lexicon) == 0


def test_sentiment_filters_keep_original_cutoffs():
    scores = pd.DataFrame({"댓글 내용": ["a", "b", "c", "d"], "감성점수 총합": [3, 0, -3, -20]})
    out = split_sentiments(scores)
    assert out["positive"]["댓글 내용"].tolist() == ["a", "b"]
    assert out["negative"]["댓글 내용"].tolist() == ["d"]
    assert out["middle"]["댓글 내용"].tolist() == ["c"]


def test_scoring_empty_comments():
    comments = pd.DataFrame({"댓글 내용": [None, "좋다"]})
    scored = score_comments(comments, [("좋", 2)])
    assert scored["감성점수 총합"].tolist() == [0, 2]
