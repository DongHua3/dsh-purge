#!/usr/bin/env python3
"""litsearch — real literature retrieval and reference verification.

Two jobs:

  1. SEARCH real bibliographic databases (OpenAlex, Crossref, PubMed, Europe PMC,
     arXiv, DOAJ) and save structured records.
  2. VERIFY that every reference in a manuscript actually exists and that its
     metadata is correct. Anything that cannot be verified is reported as
     UNVERIFIED and must not be cited.

    python litsearch.py search  --query "..." [--source ...] [--limit N]
    python litsearch.py doi     10.1126/sciadv.adt3813
    python litsearch.py verify  --refs manuscript/references.md [--out refs/verify.json]
    python litsearch.py retract --refs manuscript/references.md
    python litsearch.py cited-by --doi 10.1126/sciadv.adt3813
    python litsearch.py export  --in refs/search.json --style ris|bibtex|csv

Nothing is ever invented. If a lookup fails, the entry is reported as
unresolved - never filled in with a plausible-looking guess.

Requests + standard library only.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import time
import unicodedata
from difflib import SequenceMatcher

try:
    import requests
except ImportError:  # pragma: no cover
    print("litsearch needs `requests`: pip install requests", file=sys.stderr)
    raise SystemExit(1)

MAILTO = os.environ.get("LITSEARCH_MAILTO", "paper-pipeline@example.org")
UA = f"paper-pipeline/1.0 (mailto:{MAILTO})"
HDR = {"User-Agent": UA, "Accept": "application/json"}
TIMEOUT = 30
CACHE_DIR = os.path.expanduser(os.environ.get("LITSEARCH_CACHE", "~/.cache/litsearch"))
RW_URL = "https://api.labs.crossref.org/data/retractionwatch"

# Be polite: OpenAlex and Crossref both ask for a modest request rate.
_MIN_INTERVAL = 0.34
_last_call = [0.0]


def _utf8() -> None:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:
            pass


def _get(url: str, params: dict | None = None, tries: int = 3):
    """GET with rate limiting and bounded retries. Returns (json|text, err)."""
    for attempt in range(tries):
        wait = _MIN_INTERVAL - (time.time() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        try:
            r = requests.get(url, params=params or {}, headers=HDR, timeout=TIMEOUT)
            _last_call[0] = time.time()
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(2 ** attempt)
                continue
            if r.status_code == 404:
                return None, "not_found"
            r.raise_for_status()
            ct = r.headers.get("content-type", "")
            return (r.json() if "json" in ct else r.text), None
        except Exception as e:  # noqa: BLE001
            if attempt == tries - 1:
                return None, f"{type(e).__name__}: {e}"
            time.sleep(1.5 * (attempt + 1))
    return None, "rate_limited"


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def norm(s: str) -> str:
    """Normalise a title for comparison."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r"<[^>]+>", " ", s)              # strip JATS markup
    s = re.sub(r"[^a-z0-9\u4e00-\u9fff ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def sim(a: str, b: str) -> float:
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


_INITIALS = re.compile(r"^[A-Z](?:[.\-]?[A-Z])*\.?$")


def first_surname(authors: str) -> str:
    """Best-effort first-author surname out of a free-text author field.

    Handles every convention that actually shows up:

        "Smith, J."       surname first, comma separated
        "Smith J"         surname first, initials after
        "Bently DE"       surname first, multi-letter initials  <-- common
        "Den Hartog JP"   multi-word surname, initials after
        "Jang J-SR"       hyphenated initials
        "J. Smith"        given first
        "Dmitry Kobak"    given first, no initials (OpenAlex display name)

    The rule that makes this work: a trailing token made only of capital
    letters and separators is an initials group, not a surname.
    """
    if not authors:
        return ""
    first = re.split(r";|,| and |&", authors.strip())[0].strip()
    first = re.sub(r"\bet al\.?$", "", first, flags=re.I).strip()
    # my own parser can leave a trailing "(" from "(2024)"
    first = first.strip(" ().,;:")
    if not first:
        return ""
    # "Smith, J." - unambiguous
    if "," in authors.split(" and ")[0] and re.match(r"^[^,]+,\s*[A-Z]\.?", first):
        return norm(first.split(",")[0])

    parts = [p for p in first.split() if p not in ("(", ")", "&")]
    if not parts:
        return ""
    # drop trailing initials groups ("Bently DE" -> surname is "Bently";
    # "Den Hartog JP" -> surname is "Den Hartog")
    while len(parts) > 1 and _INITIALS.match(parts[-1]):
        parts.pop()
    return norm(" ".join(parts))


def rec_family(rec: dict) -> str:
    """First-author family name, using the structured field when available.

    Crossref gives `family` explicitly, so it is authoritative. OpenAlex only
    gives a display name, in "Given Family" order.
    """
    fam = rec.get("first_family")
    if fam:
        return norm(fam)
    src = rec.get("source", "")
    authors = rec.get("authors", "")
    if not authors:
        return ""
    first = authors.split(";")[0].strip()
    if src == "crossref":
        # we stored it as "Family Given"
        parts = first.split()
        return norm(parts[0]) if parts else ""
    # openalex / pubmed / arxiv / doaj: "Given ... Family"
    parts = first.split()
    return norm(parts[-1]) if parts else ""


def year_of(v) -> str:
    if v is None:
        return ""
    if isinstance(v, int):
        return str(v)
    if isinstance(v, (list, tuple)) and v:
        return year_of(v[0])
    if isinstance(v, dict):
        for k in ("date-parts", "value", "year"):
            if k in v:
                return year_of(v[k])
    m = re.search(r"(1[6-9]\d\d|20\d\d)", str(v))
    return m.group(1) if m else ""


# --------------------------------------------------------------------------
# source adapters: each returns a list of normalised records
# --------------------------------------------------------------------------
def _rec(**kw) -> dict:
    base = {"doi": "", "title": "", "authors": "", "year": "", "journal": "",
            "volume": "", "issue": "", "pages": "", "type": "", "source": "",
            "url": "", "abstract": "", "cited_by": None}
    base.update({k: v for k, v in kw.items() if v is not None})
    return base


def src_openalex(query: str, limit: int, **kw) -> list[dict]:
    p = {"search": query, "per-page": min(limit, 200), "mailto": MAILTO}
    if kw.get("year_from"):
        p["filter"] = f"from_publication_date:{kw['year_from']}-01-01"
    d, err = _get("https://api.openalex.org/works", p)
    if err or not d:
        return []
    out = []
    for w in d.get("results", []):
        au = w.get("authorships") or []
        names = "; ".join((a.get("author") or {}).get("display_name", "")
                          for a in au[:8] if (a.get("author") or {}).get("display_name"))
        loc = (w.get("primary_location") or {}).get("source") or {}
        bib = w.get("biblio") or {}
        out.append(_rec(
            doi=(w.get("doi") or "").replace("https://doi.org/", ""),
            title=w.get("title") or "", authors=names,
            year=year_of(w.get("publication_year")),
            journal=loc.get("display_name") or "",
            volume=bib.get("volume") or "", issue=bib.get("issue") or "",
            pages=((bib.get("first_page") or "") +
                   (("-" + bib["last_page"]) if bib.get("last_page") else "")),
            type=w.get("type") or "", source="openalex",
            url=w.get("id") or "", abstract=_openalex_abstract(w),
            cited_by=w.get("cited_by_count")))
    return out


def _openalex_abstract(w: dict) -> str:
    inv = w.get("abstract_inverted_index")
    if not inv:
        return ""
    pos: dict[int, str] = {}
    for word, idxs in inv.items():
        for i in idxs:
            pos[i] = word
    return " ".join(pos[i] for i in sorted(pos))[:2000]


def src_crossref(query: str, limit: int, **kw) -> list[dict]:
    p = {"query.bibliographic": query, "rows": min(limit, 100),
         "mailto": MAILTO, "select": ("DOI,title,author,issued,container-title,"
                                      "volume,issue,page,type,URL,abstract,"
                                      "is-referenced-by-count")}
    if kw.get("year_from"):
        p["filter"] = f"from-pub-date:{kw['year_from']}-01-01"
    d, err = _get("https://api.crossref.org/works", p)
    if err or not d:
        return []
    out = []
    for w in (d.get("message") or {}).get("items", []):
        au = w.get("author") or []
        names = "; ".join(
            f"{a.get('family','')} {a.get('given','')}".strip()
            for a in au[:8] if a.get("family") or a.get("given"))
        fam0 = (au[0].get("family") or "") if au else ""
        t = w.get("title") or []
        j = w.get("container-title") or []
        out.append(_rec(
            doi=w.get("DOI") or "", title=(t[0] if t else ""), authors=names,
            first_family=fam0,
            year=year_of(w.get("issued")), journal=(j[0] if j else ""),
            volume=w.get("volume") or "", issue=w.get("issue") or "",
            pages=w.get("page") or "", type=w.get("type") or "",
            source="crossref", url=w.get("URL") or "",
            abstract=re.sub(r"<[^>]+>", " ", w.get("abstract") or "")[:2000],
            cited_by=w.get("is-referenced-by-count")))
    return out


def src_pubmed(query: str, limit: int, **kw) -> list[dict]:
    d, err = _get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
                  {"db": "pubmed", "term": query, "retmode": "json",
                   "retmax": min(limit, 100), "sort": "relevance"})
    if err or not d:
        return []
    ids = (d.get("esearchresult") or {}).get("idlist") or []
    if not ids:
        return []
    s, err = _get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
                  {"db": "pubmed", "id": ",".join(ids), "retmode": "json"})
    if err or not s:
        return []
    out = []
    for pid in ids:
        w = (s.get("result") or {}).get(pid) or {}
        if not w:
            continue
        ids2 = {x.get("idtype"): x.get("value") for x in (w.get("articleids") or [])}
        out.append(_rec(
            doi=ids2.get("doi", ""), title=w.get("title", "").rstrip("."),
            authors="; ".join(a.get("name", "") for a in (w.get("authors") or [])[:8]),
            year=year_of(w.get("pubdate")), journal=w.get("fulljournalname", ""),
            volume=w.get("volume", ""), issue=w.get("issue", ""),
            pages=w.get("pages", ""), type="journal-article", source="pubmed",
            url=f"https://pubmed.ncbi.nlm.nih.gov/{pid}/"))
    return out


def src_europepmc(query: str, limit: int, **kw) -> list[dict]:
    d, err = _get("https://www.ebi.ac.uk/europepmc/webservices/rest/search",
                  {"query": query, "format": "json", "pageSize": min(limit, 100),
                   "resultType": "core"})
    if err or not d:
        return []
    out = []
    for w in (d.get("resultList") or {}).get("result", []):
        out.append(_rec(
            doi=w.get("doi", ""), title=w.get("title", "").rstrip("."),
            authors=w.get("authorString", ""), year=year_of(w.get("pubYear")),
            journal=w.get("journalInfo", {}).get("journal", {}).get("title", "")
            if isinstance(w.get("journalInfo"), dict) else w.get("journalTitle", ""),
            volume=w.get("journalInfo", {}).get("volume", "")
            if isinstance(w.get("journalInfo"), dict) else "",
            pages=w.get("pageInfo", ""), type=w.get("pubType", ""),
            source="europepmc",
            url=f"https://europepmc.org/article/{w.get('source','')}/{w.get('id','')}"))
    return out


def src_arxiv(query: str, limit: int, **kw) -> list[dict]:
    t, err = _get("http://export.arxiv.org/api/query",
                  {"search_query": f"all:{query}", "max_results": min(limit, 100)})
    if err or not t or not isinstance(t, str):
        return []
    out = []
    for entry in re.findall(r"<entry>(.*?)</entry>", t, re.S)[:limit]:
        def tag(name, blk=entry):
            m = re.search(rf"<{name}[^>]*>(.*?)</{name}>", blk, re.S)
            return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""
        authors = "; ".join(re.findall(r"<name>(.*?)</name>", entry))
        out.append(_rec(
            doi=tag("arxiv:doi") or "",
            title=tag("title"), authors=authors, year=year_of(tag("published")),
            journal="arXiv preprint", type="preprint", source="arxiv",
            url=tag("id")))
    return out


def src_doaj(query: str, limit: int, **kw) -> list[dict]:
    import urllib.parse
    d, err = _get("https://doaj.org/api/search/articles/"
                  + urllib.parse.quote(query), {"pageSize": min(limit, 100)})
    if err or not d:
        return []
    out = []
    for w in d.get("results", []):
        b = w.get("bibjson") or {}
        ids = {x.get("type"): x.get("id") for x in (b.get("identifier") or [])}
        j = b.get("journal") or {}
        out.append(_rec(
            doi=ids.get("doi", ""), title=b.get("title", ""),
            authors="; ".join(a.get("name", "") for a in (b.get("author") or [])[:8]),
            year=year_of(b.get("year")), journal=j.get("title", ""),
            volume=b.get("volume", ""), issue=(b.get("number") or ""),
            pages=b.get("start_page", "") or "", type="journal-article",
            source="doaj", url=(b.get("link") or [{}])[0].get("url", "")))
    return out


SOURCES = {
    "openalex": src_openalex,
    "crossref": src_crossref,
    "pubmed": src_pubmed,
    "europepmc": src_europepmc,
    "arxiv": src_arxiv,
    "doaj": src_doaj,
}
# Semantic Scholar is deliberately absent: it returns HTTP 429 without an API
# key. Set LITSEARCH_S2_KEY and add it back if you have one.


def dedupe(records: list[dict]) -> list[dict]:
    """Merge records across sources; a shared DOI is the strongest key."""
    by_doi: dict[str, dict] = {}
    by_title: dict[str, dict] = {}
    out = []
    for r in records:
        key = r.get("doi", "").lower()
        tk = norm(r.get("title", ""))[:120]
        hit = by_doi.get(key) if key else None
        if hit is None and tk:
            hit = by_title.get(tk)
        if hit is not None:
            for f in ("doi", "journal", "volume", "issue", "pages", "abstract",
                      "authors", "year"):
                if not hit.get(f) and r.get(f):
                    hit[f] = r[f]
            if hit.get("cited_by") is None and r.get("cited_by") is not None:
                hit["cited_by"] = r["cited_by"]
            srcs = hit.setdefault("also_in", [])
            if r["source"] not in srcs:
                srcs.append(r["source"])
            continue
        out.append(r)
        if key:
            by_doi[key] = r
        if tk:
            by_title[tk] = r
    return out


# --------------------------------------------------------------------------
# Retraction Watch (Crossref Labs) - 66 MB CSV, downloaded once and cached
# --------------------------------------------------------------------------
def _rw_path() -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, "retractionwatch.csv")


def ensure_retraction_data(force: bool = False) -> tuple[str | None, str]:
    p = _rw_path()
    if os.path.isfile(p) and not force and os.path.getsize(p) > 1_000_000:
        age_days = (time.time() - os.path.getmtime(p)) / 86400
        return p, f"cached ({os.path.getsize(p) / 1e6:.0f} MB, {age_days:.0f} days old)"
    try:
        r = requests.get(RW_URL, headers={"User-Agent": UA},
                         timeout=300, stream=True)
        r.raise_for_status()
        tmp = p + ".part"
        with io.open(tmp, "wb") as fh:
            for chunk in r.iter_content(1 << 20):
                fh.write(chunk)
        os.replace(tmp, p)
        return p, f"downloaded ({os.path.getsize(p) / 1e6:.0f} MB)"
    except Exception as e:  # noqa: BLE001
        return (p if os.path.isfile(p) else None), f"download failed: {e}"


def load_retractions() -> dict[str, dict]:
    p, note = ensure_retraction_data()
    if not p or not os.path.isfile(p):
        return {}
    import csv
    idx: dict[str, dict] = {}
    with io.open(p, encoding="utf-8", errors="replace", newline="") as fh:
        for row in csv.DictReader(fh):
            rec = row.get("Record ID", "")
            for key, val in (("doi", (row.get("OriginalPaperDOI") or "").strip().lower()),
                             ("retractiondoi", (row.get("RetractionDOI") or "").strip().lower())):
                if val:
                    idx[f"{key}:{val}"] = row
            if rec:
                idx[f"rw:{rec}"] = row
    return idx


def check_retracted(doi: str, idx: dict[str, dict]) -> dict | None:
    if not doi:
        return None
    d = doi.lower().replace("https://doi.org/", "").strip()
    return idx.get(f"doi:{d}") or idx.get(f"retractiondoi:{d}")


# --------------------------------------------------------------------------
# reference-list parsing and verification
# --------------------------------------------------------------------------
# Handles the common shapes:
#   [1] Smith, J., Doe, A. (2024). Title here. Journal Name 12(3), 45-67.
#   1. Smith J. Title here. Journal Name. 2024;12(3):45-67. doi:10.xxxx/yyy
#   Smith, J. (2024). Title here. Journal, 12, 45-67. https://doi.org/10.xxxx
DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:a-zA-Z0-9]+", re.I)
YEAR_RE = re.compile(r"\b(1[89]\d\d|20\d\d)\b")
REF_START = re.compile(r"^\s*(?:\[(\d+)\]|(\d+)[.)])\s+(?=\S)")

# Standards and technical reports are not indexed by Crossref/OpenAlex as
# journal articles. Failing to find one is not evidence of fabrication, so it
# gets its own verdict rather than being lumped in with NOT_FOUND.
_STANDARD_RE = re.compile(
    r"\b(ASME|ASTM|ISO|IEC|IEEE\s+Std|BS\s+EN|GB/?T|DIN|JIS|ANSI|NIST|NASA)"
    r"[\s\-]*(?:V&V|STD|Standard|SP|Handbook)?[\s\-]*[\w.\-]*\d",
    re.I)


def parse_references(text: str) -> list[dict]:
    """Split a reference list into entries, keeping the original text."""
    lines = text.splitlines()
    start = 0
    for i, ln in enumerate(lines):
        if re.match(r"^\s*#{0,3}\s*(references|bibliography|参考文献)\s*$",
                    ln.strip(), re.I):
            start = i + 1
    entries, cur, num = [], [], None
    for ln in lines[start:]:
        if not ln.strip():
            continue
        m = REF_START.match(ln)
        if m:
            if cur and num is not None:
                entries.append({"n": num, "raw": " ".join(cur).strip()})
            elif cur:
                # text before the first numbered entry is a heading, not a ref
                pass
            num = int(m.group(1) or m.group(2))
            cur = [ln[m.end():]]
        elif num is not None:
            cur.append(ln.strip())
    if cur and num is not None:
        entries.append({"n": num, "raw": " ".join(cur).strip()})

    out = []
    for e in entries:
        raw = e["raw"]
        doi = ""
        m = DOI_RE.search(raw)
        if m:
            doi = m.group(0).rstrip(".,;)")
        ym = YEAR_RE.search(raw)
        year = ym.group(1) if ym else ""

        # Work on the text after the year: that is where the title lives.
        tail = raw
        if ym:
            tail = raw[ym.end():]
        tail = DOI_RE.sub(" ", tail)
        tail = re.sub(r"https?://\S+", " ", tail)
        tail = re.sub(r"^\s*[).,;:]\s*", "", tail)
        chunks = [c.strip(" .,;") for c in re.split(r"\.\s+", tail)]
        chunks = [c for c in chunks if len(c) > 14]

        # Candidate titles, best first. Several candidates are kept so the
        # lookup can try more than one query - the split is heuristic and one
        # bad split should not make a real reference look fabricated.
        cands: list[str] = []
        if chunks:
            # the journal/volume tail is conventionally last
            mid = chunks[:-1] if len(chunks) >= 2 else chunks
            if mid:
                cands.append(max(mid, key=len))
            # and the whole post-year text minus obvious tail markers
            joined = re.split(r"\.\s*(?=[A-Z][a-z]+ [A-Z]?\d|\d+\s*[,(])", tail)[0]
            joined = joined.strip(" .,;")
            if len(joined) > 14:
                cands.append(joined[:300])
            for c in sorted(chunks, key=len, reverse=True):
                if c not in cands:
                    cands.append(c)
        # de-duplicate, keep order
        seen, uniq = set(), []
        for c in cands:
            k = norm(c)[:80]
            if k and k not in seen:
                seen.add(k)
                uniq.append(c)

        # Author field: everything before the year.
        authors_guess = raw[:ym.start()].strip(" .,;") if ym else ""

        out.append({"n": e["n"], "raw": raw, "doi": doi, "year": year,
                    "title_guess": uniq[0] if uniq else "",
                    "title_candidates": uniq[:3],
                    "authors_guess": authors_guess})
    return out


def verify_entry(entry: dict, retractions: dict[str, dict],
                 allow_network: bool = True) -> dict:
    """Verify one reference against Crossref and OpenAlex.

    Strategy, strongest evidence first:

      1. If the entry carries a DOI and it RESOLVES, the registry record is
         authoritative - we do not second-guess it with a hand-parsed title.
         We only sanity-check the year and the first-author surname.
      2. Otherwise, search by several title candidates and accept a match only
         above a similarity threshold.
      3. Anything unmatched is NOT_FOUND and must not be cited.
    """
    result = {"n": entry["n"], "raw": entry["raw"], "verdict": "UNVERIFIED",
              "candidates": [], "problems": [], "fix": {}, "matched": {},
              "evidence": ""}

    # ---- 1. DOI first ----------------------------------------------------
    doi_recs: list[dict] = []
    doi_found = False
    if entry.get("doi") and allow_network:
        d, err = _get("https://api.crossref.org/works/" + entry["doi"],
                      {"mailto": MAILTO})
        if not err and d:
            doi_recs += _crossref_item(d.get("message") or {})
            doi_found = doi_found or bool(doi_recs)
        d, err = _get("https://api.openalex.org/works/https://doi.org/"
                      + entry["doi"], {"mailto": MAILTO})
        if not err and d:
            doi_recs += _openalex_item(d)
            doi_found = doi_found or bool(doi_recs)

    if doi_found:
        best = dedupe(doi_recs)[0]
        result["evidence"] = "DOI 解析成功，以注册库记录为准"
        result["candidates"] = [{"score": 1.0, "title": best["title"][:150],
                                 "year": best["year"],
                                 "journal": best["journal"][:90],
                                 "doi": best["doi"], "source": best["source"]}]
        _field_checks(entry, best, result)
        ret = check_retracted(best.get("doi", entry["doi"]), retractions)
        if ret:
            _mark_retracted(result, ret, best)
            return result
        result["verdict"] = "FIX" if result["problems"] else "VERIFIED"
        result["matched"] = {k: best.get(k, "") for k in
                             ("doi", "title", "authors", "year", "journal",
                              "volume", "issue", "pages", "source")}
        result["confidence"] = 1.0
        return result

    if entry.get("doi") and allow_network:
        result["problems"].append(
            f"DOI {entry['doi']} 在 Crossref 和 OpenAlex 都解析不到"
            "——这个 DOI 很可能是编的，或者已失效")

    # ---- 2. title search -------------------------------------------------
    cands: list[dict] = []
    if allow_network:
        for q in (entry.get("title_candidates") or [entry.get("title_guess", "")])[:3]:
            if not q or len(q) < 15:
                continue
            got = src_crossref(q, 5) + src_openalex(q, 5)
            cands += got
            # a strong hit on any candidate is enough; stop early
            if any(sim(q, c.get("title", "")) > 0.92 for c in got):
                break
    cands = dedupe(cands)

    scored = []
    for c in cands:
        s = sim(entry.get("title_guess", ""), c.get("title", ""))
        for alt in (entry.get("title_candidates") or [])[1:]:
            s = max(s, sim(alt, c.get("title", "")))
        if entry.get("year") and c.get("year"):
            s += 0.10 if entry["year"] == c["year"] else -0.15
        sa, ca = first_surname(entry.get("authors_guess", "")), rec_family(c)
        if sa and ca:
            s += 0.08 if sa == ca else -0.10
        scored.append((s, c))
    scored.sort(key=lambda x: -x[0])
    result["candidates"] = [
        {"score": round(s, 3), "title": c["title"][:150], "year": c["year"],
         "journal": c["journal"][:90], "doi": c["doi"], "source": c["source"]}
        for s, c in scored[:3]]

    if not scored:
        result["problems"].append("在任何数据源中都查不到这条文献")
        result["verdict"] = ("MANUAL_CHECK" if _STANDARD_RE.search(entry["raw"])
                             else "NOT_FOUND")
        if result["verdict"] == "MANUAL_CHECK":
            result["problems"][-1] += (
                "；这看起来是一条标准/技术报告，Crossref 与 OpenAlex 都不收录这类文献，"
                "必须到发布机构（ASME/ISO/IEEE 等）官网核对编号与年份")
        return result
    best_s, best = scored[0]

    if best_s < 0.72:
        result["problems"].append(
            f"最接近的候选只有 {best_s:.2f} 相似度，不足以确认是同一篇"
            f"（最接近的是：{best['title'][:80]}）")
        if _STANDARD_RE.search(entry["raw"]):
            result["verdict"] = "MANUAL_CHECK"
            result["problems"][-1] += (
                "；这看起来是一条标准/技术报告，须到发布机构官网核对")
        else:
            result["verdict"] = "NOT_FOUND"
        return result

    result["evidence"] = f"按标题检索匹配，相似度 {best_s:.2f}"
    _field_checks(entry, best, result)
    ret = check_retracted(best.get("doi", ""), retractions)
    if ret:
        _mark_retracted(result, ret, best)
        return result
    result["verdict"] = "FIX" if result["problems"] else "VERIFIED"
    result["matched"] = {k: best.get(k, "") for k in
                         ("doi", "title", "authors", "year", "journal",
                          "volume", "issue", "pages", "source")}
    result["confidence"] = round(best_s, 3)
    return result


def _fmt_authors(authors: str, source: str) -> str:
    """Present authors as 'Family, Given; Family, Given' regardless of source."""
    if not authors:
        return ""
    out = []
    for a in authors.split(";"):
        a = a.strip()
        if not a:
            continue
        if source == "crossref":
            parts = a.split()
            if len(parts) >= 2:
                out.append(f"{parts[0]}, {' '.join(parts[1:])}")
            else:
                out.append(a)
        else:
            parts = a.split()
            if len(parts) >= 2:
                out.append(f"{parts[-1]}, {' '.join(parts[:-1])}")
            else:
                out.append(a)
    return "; ".join(out)


_JSTOP = {"and", "of", "the", "in", "for", "on", "to", "a", "an", "with",
          "at", "by", "part", "series", "international", "journal",
          "proceedings", "proc"}


def _significant(name: str) -> list[str]:
    return [w for w in norm(name).split()
            if not w.isdigit() and w not in _JSTOP]


def _prefix_match(a: str, b: str) -> bool:
    """True if one word is an abbreviation of the other (>= 3 chars overlap)."""
    if not a or not b:
        return False
    if a == b:
        return True
    k = min(len(a), len(b), 4)
    return a[:k] == b[:k]


def journal_matches(manuscript_text: str, registry_journal: str) -> bool:
    """Does the entry's text cite this journal, allowing for abbreviation?

    Journal names are cited abbreviated far more often than in full, and the
    abbreviation both truncates words and drops filler: "Smart Materials and
    Structures" becomes "Smart Mater. Struct."; "International Journal of
    Mechanics and Materials in Design" becomes "Int J Mech Mater Des". Word
    order also flips for some titles ("Proc SPIE" vs "SPIE Proceedings").

    So the test is: every significant word of the registry name must have a
    prefix-compatible partner somewhere in the entry, in any order. Matching
    all of them by a >=3-character prefix is very unlikely to happen by chance.
    """
    if not registry_journal:
        return True
    sig = _significant(registry_journal)
    if len(sig) < 2:
        return True                      # one-word titles are too weak to test
    hay = norm(manuscript_text)
    if norm(registry_journal) in hay:
        return True
    hwords = [w for w in hay.split() if w not in _JSTOP and not w.isdigit()]
    return all(any(_prefix_match(f, h) for h in hwords) for f in sig)


# registry types that are not journal articles: their "container" is a book or
# a publisher, so a journal-name comparison is meaningless.
_BOOKISH = {"book", "monograph", "edited-book", "reference-book",
            "book-chapter", "reference-entry", "proceedings-article",
            "standard", "report", "dissertation"}


def _field_checks(entry: dict, best: dict, result: dict) -> None:
    """Compare the manuscript's rendering of the entry with the registry."""
    bookish = (best.get("type", "") or "") in _BOOKISH
    result.setdefault("notes", [])

    if entry.get("year") and best.get("year") and entry["year"] != best["year"]:
        dy = abs(int(entry["year"]) - int(best["year"]))
        msg = (f"年份不符：稿子里写 {entry['year']}，"
               f"注册库记录是 {best['year']}")
        if dy == 1:
            # extremely common: the registry carries the online-first year while
            # the issue carries the next one (or vice versa). Flag it so the
            # author checks the printed issue, but do not call it a defect.
            result["notes"].append(
                msg + "（相差一年通常是「在线首发年」与「正式卷期年」不同，"
                      "请按你要投的刊的引用规范确认取哪个）")
        else:
            result["problems"].append(msg)
            result["fix"]["year"] = best["year"]
    if entry.get("doi") and best.get("doi") and \
            entry["doi"].lower() != best["doi"].lower():
        result["problems"].append(
            f"DOI 不符：稿子里是 {entry['doi']}，注册库记录是 {best['doi']}")
        result["fix"]["doi"] = best["doi"]
    if not entry.get("doi") and best.get("doi"):
        result["fix"]["doi"] = best["doi"]

    if best.get("journal"):
        if bookish:
            result["notes"].append(
                f"这是一条{'标准' if best.get('type') == 'standard' else '图书/会议'}类文献，"
                f"注册库把它归在「{best['journal']}」下，刊名不必比对")
        elif not journal_matches(entry["raw"], best["journal"]):
            result["problems"].append(
                f"刊名在条目里对不上：注册库记录是「{best['journal']}」")
            result["fix"]["journal"] = best["journal"]

    if best.get("authors"):
        sa, ca = first_surname(entry.get("authors_guess", "")), rec_family(best)
        if sa and ca and sa != ca:
            msg = (f"第一作者姓氏对不上：条目里是「{sa}」，"
                   f"注册库记录是「{ca}」")
            if bookish:
                # book records often list authors in a different order than the
                # title page, so this is worth knowing but not a defect
                result["notes"].append(msg + "（图书记录的作者顺序常与封面不同）")
            else:
                result["problems"].append(msg)
                result["fix"]["authors"] = _fmt_authors(best["authors"],
                                                        best["source"])
    if not entry.get("doi") and best.get("doi"):
        result["notes"].append(
            f"条目里没有 DOI；注册库给出的是 {best['doi']}，建议补上")


def _mark_retracted(result: dict, ret: dict, best: dict) -> None:
    result["problems"].append(
        "**这篇文献已被撤稿，不能作为依据引用**"
        + (f"（撤稿日期 {ret.get('RetractionDate', '?')}，"
           f"性质 {ret.get('RetractionNature', '?')}）" if ret else ""))
    result["verdict"] = "RETRACTED"
    result["retraction"] = {k: ret.get(k, "") for k in
                            ("Title", "RetractionDate", "RetractionNature",
                             "Reason", "OriginalPaperDOI")}
    result["matched"] = {k: best.get(k, "") for k in
                         ("doi", "title", "authors", "year", "journal")}


def _crossref_item(w: dict) -> list[dict]:
    if not w:
        return []
    au = w.get("author") or []
    names = "; ".join(f"{a.get('family','')} {a.get('given','')}".strip()
                      for a in au[:8] if a.get("family") or a.get("given"))
    fam0 = (au[0].get("family") or "") if au else ""
    t = w.get("title") or []
    j = w.get("container-title") or []
    return [_rec(doi=w.get("DOI", ""), title=(t[0] if t else ""), authors=names,
                 first_family=fam0,
                 year=year_of(w.get("issued")), journal=(j[0] if j else ""),
                 volume=w.get("volume", ""), issue=w.get("issue", ""),
                 pages=w.get("page", ""), type=w.get("type", ""),
                 source="crossref", url=w.get("URL", ""),
                 cited_by=w.get("is-referenced-by-count"))]


def _openalex_item(w: dict) -> list[dict]:
    if not w:
        return []
    au = w.get("authorships") or []
    names = "; ".join((a.get("author") or {}).get("display_name", "")
                      for a in au[:8] if (a.get("author") or {}).get("display_name"))
    loc = (w.get("primary_location") or {}).get("source") or {}
    bib = w.get("biblio") or {}
    return [_rec(doi=(w.get("doi") or "").replace("https://doi.org/", ""),
                 title=w.get("title") or "", authors=names,
                 year=year_of(w.get("publication_year")),
                 journal=loc.get("display_name") or "",
                 volume=bib.get("volume") or "", issue=bib.get("issue") or "",
                 type=w.get("type") or "", source="openalex",
                 url=w.get("id") or "", cited_by=w.get("cited_by_count"))]


# ----------------------------------------------------------------- commands
def cmd_search(a) -> int:
    srcs = [s.strip() for s in a.source.split(",") if s.strip()] or \
           ["openalex", "crossref"]
    bad = [s for s in srcs if s not in SOURCES]
    if bad:
        print(f"[fail] 未知数据源 {bad}；可用：{list(SOURCES)}", file=sys.stderr)
        return 1
    print(f"检索：{a.query}")
    print(f"数据源：{', '.join(srcs)}　上限：{a.limit} 条/源\n")
    allrecs = []
    for s in srcs:
        t0 = time.time()
        got = SOURCES[s](a.query, a.limit, year_from=a.year_from)
        print(f"  {s:10s} {len(got):4d} 条  ({time.time() - t0:.1f}s)")
        allrecs += got
    merged = dedupe(allrecs)
    print(f"\n去重后 {len(merged)} 条")
    out = a.out or os.path.join("refs", f"search_{int(time.time())}.json")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with io.open(out, "w", encoding="utf-8") as fh:
        json.dump({"query": a.query, "sources": srcs, "count": len(merged),
                   "retrieved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                 time.gmtime()),
                   "records": merged}, fh, ensure_ascii=False, indent=1)
    print(f"[ok] {out}")
    for r in merged[:a.show]:
        print(f"\n  {r['year']:4s}  {r['title'][:96]}")
        print(f"        {r['journal'][:70]}  doi:{r['doi'] or '(无)'}"
              f"  [{r['source']}{'+' + '+'.join(r.get('also_in', [])) if r.get('also_in') else ''}]")
    return 0


def cmd_doi(a) -> int:
    doi = a.doi.strip().replace("https://doi.org/", "")
    print(f"解析 DOI：{doi}\n")
    got = []
    d, err = _get("https://api.crossref.org/works/" + doi, {"mailto": MAILTO})
    if err:
        print(f"  crossref  {err}")
    else:
        got += _crossref_item(d.get("message") or {})
    d, err = _get("https://api.openalex.org/works/https://doi.org/" + doi,
                  {"mailto": MAILTO})
    if err:
        print(f"  openalex  {err}")
    else:
        got += _openalex_item(d)
    if not got:
        print("[fail] 这个 DOI 在两个数据源里都解析不到 —— 不要用它")
        return 1
    m = dedupe(got)[0]
    for k, lab in (("title", "标题"), ("authors", "作者"), ("year", "年份"),
                   ("journal", "期刊"), ("volume", "卷"), ("issue", "期"),
                   ("pages", "页"), ("doi", "DOI"), ("cited_by", "被引")):
        if m.get(k) not in (None, ""):
            print(f"  {lab:4s} {m[k]}")
    rw = load_retractions()
    if rw:
        ret = check_retracted(doi, rw)
        print("\n  撤稿状态：" + ("**已撤稿** -- 不可引用" if ret else "未见撤稿记录"))
    if a.json_out:
        with io.open(a.json_out, "w", encoding="utf-8") as fh:
            json.dump(m, fh, ensure_ascii=False, indent=1)
        print(f"\n[ok] {a.json_out}")
    return 0


def cmd_verify(a) -> int:
    p = a.refs
    if not os.path.isfile(p):
        print(f"[fail] 找不到 {p}", file=sys.stderr)
        return 1
    with io.open(p, encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    entries = parse_references(text)
    if not entries:
        print("[fail] 没能从文件里解析出参考文献条目。"
              "文件里需要有 'References' 之类的标题，条目以 [1] 或 '1.' 开头。",
              file=sys.stderr)
        return 1
    print(f"核验 {p}")
    print(f"解析出 {len(entries)} 条参考文献\n")
    rw = load_retractions() if not a.no_retraction_check else {}
    if rw:
        print(f"撤稿库：{len(rw)} 条记录（含原文与撤稿两种 DOI）\n")

    results, tally = [], {}
    for e in entries:
        r = verify_entry(e, rw, allow_network=not a.offline)
        results.append(r)
        tally[r["verdict"]] = tally.get(r["verdict"], 0) + 1
        mark = {"VERIFIED": "OK  ", "FIX": "FIX ", "NOT_FOUND": "MISS",
                "RETRACTED": "RETR", "UNVERIFIED": "????",
                "MANUAL_CHECK": "MANU"}[r["verdict"]]
        print(f"  [{mark}] [{e['n']}] {(e['title_guess'] or e['raw'])[:78]}")
        for pr in r["problems"]:
            print(f"         ! {pr}")
        for nt in r.get("notes", []):
            print(f"         . {nt}")
        if r.get("fix"):
            for k, v in r["fix"].items():
                print(f"         -> {k} 应为：{str(v)[:90]}")

    print("\n" + "=" * 60)
    for k in ("VERIFIED", "FIX", "NOT_FOUND", "RETRACTED", "UNVERIFIED",
              "MANUAL_CHECK"):
        if tally.get(k):
            note = {"MANUAL_CHECK": "  （标准/报告类，须手动核对发布机构官网）",
                    "VERIFIED": "", "FIX": "  （元数据按 fix 改正）",
                    "NOT_FOUND": "  （查不到，不能引用）",
                    "RETRACTED": "  （已撤稿，绝对不能引用）",
                    "UNVERIFIED": "  （未能确认）"}[k]
            print(f"  {k:12s} {tally[k]}{note}")
    blocking = (tally.get("NOT_FOUND", 0) + tally.get("RETRACTED", 0)
                + tally.get("UNVERIFIED", 0))
    print()
    if blocking:
        print(f"**{blocking} 条不能直接引用**：查不到的不能引，"
              f"被撤稿的绝对不能引，未核实的要标 UNVERIFIED。")
    if tally.get("MANUAL_CHECK"):
        print(f"**{tally['MANUAL_CHECK']} 条需人工核对**"
              "（标准/技术报告不在学术数据库里，去发布机构官网查编号与年份）。")
    if not blocking and not tally.get("MANUAL_CHECK"):
        print("全部条目都能定位到真实文献。" +
              ("有 FIX 的按提示改元数据。" if tally.get("FIX") else ""))

    out = a.out or os.path.join(os.path.dirname(p) or ".", "citation_verify.json")
    with io.open(out, "w", encoding="utf-8") as fh:
        json.dump({"refs_file": p, "verified_at": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "tally": tally,
            "blocking": blocking, "results": results}, fh,
            ensure_ascii=False, indent=1)
    print(f"\n[ok] 报告：{out}")
    return 1 if blocking else 0


def cmd_retract(a) -> int:
    rw = load_retractions()
    if not rw:
        print("[fail] 拿不到撤稿库（下载失败且无缓存）", file=sys.stderr)
        return 1
    print(f"撤稿库已就绪：{len(rw)} 条索引\n")
    hits = 0
    if a.doi:
        r = check_retracted(a.doi, rw)
        if r:
            hits += 1
            print(f"  **已撤稿** {a.doi}")
            print(f"     标题：{r.get('Title','')}")
            print(f"     撤稿日期：{r.get('RetractionDate','')}　"
                  f"性质：{r.get('RetractionNature','')}")
            print(f"     原因：{(r.get('Reason') or '')[:300]}")
        else:
            print(f"  未见撤稿记录：{a.doi}")
        return 1 if r else 0
    if a.refs:
        with io.open(a.refs, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        for e in parse_references(text):
            if not e.get("doi"):
                continue
            r = check_retracted(e["doi"], rw)
            if r:
                hits += 1
                print(f"  **[{e['n']}] 已撤稿** {e['doi']}")
                print(f"     {(r.get('Reason') or '')[:200]}")
        print(f"\n共 {hits} 条被撤稿。" if hits else "\n未发现被撤稿的引用。")
        return 1 if hits else 0
    print("要给 --doi 或 --refs")
    return 2


def cmd_cited_by(a) -> int:
    doi = a.doi.strip().replace("https://doi.org/", "")
    d, err = _get("https://api.openalex.org/works",
                  {"filter": f"cites:https://doi.org/{doi}",
                   "per-page": min(a.limit, 100), "mailto": MAILTO})
    if err or not d:
        print(f"[fail] {err or '解析不到'}")
        return 1
    print(f"引用 {doi} 的文献（共 {(d.get('meta') or {}).get('count', 0)} 篇）\n")
    for w in d.get("results", []):
        loc = (w.get("primary_location") or {}).get("source") or {}
        print(f"  {year_of(w.get('publication_year'))}  "
              f"{(w.get('title') or '')[:88]}")
        print(f"        {loc.get('display_name','')[:70]}")
    return 0


def cmd_export(a) -> int:
    with io.open(a.infile, encoding="utf-8") as fh:
        data = json.load(fh)
    recs = data.get("records", data if isinstance(data, list) else [])
    out = a.out or os.path.splitext(a.infile)[0] + "." + a.style
    if a.style == "ris":
        blocks = []
        for r in recs:
            L = ["TY  - JOUR" if r.get("type") != "preprint" else "TY  - UNPB"]
            for k, tag in (("title", "TI"), ("authors", "AU"), ("year", "PY"),
                           ("journal", "JO"), ("volume", "VL"), ("issue", "IS"),
                           ("pages", "SP"), ("doi", "DO"), ("url", "UR")):
                if r.get(k):
                    val = r[k].replace("; ", "\nAU  - ") if k == "authors" else r[k]
                    L.append(f"{tag}  - {val}")
            blocks.append("\n".join(L) + "\nER  -")
        body = "\n\n".join(blocks) + "\n"
    elif a.style == "bibtex":
        body = ""
        for i, r in enumerate(recs, 1):
            key = (r.get("authors", "anon").split(";")[0].split()[-1].lower()
                   if r.get("authors") else "anon") + str(r.get("year", i))
            body += (f"@article{{{key},\n  title = {{{r.get('title','')}}},\n"
                     f"  author = {{{r.get('authors','')}}},\n"
                     f"  journal = {{{r.get('journal','')}}},\n"
                     f"  year = {{{r.get('year','')}}},\n"
                     f"  doi = {{{r.get('doi','')}}}\n}}\n\n")
    else:
        cols = ["doi", "title", "authors", "year", "journal", "volume",
                "issue", "pages", "source"]
        rows = [",".join(cols)]
        for r in recs:
            rows.append(",".join('"' + str(r.get(c, "")).replace('"', "'") + '"'
                                 for c in cols))
        body = "\n".join(rows) + "\n"
    with io.open(out, "w", encoding="utf-8") as fh:
        fh.write(body)
    print(f"[ok] {out}（{len(recs)} 条，{a.style}）")
    return 0


def main() -> int:
    _utf8()
    ap = argparse.ArgumentParser(prog="litsearch",
                                 description="真实文献检索与参考文献核验")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search", help="多源检索并保存结构化记录")
    s.add_argument("--query", required=True)
    s.add_argument("--source", default="openalex,crossref",
                   help=f"逗号分隔，可选：{','.join(SOURCES)}")
    s.add_argument("--limit", type=int, default=25)
    s.add_argument("--year-from", dest="year_from", default="")
    s.add_argument("--out", default="")
    s.add_argument("--show", type=int, default=8)
    s.set_defaults(func=cmd_search)

    d = sub.add_parser("doi", help="解析一个 DOI 的权威元数据")
    d.add_argument("doi")
    d.add_argument("--json", dest="json_out", default="")
    d.set_defaults(func=cmd_doi)

    v = sub.add_parser("verify", help="逐条核验参考文献是否真实存在")
    v.add_argument("--refs", required=True)
    v.add_argument("--out", default="")
    v.add_argument("--offline", action="store_true",
                   help="不联网，只做本地一致性检查")
    v.add_argument("--no-retraction-check", dest="no_retraction_check",
                   action="store_true")
    v.set_defaults(func=cmd_verify)

    r = sub.add_parser("retract", help="检查是否引用到被撤稿的文献")
    r.add_argument("--doi", default="")
    r.add_argument("--refs", default="")
    r.set_defaults(func=cmd_retract)

    c = sub.add_parser("cited-by", help="谁引用了这篇文献")
    c.add_argument("--doi", required=True)
    c.add_argument("--limit", type=int, default=25)
    c.set_defaults(func=cmd_cited_by)

    e = sub.add_parser("export", help="导出 ris / bibtex / csv")
    e.add_argument("--in", dest="infile", required=True)
    e.add_argument("--style", default="ris", choices=["ris", "bibtex", "csv"])
    e.add_argument("--out", default="")
    e.set_defaults(func=cmd_export)

    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
