"""Date-partitioned PubMed search and PMID deduplication."""
from __future__ import annotations

from datetime import date, timedelta
import logging
from typing import Iterable

LOG = logging.getLogger(__name__)


def periods(start: date, end: date, frequency: str = 'quarter') -> list[tuple[date, date]]:
    if start > end:
        raise ValueError('Start date must not be after end date')
    if frequency not in {'quarter', 'year'}:
        raise ValueError('frequency must be quarter or year')
    result = []
    cursor = start
    while cursor <= end:
        if frequency == 'year':
            exclusive = date(cursor.year + 1, 1, 1)
        else:
            next_quarter_month = ((cursor.month - 1) // 3 + 1) * 3 + 1
            exclusive = (date(cursor.year + 1, 1, 1) if next_quarter_month > 12
                         else date(cursor.year, next_quarter_month, 1))
        period_end = min(end, exclusive - timedelta(days=1))
        result.append((cursor, period_end))
        cursor = period_end + timedelta(days=1)
    return result


def iter_slice_ids(client, query: str, start: date, end: date,
                   page_size: int = 200, max_window: int = 9500) -> Iterable[str]:
    """Recursively split dates if ESearch exceeds its PubMed 10K result window."""
    if page_size < 1 or page_size > max_window:
        raise ValueError('Invalid page size')
    start_s, end_s = start.isoformat(), end.isoformat()
    count, first_ids = client.search(query, start_s, end_s, retmax=page_size)
    if count > max_window:
        if start == end:
            raise RuntimeError(f'{count} results on {start}: cannot split one day; '
                               'refine the search expression.')
        days = (end - start).days
        midpoint = start + timedelta(days=days // 2)
        LOG.info('Splitting %s~%s (%s hits) into smaller ranges', start, end, count)
        yield from iter_slice_ids(client, query, start, midpoint, page_size, max_window)
        yield from iter_slice_ids(client, query, midpoint + timedelta(days=1), end,
                                  page_size, max_window)
        return
    yield from first_ids
    for offset in range(len(first_ids), count, page_size):
        page_count, ids = client.search(query, start_s, end_s,
                                        retstart=offset, retmax=page_size)
        if not ids:
            raise RuntimeError(f'Unexpected empty search page: offset {offset}/{count}')
        yield from ids
        if page_count != count:
            LOG.warning('PubMed result count changed during pagination: %d -> %d',
                        count, page_count)


def collect_pmids(client, queries: list[str], start: date, end: date,
                  frequency: str = 'quarter', page_size: int = 200,
                  max_pmids: int | None = None) -> list[str]:
    """Combine multiple search expressions and deduplicate PMIDs in stable order."""
    seen: set[str] = set()
    ordered = []
    for query_number, query in enumerate(queries, 1):
        for section_start, section_end in periods(start, end, frequency):
            LOG.info('Query %d/%d | %s–%s', query_number, len(queries),
                     section_start, section_end)
            for pmid in iter_slice_ids(client, query, section_start, section_end,
                                      page_size=page_size):
                if pmid not in seen:
                    seen.add(pmid)
                    ordered.append(pmid)
                    if max_pmids and len(ordered) >= max_pmids:
                        return ordered
    return ordered
