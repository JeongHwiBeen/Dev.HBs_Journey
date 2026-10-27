"""Offline regression tests; they never call NCBI."""
from __future__ import annotations

from datetime import date
import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from pubmed_crawler.parser import COLUMNS, parse_articles
from pubmed_crawler.pipeline import fetch_and_save, load_pmids, save_pmids
from pubmed_crawler.search import collect_pmids, iter_slice_ids, periods
from pubmed_crawler.cli import get_queries, parse_args

SEARCH_XML = '''<PubmedArticleSet>
<PubmedArticle><MedlineCitation><PMID>12345</PMID><Article>
<ArticleTitle>A <i>synthetic</i> example</ArticleTitle>
<Journal><JournalIssue><PubDate><Year>2024</Year><Month>Aug</Month><Day>15</Day></PubDate></JournalIssue><Title>Example Journal</Title></Journal>
<AuthorList><Author><ForeName>Jane</ForeName><LastName>Doe</LastName>
<AffiliationInfo><Affiliation>Institute A</Affiliation></AffiliationInfo></Author></AuthorList>
<Abstract><AbstractText Label="BACKGROUND">Background with <b>bold</b> text.</AbstractText><AbstractText Label="METHODS">Method text.</AbstractText></Abstract>
<ELocationID EIdType="doi">10.1000/test</ELocationID></Article>
<KeywordList><Keyword>AI</Keyword><Keyword>PubMed</Keyword></KeywordList>
</MedlineCitation><PubmedData><ArticleIdList><ArticleId IdType="doi">10.1000/official</ArticleId></ArticleIdList></PubmedData></PubmedArticle>
<PubmedArticle><MedlineCitation><PMID>67890</PMID><Article><ArticleTitle>Untitled tests</ArticleTitle></Article></MedlineCitation></PubmedArticle>
</PubmedArticleSet>'''


class FakeClient:
    def __init__(self):
        self.requests = []
    def search(self, query, start_date, end_date, retstart=0, retmax=200):
        self.requests.append((query, start_date, end_date, retstart, retmax))
        return 3, ['11', '12', '13'][retstart:retstart+retmax]
    def fetch(self, pmids):
        return ET.fromstring(SEARCH_XML)


class Tests(unittest.TestCase):
    def test_quarter_boundaries_and_partial_end(self):
        spans = periods(date(2024, 1, 1), date(2024, 8, 31))
        self.assertEqual(spans, [(date(2024, 1, 1), date(2024, 3, 31)),
                                 (date(2024, 4, 1), date(2024, 6, 30)),
                                 (date(2024, 7, 1), date(2024, 8, 31))])

    def test_year_boundaries_and_invalid_dates(self):
        self.assertEqual(periods(date(2023, 11, 1), date(2024, 2, 2), 'year'), [
            (date(2023, 11, 1), date(2023, 12, 31)),
            (date(2024, 1, 1), date(2024, 2, 2))])
        with self.assertRaises(ValueError):
            periods(date(2024, 2, 1), date(2024, 1, 1))

    def test_search_pagination(self):
        client = FakeClient()
        self.assertEqual(list(iter_slice_ids(client, 'q', date(2024, 1, 1),
                                              date(2024, 1, 1), page_size=2)),
                         ['11', '12', '13'])
        self.assertEqual(len(client.requests), 2)

    def test_search_deduplicates_across_queries_and_periods(self):
        client = FakeClient()
        values = collect_pmids(client, ['q1', 'q2'], date(2024, 1, 1),
                               date(2024, 8, 31), page_size=2)
        self.assertEqual(values, ['11', '12', '13'])

    def test_date_splits_if_search_results_exceed_window(self):
        class Oversized(FakeClient):
            def search(self, q, first, last, retstart=0, retmax=200):
                if first != last:
                    return 12, ['unexpected']
                return (1, [first])
        result = list(iter_slice_ids(Oversized(), 'q', date(2024, 1, 1),
                                     date(2024, 1, 2), page_size=2, max_window=10))
        self.assertEqual(result, ['2024-01-01','2024-01-02'])

    def test_xml_metadata_parsing(self):
        rows = parse_articles(ET.fromstring(SEARCH_XML))
        self.assertEqual(len(rows), 2)
        self.assertEqual(list(rows[0]), COLUMNS)
        self.assertEqual(rows[0]['PMID'], '12345')
        self.assertEqual(rows[0]['Title'], 'A synthetic example')
        self.assertEqual(rows[0]['Authors'], 'Jane Doe')
        self.assertEqual(rows[0]['Journal'], 'Example Journal')
        self.assertEqual(rows[0]['Keywords'], 'AI; PubMed')
        self.assertEqual(rows[0]['DOI'], '10.1000/official')
        self.assertIn('BACKGROUND: Background with bold text.', rows[0]['Abstract'])
        self.assertEqual(rows[1]['DOI'], '')

    def test_resume_and_csv_column_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'papers.csv'
            client = FakeClient()
            count, total = fetch_and_save(client, ['12345','67890'], path)
            self.assertEqual((count, total), (2,2))
            count, total = fetch_and_save(client, ['12345','67890'], path, resume=True)
            self.assertEqual((count, total), (0,2))
            with path.open(encoding='utf-8-sig',newline='') as file:
                reader = csv.DictReader(file)
                self.assertEqual(reader.fieldnames, COLUMNS)
                self.assertEqual(len(list(reader)), 2)

    def test_missing_records_do_not_silently_succeed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RuntimeError, 'omitted PMIDs'):
                fetch_and_save(FakeClient(), ['12345','99999'], Path(tmp)/'articles.csv')

    def test_pmids_checkpoint_dedup(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)/'pmids.json'
            save_pmids(['42','42','43'],target)
            self.assertEqual(load_pmids(target), ['42','43'])

    def test_queries_preserved_and_cli_override(self):
        opts = parse_args(['run','--profile','all'])
        queries = get_queries(opts)
        self.assertEqual(len(queries), 5)
        self.assertTrue(any('artificial cell*' in x for x in queries))
        self.assertTrue(any('agriculture*' in x for x in queries))
        self.assertTrue(any('robot*' in x for x in queries))
        opts = parse_args(['search','--query','cancer[tiab]'])
        self.assertEqual(get_queries(opts), ['cancer[tiab]'])


if __name__ == '__main__':
    unittest.main()
