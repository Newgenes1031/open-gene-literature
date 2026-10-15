"""Human gene literature explorer, using HGNC and Europe PMC public APIs."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
from urllib.parse import quote
import webbrowser

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

VERSION = "0.2.0"
ROOT = Path(__file__).resolve().parent


class APIError(ValueError):
    pass


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)

    def handle_starttag(self, tag, attrs):
        if tag in {"p", "br", "div", "h4"}:
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in {"p", "div", "h4"}:
            self.parts.append(" ")


def plain(value):
    parser = PlainText()
    parser.feed(value or "")
    return re.sub(r"\s+", " ", "".join(parser.parts)).strip()


class Client:
    def __init__(self, cache: Path, offline=False):
        self.cache, self.offline = cache, offline
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": f"OpenGeneLiterature/{VERSION}",
                                     "Accept": "application/json"})
        retry = Retry(total=2, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504],
                      allowed_methods=["GET"], respect_retry_after_header=True)
        self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self.sources = []

    def get(self, url, params=None):
        prepared = requests.Request("GET", url, params=params).prepare().url
        key = hashlib.sha256(prepared.encode()).hexdigest()
        path = self.cache / f"{key}.json"
        if path.exists():
            record = json.loads(path.read_text())
            self.sources.append({"url": prepared, "retrieved_at": record["retrieved_at"],
                                 "cached": True})
            return record["data"]
        if self.offline:
            raise APIError(f"No cached response for {prepared}; run online once first.")
        try:
            response = self.session.get(url, params=params, timeout=(10, 45))
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise APIError(f"API request failed: {prepared}: {exc}") from exc
        record = {"retrieved_at": datetime.now(timezone.utc).isoformat(), "data": data}
        self.cache.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        self.sources.append({"url": prepared, "retrieved_at": record["retrieved_at"],
                             "cached": False})
        return data


def resolve_gene(client, term):
    term = term.strip().upper()
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9_.-]{0,59}", term):
        raise APIError("Enter a human gene symbol or alias, for example TP53 or p53.")
    base = "https://rest.genenames.org/fetch"
    # An approved symbol takes precedence over aliases belonging to other genes.
    for fields in [("symbol",), ("alias_symbol", "prev_symbol")]:
        candidates = {}
        for field in fields:
            docs = client.get(f"{base}/{field}/{quote(term, safe='')}")["response"]["docs"]
            for doc in docs:
                if doc.get("status") == "Approved":
                    candidates[doc["hgnc_id"]] = doc
        if len(candidates) > 1:
            symbols = ", ".join(sorted(doc["symbol"] for doc in candidates.values()))
            raise APIError(f"Ambiguous alias {term}: {symbols}. Enter an approved symbol.")
        if candidates:
            doc = next(iter(candidates.values()))
            gene = {key: doc.get(key, [] if key.endswith("symbol") and key != "symbol" else "")
                    for key in ["symbol", "name", "hgnc_id", "alias_symbol", "prev_symbol",
                                "ensembl_gene_id", "entrez_id"]}
            gene["input_symbol"] = term
            return gene
    raise APIError(f"No approved human HGNC gene found for {term}.")


def quoted(value):
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def search_terms(gene, include_aliases=False):
    # Broad aliases are opt-in: short gene symbols are often ordinary words.
    terms = [gene["symbol"], gene["name"]]
    # The alias explicitly entered by the user remains in the search, e.g. p53.
    if gene.get("input_symbol") and gene["input_symbol"] != gene["symbol"]:
        terms.append(gene["input_symbol"])
    if include_aliases:
        terms += sorted(set(gene["alias_symbol"] + gene["prev_symbol"]))
    return list(dict.fromkeys(t for t in terms if t and (t == gene["symbol"] or len(t) >= 3)))


def build_query(gene, context="", sort="relevance", include_aliases=False):
    terms = search_terms(gene, include_aliases)
    if gene["symbol"] not in terms:
        terms.insert(0, gene["symbol"])
    # A short/common symbol also needs a molecular context in the title/abstract.
    clauses = []
    for term in terms:
        clause = f"TITLE_ABS:{quoted(term)}"
        if len(term) <= 3:
            clause = f"({clause} AND (TITLE_ABS:gene OR TITLE_ABS:protein OR TITLE_ABS:transcription))"
        clauses.append(clause)
    query = "SRC:MED AND (" + " OR ".join(clauses) + ")"
    if context.strip():
        query += f" AND TITLE_ABS:{quoted(context.strip())}"
    if sort != "relevance":
        query += " " + {"recent": "sort_date:y", "cited": "sort_cited:y"}[sort]
    return query


def term_pattern(terms):
    return re.compile(r"(?<![A-Za-z0-9])(?:" + "|".join(re.escape(t) for t in terms)
                      + r")(?![A-Za-z0-9])", re.I)


def classify(record):
    types = [str(v) for v in record.get("pubTypeList", {}).get("pubType", [])]
    if any("retract" in v.lower() for v in types):
        return "철회 관련", types
    if any("review" in v.lower() for v in types):
        return "리뷰", types
    if any("trial" in v.lower() for v in types):
        return "임상시험", types
    return "기타 논문", types


def normalize(record, terms):
    abstract = plain(record.get("abstractText", ""))
    title = plain(record.get("title", ""))
    pattern = term_pattern(terms)
    sentences = re.split(r"(?<=[.!?])\s+", abstract)
    excerpts = [s for s in sentences if pattern.search(s)][:2]
    matched = [t for t in terms if term_pattern([t]).search(title + " " + abstract)]
    category, types = classify(record)
    pmid, doi = record.get("pmid", ""), record.get("doi", "")
    journal = record.get("journalInfo", {}).get("journal", {}).get("title", "")
    source, identifier = record.get("source", "MED"), record.get("id", "")
    return {
        "title": title, "authors": record.get("authorString", ""),
        "year": record.get("pubYear", ""), "date": record.get("firstPublicationDate", ""),
        "journal": journal, "pmid": pmid, "doi": doi, "category": category,
        "publication_types": types, "cited_by_count": int(record.get("citedByCount") or 0),
        "open_access": record.get("isOpenAccess") == "Y", "matched_terms": matched,
        "gene_excerpt": excerpts, "abstract": abstract,
        "match_note": "제목·초록의 문자열 일치" if matched else "검색 색인에서 일치; 제목·초록 직접 확인 필요",
        "url": f"https://europepmc.org/article/{quote(source, safe='')}/{quote(identifier, safe='')}",
        "pubmed_url": f"https://pubmed.ncbi.nlm.nih.gov/{quote(pmid, safe='')}/" if pmid else "",
        "doi_url": "https://doi.org/" + quote(doi, safe="/") if doi else "",
    }


def fetch_papers(client, query, terms, limit):
    papers, seen, cursor, cursors = [], set(), "*", set()
    total = None
    while len(papers) < limit and cursor and cursor not in cursors:
        cursors.add(cursor)
        data = client.get("https://www.ebi.ac.uk/europepmc/webservices/rest/search",
                          {"query": query, "format": "json", "resultType": "core",
                           "pageSize": min(100, limit - len(papers)), "cursorMark": cursor})
        if "errCode" in data or "resultList" not in data:
            raise APIError(f"Europe PMC returned an invalid search response: {data.get('errMsg', data)}")
        total = int(data.get("hitCount", 0))
        records = data["resultList"].get("result", [])
        for record in records:
            key = (record.get("source"), record.get("id"))
            if key not in seen:
                seen.add(key)
                papers.append(normalize(record, terms))
        cursor = data.get("nextCursorMark")
        if not records:
            break
    return total or 0, papers[:limit]


def render_html(report):
    esc = lambda v: html.escape(str(v), quote=True)
    gene = report["gene"]
    cards = []
    for index, p in enumerate(report["papers"], 1):
        links = [f'<a href="{esc(p["url"])}" target="_blank" rel="noopener">Europe PMC</a>']
        if p["pubmed_url"]:
            links.append(f'<a href="{esc(p["pubmed_url"])}" target="_blank" rel="noopener">PMID {esc(p["pmid"])}</a>')
        if p["doi_url"]:
            links.append(f'<a href="{esc(p["doi_url"])}" target="_blank" rel="noopener">DOI</a>')
        excerpts = "".join(f"<blockquote>{esc(s)}</blockquote>" for s in p["gene_excerpt"])
        cards.append(f'''<article><span class="badge">{esc(p['category'])}</span>
<h2>{index}. {esc(p['title'])}</h2><p>{esc(p['authors'])}</p>
<p>{esc(p['journal'])} · {esc(p['year'])} · 인용 {p['cited_by_count']}회 (Europe PMC)</p>
<p>{' · '.join(links)}</p><p class="muted">{esc(p['match_note'])} · 일치한 이름: {esc(', '.join(p['matched_terms']))}</p>
{excerpts}<details><summary>원문 초록</summary><p>{esc(p['abstract']) or '초록이 제공되지 않았습니다.'}</p></details></article>''')
    return f'''<!doctype html><html lang="ko"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(gene['symbol'])} · Open Gene Literature</title>
<style>body{{margin:0;background:#f4f7fa;color:#172d3e;font:16px/1.7 -apple-system,BlinkMacSystemFont,sans-serif}}
main{{max-width:1000px;margin:40px auto;padding:0 24px}}h1{{font-size:40px;margin:0}}h2{{font-size:20px;line-height:1.5}}
header,article,section{{background:white;border:1px solid #d8e3e9;border-radius:14px;padding:26px;margin:18px 0}}
a{{color:#086a7b}}.muted{{color:#576d7c;font-size:14px}}.badge{{background:#def3ef;padding:4px 10px;border-radius:6px}}
blockquote{{border-left:3px solid #138a89;margin:18px 0;padding:8px 18px;background:#f0f8f7}}
code{{overflow-wrap:anywhere}}details{{margin-top:16px}}summary{{cursor:pointer}}</style>
<main><header><p class="muted">OPEN GENE LITERATURE · HUMAN GENE</p><h1>{esc(gene['symbol'])}</h1>
<p>{esc(gene['name'])} · {esc(gene['hgnc_id'])}</p>
<p>검색 결과 {report['total_hits']:,}건 중 {len(report['papers'])}건 · 정렬: {esc(report['sort'])}</p>
<p class="muted">유전자명과 일치하는 논문을 찾아 정리했습니다. 회색 설명과 인용문은 자동 검색 결과이며 인과관계 판정이 아닙니다.
HGNC는 사람 유전자 기준입니다. 검색 논문의 실험 종은 혼합될 수 있습니다. 초록 발췌문은 원문 그대로입니다.</p></header>
<section><details><summary>검색 조건과 출처</summary><p>{esc(report['created_at'])}</p><code>{esc(report['query'])}</code>
<p>HGNC · Europe PMC (PubMed indexed records). 인용 수는 Europe PMC 기준이며 Web of Science와 다릅니다.</p>
<p>별칭 확장: {esc(report['include_aliases'])}. 일부 유전자명은 일반 단어와 겹치므로 개별 논문을 확인하세요.</p></details></section>
{''.join(cards) or '<section>검색 조건에 맞는 논문이 없습니다.</section>'}</main></html>'''


def save_report(report, output):
    output.mkdir(parents=True, exist_ok=True)
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "report.html").write_text(render_html(report), encoding="utf-8")
    columns = ["title", "year", "journal", "category", "pmid", "doi", "cited_by_count", "url"]
    with (output / "papers.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        # Avoid spreadsheet formula interpretation in bibliographic text.
        for paper in report["papers"]:
            writer.writerow({k: ("'" + v if isinstance(v, str) and v.startswith(("=", "+", "-", "@")) else v)
                             for k, v in paper.items() if k in columns})


def search_literature(term, *, context="", sort="relevance", limit=30,
                      include_aliases=False, cache=None, offline=False,
                      progress=None):
    """Shared CLI/GUI search; no UI calls and no report writes."""
    if not 1 <= limit <= 300:
        raise APIError("논문 수는 1~300 사이로 입력하세요.")
    if sort not in {"relevance", "recent", "cited"}:
        raise APIError("알 수 없는 정렬 방식입니다.")
    notify = progress or (lambda message: None)
    client = Client(Path(cache) if cache is not None else ROOT / ".cache", offline)
    try:
        notify("유전자 이름 확인 중…")
        gene = resolve_gene(client, term)
        query = build_query(gene, context, sort, include_aliases)
        notify(f"{gene['symbol']} 관련 논문 검색 중…")
        total, papers = fetch_papers(client, query, search_terms(gene, include_aliases), limit)
        return {"version": VERSION, "created_at": datetime.now(timezone.utc).isoformat(),
                "gene": gene, "input": term, "query": query, "context": context,
                "sort": sort, "include_aliases": include_aliases,
                "total_hits": total, "papers": papers, "sources": client.sources}
    finally:
        client.session.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="유전자명으로 실제 논문과 근거 초록을 정리합니다 (사람 HGNC 기준).")
    parser.add_argument("gene", help="TP53, FASN, STAT3 또는 HGNC 별칭")
    parser.add_argument("--context", default="", help="제목·초록에서 함께 찾을 구문, 예: colorectal cancer")
    parser.add_argument("--sort", choices=["relevance", "recent", "cited"], default="relevance")
    parser.add_argument("--limit", type=int, default=30, help="가져올 논문 수 (1–300)")
    parser.add_argument("--include-aliases", action="store_true")
    parser.add_argument("--cache", type=Path, default=ROOT / ".cache")
    parser.add_argument("--offline", action="store_true", help="이미 받은 응답만 사용")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--open", action="store_true", help="완성된 보고서를 브라우저에서 열기")
    args = parser.parse_args(argv)
    if not 1 <= args.limit <= 300:
        parser.error("--limit must be between 1 and 300")
    try:
        report = search_literature(args.gene, context=args.context, sort=args.sort,
                                   limit=args.limit, include_aliases=args.include_aliases,
                                   cache=args.cache, offline=args.offline)
        gene = report["gene"]
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        output = args.output or ROOT / "reports" / f"{gene['symbol']}-{stamp}"
        save_report(report, output)
    except (APIError, OSError, KeyError, ValueError) as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1
    print(f"{gene['symbol']} ({gene['name']}) · {report['total_hits']:,}건 중 {len(report['papers'])}건 저장")
    print((output / "report.html").resolve())
    if args.open:
        webbrowser.open((output / "report.html").resolve().as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
