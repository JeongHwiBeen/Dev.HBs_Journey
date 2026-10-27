"""NCBI E-utilities client with bounded retries and shared rate-limiting."""
from __future__ import annotations

import logging
import os
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

LOG = logging.getLogger(__name__)
BASE_URL = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils'
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class PubMedClient:
    def __init__(self, email: str, api_key: str | None = None, timeout: float = 30,
                 retries: int = 4, request_interval: float | None = None):
        if not email or '@' not in email:
            raise ValueError('Provide a real contact email with --email or PUBMED_EMAIL.')
        if retries < 0:
            raise ValueError('retries must be >= 0')
        self.email = email
        self.api_key = api_key or os.getenv('NCBI_API_KEY')
        self.timeout = timeout
        self.retries = retries
        self.request_interval = request_interval if request_interval is not None else (
            0.12 if self.api_key else 0.40
        )
        self._lock = threading.Lock()
        self._next_request_time = 0.0

    def _throttle(self) -> None:
        with self._lock:
            now = time.monotonic()
            remaining = self._next_request_time - now
            if remaining > 0:
                time.sleep(remaining)
            self._next_request_time = time.monotonic() + self.request_interval

    def request_xml(self, endpoint: str, params: dict[str, object]) -> ET.Element:
        if endpoint not in {'esearch.fcgi', 'efetch.fcgi'}:
            raise ValueError('Unsupported E-utilities endpoint.')
        request_params = {
            **params,
            'db': 'pubmed',
            'retmode': 'xml',
            'tool': 'PubMedLiteratureCrawler',
            'email': self.email,
        }
        if self.api_key:
            request_params['api_key'] = self.api_key
        payload = urlencode(request_params).encode('utf-8')
        url = f'{BASE_URL}/{endpoint}'
        # POST prevents very long boolean search queries from overflowing URL limits.
        use_post = len(payload) > 1700 or endpoint == 'efetch.fcgi'
        for attempt in range(self.retries + 1):
            self._throttle()
            request = Request(
                url if use_post else url + '?' + payload.decode('ascii'),
                data=payload if use_post else None,
                headers={'User-Agent': f'PubMedLiteratureCrawler/1.0 (mailto:{self.email})',
                         'Accept': 'application/xml'},
            )
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    xml = response.read()
                root = ET.fromstring(xml)
                # NCBI can return API-level errors in HTTP 200 XML.
                if root.tag == 'eSearchResult':
                    errs = [el.text for el in root.findall('ERROR') if el.text]
                    if errs:
                        raise RuntimeError(f'NCBI ESearch error: {"; ".join(errs)}')
                return root
            except HTTPError as exc:
                if exc.code not in RETRYABLE_STATUS or attempt == self.retries:
                    raise RuntimeError(f'NCBI HTTP {exc.code} at {endpoint}') from exc
                delay = min(30.0, 2 ** attempt)
                LOG.warning('HTTP %d; retry in %.1fs (%d/%d)', exc.code, delay,
                            attempt + 1, self.retries)
            except (URLError, TimeoutError, ConnectionError) as exc:
                if attempt == self.retries:
                    raise RuntimeError(f'Unable to fetch {endpoint}: {exc}') from exc
                delay = min(30.0, 2 ** attempt)
                LOG.warning('Network error; retry in %.1fs (%d/%d): %s',
                            delay, attempt + 1, self.retries, exc)
            except ET.ParseError as exc:
                raise RuntimeError(f'Invalid XML returned by {endpoint}') from exc
            time.sleep(delay)
        raise RuntimeError('Unreachable retry state')

    def search(self, query: str, start_date: str, end_date: str,
               retstart: int = 0, retmax: int = 200) -> tuple[int, list[str]]:
        root = self.request_xml('esearch.fcgi', {
            'term': query, 'datetype': 'pdat', 'mindate': start_date,
            'maxdate': end_date, 'retstart': retstart, 'retmax': retmax,
        })
        count_text = root.findtext('Count')
        if count_text is None:
            raise RuntimeError('Missing Count in ESearch XML')
        ids = [(x.text or '').strip() for x in root.findall('IdList/Id')]
        return int(count_text), [x for x in ids if x]

    def fetch(self, pmids: list[str]) -> ET.Element:
        if not pmids:
            raise ValueError('At least one PMID is required')
        return self.request_xml('efetch.fcgi', {'id': ','.join(pmids)})
