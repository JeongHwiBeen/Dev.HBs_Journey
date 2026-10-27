from disaster_alert_improvement.keyword_analysis import extract_keywords


class DummyOkt:
    def nouns(self, text):
        return ["재난", "재난", "안전", "것", "경보"]


def test_keyword_frequency():
    result = extract_keywords(["dummy"], stopwords={"것"}, okt=DummyOkt())
    assert dict(zip(result["word"], result["count"])) == {"재난": 2, "경보": 1, "안전": 1}
