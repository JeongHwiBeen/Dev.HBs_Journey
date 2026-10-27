"""Network transport unit tests: no external HTTP calls."""
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from pubmed_crawler.client import PubMedClient


class FakeResponse:
    def __init__(self, xml: bytes):
        self.xml = xml
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self):
        return self.xml


class ClientTests(unittest.TestCase):
    def test_short_search_uses_get_and_email_and_returns_ids(self):
        client = PubMedClient(email='test@example.com', request_interval=0)
        xml = b'<eSearchResult><Count>2</Count><IdList><Id>12</Id><Id>34</Id></IdList></eSearchResult>'
        with patch('pubmed_crawler.client.urlopen', return_value=FakeResponse(xml)) as request:
            count, ids = client.search('gene[tiab]', '2024-01-01', '2024-08-31')
        self.assertEqual((count, ids), (2,['12','34']))
        sent = request.call_args.args[0]
        self.assertIsNone(sent.data)
        self.assertIn('email=test%40example.com', sent.full_url)
        self.assertIn('datetype=pdat', sent.full_url)

    def test_long_search_uses_post(self):
        client = PubMedClient(email='test@example.com', request_interval=0)
        xml = b'<eSearchResult><Count>0</Count><IdList/></eSearchResult>'
        with patch('pubmed_crawler.client.urlopen', return_value=FakeResponse(xml)) as request:
            client.search(' OR '.join(['gene[tiab]']*300), '2024-01-01', '2024-08-31')
        sent = request.call_args.args[0]
        self.assertIsNotNone(sent.data)
        self.assertEqual(sent.full_url, 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi')

    def test_retries_http_429_then_succeeds(self):
        client = PubMedClient(email='test@example.com', request_interval=0, retries=1)
        exc = HTTPError('url', 429, 'Too many requests', {}, io.BytesIO(b''))
        xml = b'<eSearchResult><Count>0</Count><IdList/></eSearchResult>'
        with patch('pubmed_crawler.client.urlopen', side_effect=[exc, FakeResponse(xml)]) as request, \
             patch('pubmed_crawler.client.time.sleep'):
            count, ids = client.search('gene', '2024-01-01', '2024-08-31')
        self.assertEqual((count, ids), (0, []))
        self.assertEqual(request.call_count, 2)

    def test_permanent_http_400_does_not_retry(self):
        client = PubMedClient(email='test@example.com', request_interval=0, retries=3)
        exc = HTTPError('url', 400, 'Bad Request', {}, io.BytesIO(b''))
        with patch('pubmed_crawler.client.urlopen', side_effect=exc) as request:
            with self.assertRaisesRegex(RuntimeError, 'HTTP 400'):
                client.search('bad search', '2024-01-01','2024-08-31')
        self.assertEqual(request.call_count, 1)


if __name__ == '__main__':
    unittest.main()

class CommandIntegrationTests(unittest.TestCase):
    def test_run_command_saves_pmids_and_csv_using_fake_api(self):
        import csv
        import json
        import tempfile
        from pubmed_crawler import cli

        xml = b'''<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>13579</PMID>
        <Article><ArticleTitle>Offline Integration</ArticleTitle></Article></MedlineCitation>
        </PubmedArticle></PubmedArticleSet>'''

        class StubAPI:
            def __init__(self, *args, **kwargs):
                pass
            def search(self, term, start_date, end_date, retstart=0, retmax=200):
                return (1, ['13579'] if retstart == 0 else [])
            def fetch(self, pmids):
                from xml.etree import ElementTree as ET
                return ET.fromstring(xml)

        with tempfile.TemporaryDirectory() as directory, \
             patch('pubmed_crawler.cli.PubMedClient', StubAPI):
            pmids = Path(directory) / 'ids.json'
            csv_out = Path(directory) / 'out.csv'
            result = cli.main(['--email','test@example.com','run',
                               '--query','synthetic biology[tiab]',
                               '--start-date','2024-08-01',
                               '--end-date','2024-08-01',
                               '--pmids-out',str(pmids),
                               '--output',str(csv_out)])
            self.assertEqual(result, 0)
            self.assertEqual(json.loads(pmids.read_text()), ['13579'])
            with csv_out.open(encoding='utf-8-sig', newline='') as file:
                rows = list(csv.DictReader(file))
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]['Title'], 'Offline Integration')
