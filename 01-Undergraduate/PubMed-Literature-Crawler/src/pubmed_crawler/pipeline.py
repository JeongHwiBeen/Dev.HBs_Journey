"""Checkpointed search/download orchestration and CSV export."""
from __future__ import annotations

import csv
import json
import logging
from pathlib import Path

from .parser import COLUMNS, parse_articles
from .search import collect_pmids

LOG = logging.getLogger(__name__)


def save_pmids(pmids: list[str], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(pmids, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)


def load_pmids(path: Path) -> list[str]:
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, list) or any(not isinstance(pmid, str) for pmid in value):
        raise ValueError('PMID JSON must be an array of strings')
    return list(dict.fromkeys(value))


def search_and_save(client, queries: list[str], start, end, frequency: str,
                    output_file: Path, max_pmids: int | None = None) -> list[str]:
    pmids = collect_pmids(client, queries, start, end, frequency,
                          max_pmids=max_pmids)
    save_pmids(pmids, output_file)
    LOG.info('Collected %d unique PMIDs -> %s', len(pmids), output_file)
    return pmids


def read_existing_pmids(csv_file: Path) -> set[str]:
    if not csv_file.exists() or not csv_file.stat().st_size:
        return set()
    with csv_file.open('r', encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not set(COLUMNS).issubset(reader.fieldnames):
            raise ValueError('Existing CSV does not match expected output columns')
        return {row['PMID'] for row in reader if row.get('PMID')}


def fetch_and_save(client, pmids: list[str], csv_file: Path,
                   batch_size: int = 200, resume: bool = False) -> tuple[int,int]:
    if batch_size < 1 or batch_size > 500:
        raise ValueError('batch_size must be 1..500')
    csv_file.parent.mkdir(parents=True, exist_ok=True)
    completed = read_existing_pmids(csv_file) if resume else set()
    remaining = [p for p in dict.fromkeys(pmids) if p not in completed]
    if resume and csv_file.exists():
        write_mode = 'a'
    else:
        write_mode = 'w'
    written = 0
    with csv_file.open(write_mode, encoding='utf-8-sig' if write_mode == 'w' else 'utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        if write_mode == 'w' or not csv_file.stat().st_size:
            writer.writeheader()
        for offset in range(0, len(remaining), batch_size):
            batch = remaining[offset:offset + batch_size]
            response = client.fetch(batch)
            rows = parse_articles(response)
            actual = {row['PMID'] for row in rows}
            missing = set(batch) - actual
            if missing:
                # Explicitly fail rather than silently treating absent records as collected.
                raise RuntimeError('NCBI omitted PMIDs from EFetch response: ' +
                                   ', '.join(sorted(missing)))
            for row in rows:
                if row['PMID'] not in completed:
                    writer.writerow(row)
                    completed.add(row['PMID'])
                    written += 1
            handle.flush()  # Batch results remain recoverable if interrupted.
            LOG.info('Downloaded %d/%d new articles', min(offset + batch_size, len(remaining)),
                     len(remaining))
    LOG.info('Saved %d new articles to %s', written, csv_file)
    return written, len(completed)
