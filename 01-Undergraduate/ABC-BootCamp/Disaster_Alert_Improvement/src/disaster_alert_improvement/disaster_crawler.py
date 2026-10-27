"""재난안전데이터 공유플랫폼의 재난문자 목록 수집.

원본: '7조_재난문자 전체_크롤링.py'
페이지 탐색 방식과 HTML 선택자(board-count, tableHover, cell-date)를 유지합니다.
사이트 구조 변경 시 선택자 수정이 필요할 수 있습니다.
"""

from __future__ import annotations

import math
import re
import time
from pathlib import Path
from urllib.parse import urlencode

import pandas as pd
from bs4 import BeautifulSoup

BASE_URL = "https://www.safetydata.go.kr/disaster-data/disasterNotification"
PAGE_SIZE = 10


def build_page_url(page: int) -> str:
    """원본 코드에서 사용한 재난문자 페이지 URL을 생성합니다."""
    if page < 1:
        raise ValueError("페이지 번호는 1 이상이어야 합니다.")
    params = {
        "searchStartDttm": "",
        "searchEndDttm": "",
        "keyword": "",
        "orderBy": "",
        "currentPage": page,
        "cntPerPage": PAGE_SIZE,
        "pageSize": PAGE_SIZE,
    }
    return f"{BASE_URL}?{urlencode(params)}"


def parse_total_count(html: str) -> int:
    """목록 상단의 총 재난문자 수를 가져옵니다."""
    soup = BeautifulSoup(html, "html.parser")
    node = soup.select_one("p.board-count")
    if node is None:
        raise ValueError("총 건수(board-count)를 찾지 못했습니다. 사이트 구조를 확인하세요.")
    digits = re.sub(r"[^0-9]", "", node.get_text(" ", strip=True))
    if not digits:
        raise ValueError("총 건수를 숫자로 해석할 수 없습니다.")
    return int(digits)


def parse_alert_rows(html: str) -> pd.DataFrame:
    """표에서 제목/등록일을 추출합니다(원본 데이터 구조 유지)."""
    soup = BeautifulSoup(html, "html.parser")
    titles = [tag.get_text(" ", strip=True) for tag in soup.select("a.tableHover")]
    dates = [tag.get_text(" ", strip=True) for tag in soup.select("td.cell-date")]
    if len(titles) != len(dates):
        raise ValueError(
            f"제목({len(titles)})과 등록일({len(dates)}) 건수가 다릅니다. HTML 선택자를 확인하세요."
        )
    return pd.DataFrame({"제목": titles, "등록일": dates})


def create_driver(*, headless: bool = False, no_sandbox: bool = False):
    """Chrome WebDriver를 생성합니다. Selenium은 크롤링 시에만 필요합니다."""
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service as ChromeService
    from webdriver_manager.chrome import ChromeDriverManager

    options = webdriver.ChromeOptions()
    options.add_argument("--disable-dev-shm-usage")
    if headless:
        options.add_argument("--headless=new")
    # 원본은 기본으로 샌드박스를 비활성화했지만, 이 옵션은 필요한 환경에서만 사용합니다.
    if no_sandbox:
        options.add_argument("--no-sandbox")
    service = ChromeService(executable_path=ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)


def crawl_disaster_alerts(
    output_path: str | Path,
    *,
    start_page: int = 1,
    max_pages: int | None = None,
    delay: float = 3.0,
    headless: bool = False,
    no_sandbox: bool = False,
) -> pd.DataFrame:
    """재난문자를 페이지별로 수집하고 UTF-8 BOM CSV로 저장합니다.

    원본은 페이지 진입 및 스크롤 후 각 3초 대기했습니다. delay를 통해 조절합니다.
    """
    if start_page < 1 or (max_pages is not None and max_pages < 1) or delay < 0:
        raise ValueError("start_page/max_pages는 양수, delay는 0 이상이어야 합니다.")

    driver = create_driver(headless=headless, no_sandbox=no_sandbox)
    try:
        driver.get(build_page_url(start_page))
        time.sleep(delay)
        count = parse_total_count(driver.page_source)
        last_page = math.ceil(count / PAGE_SIZE)
        end_page = min(last_page, start_page + max_pages - 1) if max_pages else last_page

        frames = []
        for page in range(start_page, end_page + 1):
            driver.get(build_page_url(page))
            time.sleep(delay)
            driver.execute_script("window.scrollTo(0, 800)")
            time.sleep(delay)
            frame = parse_alert_rows(driver.page_source)
            frames.append(frame)
            print(f"[{page}/{end_page}] 수집 완료: {len(frame)}건")

        result = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["제목", "등록일"])
        dest = Path(output_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        result.to_csv(dest, index=False, encoding="utf-8-sig")
        print(f"총 {len(result)}건 저장: {dest}")
        return result
    finally:
        driver.quit()
