from disaster_alert_improvement.disaster_crawler import build_page_url, parse_alert_rows, parse_total_count


def test_total_and_rows():
    html = '''<p class="board-count">총 23건</p><table><tr>
    <td><a class="tableHover">폭우주의보</a></td><td class="cell-date">2024-07-25</td>
    </tr></table>'''
    assert parse_total_count(html) == 23
    rows = parse_alert_rows(html)
    assert rows.iloc[0].to_dict() == {"제목": "폭우주의보", "등록일": "2024-07-25"}
    assert "currentPage=2" in build_page_url(2)
