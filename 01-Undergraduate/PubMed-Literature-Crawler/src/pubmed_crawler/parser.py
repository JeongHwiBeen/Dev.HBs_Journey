"""Parse PubMed EFetch XML into columns used in the original three scripts."""
from __future__ import annotations
from xml.etree import ElementTree as ET

COLUMNS = ['PMID', 'Title', 'Authors', 'Affiliations', 'Journal',
           'Publication Date', 'Abstract', 'Keywords', 'URL', 'DOI']


def element_text(node: ET.Element | None) -> str:
    return ' '.join(' '.join(node.itertext()).split()) if node is not None else ''


def unique_in_order(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def parse_article(article: ET.Element) -> dict[str, str]:
    medline = article.find('./MedlineCitation')
    if medline is None:
        raise ValueError('PubmedArticle does not contain MedlineCitation')
    pmid = (medline.findtext('PMID') or '').strip()
    if not pmid:
        raise ValueError('PubMed record is missing a PMID')
    detail = medline.find('./Article')
    title = element_text(detail.find('ArticleTitle')) if detail is not None else ''
    authors = []
    affiliations = []
    if detail is not None:
        for author in detail.findall('./AuthorList/Author'):
            collective = element_text(author.find('CollectiveName'))
            last = element_text(author.find('LastName'))
            first = element_text(author.find('ForeName')) or element_text(author.find('Initials'))
            person = collective or ' '.join(part for part in [first, last] if part)
            if person:
                authors.append(person)
            affiliations.extend(element_text(aff) for aff in author.findall('./AffiliationInfo/Affiliation'))
    journal = element_text(detail.find('./Journal/Title')) if detail is not None else ''
    if not journal and detail is not None:
        journal = element_text(detail.find('./Journal/ISOAbbreviation'))
    pub_date = detail.find('./Journal/JournalIssue/PubDate') if detail is not None else None
    publication_date = ''
    if pub_date is not None:
        year, month, day = (element_text(pub_date.find(k)) for k in ['Year', 'Month', 'Day'])
        publication_date = '-'.join(v for v in (year, month, day) if v)
        publication_date = publication_date or element_text(pub_date.find('MedlineDate'))
    if not publication_date:
        history = article.find('./PubmedData/History/PubMedPubDate')
        if history is not None:
            publication_date = '-'.join(element_text(history.find(k)) for k in ['Year','Month','Day'])
    abstracts = []
    if detail is not None:
        for node in detail.findall('./Abstract/AbstractText'):
            prefix = node.attrib.get('Label', '').strip()
            content = element_text(node)
            if content:
                abstracts.append(f'{prefix}: {content}' if prefix else content)
    keywords = unique_in_order([element_text(node) for node in medline.findall('./KeywordList/Keyword')])
    doi = ''
    for node in article.findall('./PubmedData/ArticleIdList/ArticleId'):
        if node.attrib.get('IdType', '').lower() == 'doi':
            doi = element_text(node)
            break
    if not doi and detail is not None:
        for node in detail.findall('./ELocationID'):
            if node.attrib.get('EIdType', '').lower() == 'doi':
                doi = element_text(node)
                break
    return {
        'PMID': pmid,
        'Title': title,
        'Authors': ', '.join(unique_in_order(authors)),
        'Affiliations': '; '.join(unique_in_order(affiliations)),
        'Journal': journal,
        'Publication Date': publication_date,
        'Abstract': ' '.join(abstracts),
        'Keywords': '; '.join(keywords),
        'URL': f'https://pubmed.ncbi.nlm.nih.gov/{pmid}/',
        'DOI': doi,
    }


def parse_articles(root: ET.Element) -> list[dict[str, str]]:
    results = []
    for article in root.findall('./PubmedArticle'):
        results.append(parse_article(article))
    return results
