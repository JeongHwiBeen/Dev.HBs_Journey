"""실제 KoNLPy/외부 데이터 없이 파일 파이프라인 접합부를 검증합니다."""

import json
import sys
import types

import pandas as pd

from disaster_alert_improvement.pipeline import analyze_comments


class FakeOkt:
    def nouns(self, text):
        return [word.strip() for word in text.split() if word.strip()]


def test_end_to_end_with_local_fixtures(tmp_path, monkeypatch):
    fake_tag_module = types.ModuleType("konlpy.tag")
    fake_tag_module.Okt = FakeOkt
    monkeypatch.setitem(sys.modules, "konlpy", types.ModuleType("konlpy"))
    monkeypatch.setitem(sys.modules, "konlpy.tag", fake_tag_module)

    csv = tmp_path / "comments.csv"
    pd.DataFrame({"댓글내용": ["좋아요 안전", "위험 불안", "알림"]}).to_csv(csv, index=False)
    lexicon = tmp_path / "SentiWord_info.json"
    lexicon.write_text(
        json.dumps([{"word_root": "좋", "polarity": "1"}, {"word_root": "위험", "polarity": "-20"}], ensure_ascii=False),
        encoding="utf-8",
    )
    output = tmp_path / "out"
    summary = analyze_comments(kind="missing", comments_csv=csv, lexicon_json=lexicon, output_dir=output)
    assert summary == {"all": 3, "positive": 2, "negative": 1, "middle": 0}
    assert (output / "missing" / "sentiment_scores.csv").exists()
    assert (output / "missing" / "keywords_all.csv").exists()
    assert (output / "missing" / "keywords_all.html").exists()
    assert (output / "missing" / "comments_negative.csv").exists()
