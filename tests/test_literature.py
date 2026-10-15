import json
from pathlib import Path
import tempfile
import unittest

from gene_literature import APIError, Client, build_query, fetch_papers, normalize, plain, render_html, resolve_gene


GENE = {"symbol": "FASN", "name": "fatty acid synthase", "hgnc_id": "HGNC:3594",
        "status": "Approved", "alias_symbol": ["FAS"], "prev_symbol": []}


class FakeClient:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def get(self, url, params=None):
        self.calls.append((url, params))
        return next(self.responses)


class LiteratureTests(unittest.TestCase):
    def test_approved_symbol_precedes_other_aliases(self):
        client = FakeClient([{"response": {"docs": [GENE]}}])
        self.assertEqual(resolve_gene(client, "fasn")["symbol"], "FASN")
        self.assertEqual(len(client.calls), 1)

    def test_ambiguous_alias_is_not_silently_selected(self):
        other = {**GENE, "symbol": "OTHER", "hgnc_id": "HGNC:999"}
        client = FakeClient([{"response": {"docs": []}},
                             {"response": {"docs": [GENE, other]}},
                             {"response": {"docs": []}}])
        with self.assertRaisesRegex(APIError, "Ambiguous"):
            resolve_gene(client, "FAS")

    def test_unknown_gene_and_query_injection(self):
        client = FakeClient([{"response": {"docs": []}}] * 3)
        with self.assertRaisesRegex(APIError, "No approved"):
            resolve_gene(client, "UNKNOWN")
        with self.assertRaises(APIError):
            resolve_gene(client, "FASN OR cancer")
        query = build_query(GENE, 'cancer" OR *')
        self.assertIn('TITLE_ABS:"cancer\\" OR *"', query)
        self.assertNotIn('TITLE_ABS:"FAS"', query)

    def test_user_entered_alias_is_kept_in_search(self):
        query = build_query({**GENE, "input_symbol": "FAS"})
        self.assertIn('TITLE_ABS:"FAS"', query)

    def test_deduplication_pagination_and_missing_abstract(self):
        a = {"source": "MED", "id": "1", "pmid": "1", "title": "FASN study"}
        b = {"source": "MED", "id": "2", "pmid": "2", "title": "Another FASN study"}
        client = FakeClient([
            {"hitCount": 2, "resultList": {"result": [a]}, "nextCursorMark": "next"},
            {"hitCount": 2, "resultList": {"result": [a, b]}, "nextCursorMark": "next"},
        ])
        total, papers = fetch_papers(client, "query", ["FASN"], 2)
        self.assertEqual((total, len(papers)), (2, 2))
        self.assertEqual(papers[0]["abstract"], "")
        self.assertEqual(papers[0]["gene_excerpt"], [])

    def test_gene_mention_is_not_a_causal_claim_or_substring_match(self):
        paper = normalize({"title": "FASN study", "abstractText": "<p>FASN was measured.</p> FASNX was not the gene."}, ["FASN"])
        self.assertEqual(paper["gene_excerpt"], ["FASN was measured."])
        self.assertEqual(paper["category"], "기타 논문")

    def test_review_and_retraction_labels(self):
        self.assertEqual(normalize({"pubTypeList": {"pubType": ["Review"]}}, ["FASN"])["category"], "리뷰")
        self.assertEqual(normalize({"pubTypeList": {"pubType": ["Retracted Publication", "Review"]}}, ["FASN"])["category"], "철회 관련")

    def test_html_escapes_remote_text(self):
        report = {"gene": GENE, "papers": [], "total_hits": 0, "sort": "recent",
                  "query": '<script>alert("x")</script>', "include_aliases": False, "created_at": "now"}
        output = render_html(report)
        self.assertNotIn('<script>', output)
        self.assertIn('&lt;script&gt;', output)
        self.assertEqual(plain('<p>Hello</p><p>world</p>'), "Hello world")

    def test_offline_cache_keeps_original_retrieval_time(self):
        import hashlib
        url = "https://example.org/"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            key = hashlib.sha256(url.encode()).hexdigest()
            (path / f"{key}.json").write_text(json.dumps({"retrieved_at": "2026-10-01", "data": {"ok": True}}))
            client = Client(path, offline=True)
            self.assertEqual(client.get(url), {"ok": True})
            self.assertEqual(client.sources[0]["retrieved_at"], "2026-10-01")
            with self.assertRaisesRegex(APIError, "No cached response"):
                client.get("https://example.org/uncached")


if __name__ == "__main__":
    unittest.main()
