"""Command-line interface: search / fetch / run PubMed literature collection."""
from __future__ import annotations

import argparse
from datetime import date
import json
import logging
import os
from pathlib import Path

from .client import PubMedClient
from .pipeline import fetch_and_save, load_pmids, search_and_save

ROOT = Path(__file__).resolve().parents[2]
PROFILES = ROOT / 'config' / 'search_profiles.json'


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Collect PubMed PMIDs and paper metadata using official NCBI E-utilities.')
    parser.add_argument('--email', default=os.getenv('PUBMED_EMAIL'),
                        help='Real contact email, or set PUBMED_EMAIL (required for network requests).')
    parser.add_argument('--api-key', default=os.getenv('NCBI_API_KEY'),
                        help='Optional NCBI API key; environment variable is safer.')
    parser.add_argument('--verbose', action='store_true')
    sub = parser.add_subparsers(dest='command', required=True)

    def add_search_options(target):
        target.add_argument('--profile', default='synthetic_biology',
                            choices=['synthetic_biology', 'agri_biotech',
                                     'biochip_robot_neuro', 'all'],
                            help='Predefined search topic from the original scripts.')
        target.add_argument('--query', action='append', default=[],
                            help='Custom PubMed boolean expression. Repeat for multiple topics. '
                                 'When provided, overrides --profile.')
        target.add_argument('--start-date', default='2012-01-01')
        target.add_argument('--end-date', default='2024-08-31')
        target.add_argument('--frequency', default='quarter', choices=['quarter','year'])
        target.add_argument('--max-pmids', type=int, default=None,
                            help='Stop after collecting this many distinct PMIDs (testing/preview).')
        target.add_argument('--pmids-out', type=Path, default=Path('results/pmids.json'))

    search = sub.add_parser('search', help='Collect distinct PubMed IDs to JSON.')
    add_search_options(search)
    fetch = sub.add_parser('fetch', help='Retrieve details from a saved PMID JSON file.')
    fetch.add_argument('--pmids-in', type=Path, default=Path('results/pmids.json'))
    fetch.add_argument('--output', type=Path, default=Path('results/pubmed_results.csv'))
    fetch.add_argument('--batch-size', type=int, default=200)
    fetch.add_argument('--resume', action='store_true',
                       help='Skip PMIDs already saved in existing CSV.')

    run = sub.add_parser('run', help='Search and fetch papers (complete pipeline).')
    add_search_options(run)
    run.add_argument('--output', type=Path, default=Path('results/pubmed_results.csv'))
    run.add_argument('--batch-size', type=int, default=200)
    run.add_argument('--resume', action='store_true',
                     help='Reuse existing pmids.json when available, then append missing details.')
    return parser.parse_args(argv)


def get_queries(args: argparse.Namespace) -> list[str]:
    if args.query:
        if any(not term.strip() for term in args.query):
            raise ValueError('--query cannot be blank')
        return args.query
    data = json.loads(PROFILES.read_text(encoding='utf-8'))
    profile_names = list(data) if args.profile == 'all' else [args.profile]
    return [expr for name in profile_names for expr in data[name]['queries']]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format='%(asctime)s %(levelname)s %(message)s')
    if not args.email:
        raise SystemExit('Set PUBMED_EMAIL or pass --email (NCBI identification policy).')
    client = PubMedClient(email=args.email, api_key=args.api_key)
    if args.command in ('search', 'run'):
        try:
            start = date.fromisoformat(args.start_date)
            end = date.fromisoformat(args.end_date)
        except ValueError as exc:
            raise SystemExit('Dates must be YYYY-MM-DD.') from exc
        if start > end:
            raise SystemExit('The start date must be <= the end date.')
        if args.max_pmids is not None and args.max_pmids < 1:
            raise SystemExit('--max-pmids must be > 0.')
        queries = get_queries(args)
        if args.command == 'run' and args.resume and args.pmids_out.exists():
            pmids = load_pmids(args.pmids_out)
            logging.info('Reusing %d PMIDs from %s', len(pmids), args.pmids_out)
        else:
            pmids = search_and_save(client, queries, start, end, args.frequency,
                                    args.pmids_out, args.max_pmids)
        if args.command == 'search':
            print(f'PMIDs: {len(pmids)} → {args.pmids_out}')
            return 0
    else:
        if not args.pmids_in.exists():
            raise SystemExit(f'No PMID list found: {args.pmids_in}; run search first.')
        pmids = load_pmids(args.pmids_in)
    added, total = fetch_and_save(client, pmids, args.output,
                                 batch_size=args.batch_size, resume=args.resume)
    print(f'Added records: {added} | Total in CSV: {total} → {args.output}')
    return 0
