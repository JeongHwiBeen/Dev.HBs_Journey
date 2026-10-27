"""키워드 막대그래프(Plotly HTML), 워드클라우드(PNG) 생성."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def save_keyword_bar(frequencies: pd.DataFrame, output_path: str | Path, *, top_n: int = 20, title: str = "키워드 빈도") -> Path | None:
    """원본 px.bar() 그래프를 로컬 HTML로 저장합니다."""
    if frequencies.empty:
        return None
    import plotly.express as px

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    top = frequencies.nlargest(top_n, "count")
    fig = px.bar(top, x="word", y="count", text="count", title=title, labels={"word": "명사", "count": "빈도수"})
    fig.write_html(str(output), include_plotlyjs=True, full_html=True)
    return output


def save_wordcloud(
    frequencies: pd.DataFrame,
    output_path: str | Path,
    *,
    font_path: str | Path,
    mask_path: str | Path | None = None,
    width: int = 1000,
    height: int = 700,
) -> Path | None:
    """원본 wordcloud + 선택적 마스크 이미지 컬러링 기능을 재사용합니다."""
    if frequencies.empty:
        return None
    from wordcloud import ImageColorGenerator, WordCloud
    font_file = Path(font_path)
    if not font_file.is_file():
        raise FileNotFoundError(f"워드클라우드에 사용할 한글 폰트 파일이 없습니다: {font_file}")

    wc_args = {
        "font_path": str(font_file),
        "background_color": "white",
        "width": width,
        "height": height,
    }
    if mask_path is not None:
        import numpy as np
        from PIL import Image

        mask_file = Path(mask_path)
        if not mask_file.is_file():
            raise FileNotFoundError(f"워드클라우드 마스크 이미지가 없습니다: {mask_file}")
        with Image.open(mask_file) as image:
            mask = np.array(image.convert("RGB"))
        wc_args["mask"] = mask

    word_frequencies = dict(zip(frequencies["word"], frequencies["count"]))
    wc = WordCloud(**wc_args).generate_from_frequencies(word_frequencies)
    if mask_path is not None:
        wc = wc.recolor(color_func=ImageColorGenerator(mask, default_color=(255, 255, 255)))

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    wc.to_file(str(output))
    return output
