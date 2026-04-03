"""
Open, no-license clinical data for AI grounding (Doximity-style "evidence" feel).

Uses public APIs only:
- PubMed / NCBI E-utilities — literature (https://www.ncbi.nlm.nih.gov/home/develop/api/)
- openFDA — U.S. drug labeling (https://open.fda.gov/apis/)

Set NCBI_EMAIL (recommended by NCBI) and optionally NCBI_API_KEY for higher rate limits.
"""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

import httpx

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
OPENFDA_LABEL = "https://api.fda.gov/drug/label.json"

# NCBI asks tools to identify themselves; email improves support if they need to contact you.
_TOOL = "wellbeing-web"
_EMAIL = os.environ.get("NCBI_EMAIL", "wellbeing-web@localhost")
_NCBI_KEY = os.environ.get("NCBI_API_KEY", "").strip()


def _eutils_params(extra: dict) -> dict:
    p = {"tool": _TOOL, "email": _EMAIL, **extra}
    if _NCBI_KEY:
        p["api_key"] = _NCBI_KEY
    return p


def _tokenize_for_fda(q: str) -> List[str]:
    """Short tokens that might match generic/brand names in openFDA."""
    raw = re.findall(r"[A-Za-z][A-Za-z0-9\-]{3,}", (q or "").lower())
    stop = {
        "what", "when", "where", "which", "who", "how", "why", "does", "have", "been",
        "from", "with", "that", "this", "your", "about", "into", "some", "than", "them",
        "then", "there", "these", "those", "very", "just", "only", "also", "like", "make",
        "help", "take", "safe", "good", "best", "food", "diet", "much", "many", "more",
        "most", "should", "could", "would", "patient", "doctor", "symptoms", "cause",
        "treatment", "medication", "medications", "drug", "drugs", "pill", "pills", "dose",
    }
    out = []
    for t in raw:
        if t in stop:
            continue
        if t not in out:
            out.append(t)
        if len(out) >= 6:
            break
    return out


def _pubmed_search_ids(term: str, retmax: int = 5) -> List[str]:
    term = (term or "").strip()[:400]
    if len(term) < 4:
        return []
    with httpx.Client(timeout=25.0) as client:
        r = client.get(
            f"{EUTILS_BASE}/esearch.fcgi",
            params=_eutils_params(
                {"db": "pubmed", "term": term, "retmax": str(retmax), "retmode": "json", "sort": "relevance"}
            ),
        )
        r.raise_for_status()
        data = r.json()
        return data.get("esearchresult", {}).get("idlist") or []


def _pubmed_fetch_summaries(pmids: List[str]) -> str:
    if not pmids:
        return ""
    with httpx.Client(timeout=35.0) as client:
        r = client.get(
            f"{EUTILS_BASE}/efetch.fcgi",
            params=_eutils_params(
                {"db": "pubmed", "id": ",".join(pmids), "rettype": "abstract", "retmode": "xml"}
            ),
        )
        r.raise_for_status()
        return r.text


def _parse_pubmed_xml(xml_text: str, max_abstract_len: int = 900) -> List[Tuple[str, str, str]]:
    """Returns list of (pmid, title, abstract_snippet)."""
    rows: List[Tuple[str, str, str]] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return rows
    for article in root.findall(".//PubmedArticle"):
        pmid_el = article.find(".//MedlineCitation/PMID")
        if pmid_el is None:
            pmid_el = article.find(".//PMID")
        title_el = article.find(".//ArticleTitle")
        if pmid_el is None:
            continue
        pmid = (pmid_el.text or "").strip()
        title = (title_el.text or "Untitled").strip().replace("\n", " ")
        abstract_bits = []
        ab = article.find(".//Abstract")
        if ab is not None:
            for at in ab.findall("AbstractText"):
                label = at.get("Label")
                chunk = (at.text or "").strip()
                if not chunk:
                    continue
                if label:
                    abstract_bits.append(f"{label}: {chunk}")
                else:
                    abstract_bits.append(chunk)
        abstract = " ".join(abstract_bits).replace("\n", " ")
        if len(abstract) > max_abstract_len:
            abstract = abstract[: max_abstract_len - 1].rsplit(" ", 1)[0] + "…"
        rows.append((pmid, title, abstract or "(no abstract in PubMed record)"))
    return rows


def _openfda_label_search(search_expr: str, limit: int = 1) -> Optional[dict]:
    search_expr = (search_expr or "").strip()
    if not search_expr:
        return None
    with httpx.Client(timeout=25.0) as client:
        r = client.get(OPENFDA_LABEL, params={"search": search_expr, "limit": str(limit)})
        if r.status_code != 200:
            return None
        data = r.json()
        results = data.get("results") or []
        return results[0] if results else None


def _format_openfda_hit(hit: dict) -> Optional[str]:
    if not hit:
        return None
    of = hit.get("openfda") or {}
    brands = of.get("brand_name") or []
    generics = of.get("generic_name") or []
    set_id = hit.get("set_id") or ""
    brand = brands[0] if brands else ""
    generic = generics[0] if generics else ""
    ind = hit.get("indications_and_usage") or []
    warn = hit.get("warnings") or []
    text = ind[0] if isinstance(ind, list) and ind else ""
    if not text and isinstance(warn, list) and warn:
        text = warn[0]
    if isinstance(text, str):
        t = re.sub(r"\s+", " ", text).strip()
        if len(t) > 1000:
            t = t[:999].rsplit(" ", 1)[0] + "…"
    else:
        t = ""
    if not t and not brand and not generic:
        return None
    lines = ["--- openFDA U.S. drug label (public data; not personalized medical advice) ---"]
    if brand or generic:
        lines.append(f"Product context: brand={brand or 'n/a'}, generic={generic or 'n/a'}")
    if set_id:
        lines.append(f"openFDA set_id: {set_id}")
    lines.append(f"Label excerpt: {t or '(see openFDA for full label)'}")
    lines.append(f"Verify on openFDA: {OPENFDA_LABEL}?search=set_id:{quote(set_id, safe='')}" if set_id else f"Browse: {OPENFDA_LABEL}")
    return "\n".join(lines)


def _pubmed_esummary_json(pmids: List[str]) -> dict:
    if not pmids:
        return {}
    with httpx.Client(timeout=35.0) as client:
        r = client.get(
            f"{EUTILS_BASE}/esummary.fcgi",
            params=_eutils_params({"db": "pubmed", "id": ",".join(pmids), "retmode": "json"}),
        )
        r.raise_for_status()
        return r.json()


def _year_from_esummary(rec: dict) -> str:
    sp = (rec.get("sortpubdate") or "")[:10]
    if len(sp) >= 4 and sp[:4].isdigit():
        return sp[:4]
    pd = rec.get("pubdate") or ""
    m = re.match(r"(\d{4})", pd)
    return m.group(1) if m else ""


def _doi_from_esummary(rec: dict) -> str:
    for aid in rec.get("articleids") or []:
        if isinstance(aid, dict) and aid.get("idtype") == "doi":
            return (aid.get("value") or "").strip()
    return ""


def _author_family_from_pubmed_name(name: str) -> str:
    """Best-effort: first token is family name for 'Sanchez-Rangel E' style."""
    if not name:
        return ""
    return name.split()[0]


def citation_record_from_esummary(pmid: str, rec: dict) -> Dict[str, Any]:
    """Structured reference for API + APA-style strings."""
    title = (rec.get("title") or "Untitled").strip()
    if title.endswith("."):
        title_t = title
    else:
        title_t = title + "."
    journal = (rec.get("fulljournalname") or rec.get("source") or "").strip()
    volume = (rec.get("volume") or "").strip()
    issue = (rec.get("issue") or "").strip()
    pages = (rec.get("pages") or "").strip()
    year = _year_from_esummary(rec) or "n.d."
    doi = _doi_from_esummary(rec)
    url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
    authors_raw = []
    for a in rec.get("authors") or []:
        if isinstance(a, dict) and a.get("name"):
            authors_raw.append(a["name"].strip())
    sort_first = (rec.get("sortfirstauthor") or "").strip()
    fam = _author_family_from_pubmed_name(sort_first) or (
        _author_family_from_pubmed_name(authors_raw[0]) if authors_raw else "Unknown"
    )
    citation_short = f"{title} ({fam}, {year})"
    # APA 7th-style journal article (omit missing parts)
    auth_bits = []
    for nm in authors_raw[:6]:
        parts = nm.rsplit(" ", 1)
        if len(parts) == 2 and len(parts[1]) <= 4 and parts[1].replace("-", "").isalpha():
            auth_bits.append(f"{parts[0]}, {parts[1].replace(' ', '.')}.".replace("..", "."))
        else:
            auth_bits.append(nm)
    if len(authors_raw) > 6:
        auth_str = ", ".join(auth_bits) + ", et al."
    elif len(auth_bits) == 1:
        auth_str = auth_bits[0]
    elif len(auth_bits) == 2:
        auth_str = f"{auth_bits[0]}, & {auth_bits[1]}"
    elif auth_bits:
        auth_str = ", ".join(auth_bits[:-1]) + f", & {auth_bits[-1]}"
    else:
        auth_str = fam
    jrnl = f"*{journal}*" if journal else ""
    voliss = ""
    if volume and issue:
        voliss = f", *{volume}*({issue})"
    elif volume:
        voliss = f", *{volume}*"
    pg = f", {pages}" if pages else ""
    citation_apa = f"{auth_str} ({year}). {title_t}"
    if journal:
        citation_apa += f" {jrnl}{voliss}{pg}."
    else:
        citation_apa += "."
    if doi:
        citation_apa += f" https://doi.org/{doi}"
    return {
        "pmid": pmid,
        "title": title,
        "authors": authors_raw,
        "year": year,
        "journal": journal,
        "volume": volume,
        "issue": issue,
        "pages": pages,
        "doi": doi,
        "url": url,
        "citation_short": citation_short,
        "citation_apa": citation_apa,
        "source": "pubmed",
    }


def pubmed_references_for_pmids(pmids: List[str]) -> List[Dict[str, Any]]:
    """Deduplicate while preserving order; fetch NLM summary metadata."""
    seen = set()
    ordered: List[str] = []
    for p in pmids:
        p = (p or "").strip()
        if not p.isdigit() or p in seen:
            continue
        seen.add(p)
        ordered.append(p)
    if not ordered:
        return []
    data = _pubmed_esummary_json(ordered)
    result = data.get("result", {})
    uids = result.get("uids") or ordered
    out: List[Dict[str, Any]] = []
    for uid in uids:
        rec = result.get(uid)
        if not isinstance(rec, dict):
            continue
        out.append(citation_record_from_esummary(str(uid), rec))
    return out


def build_repository_pubmed_block(pmids: List[str], max_abstract_len: int = 800) -> Optional[str]:
    """Text block for LLM from curated repository PMIDs."""
    if not pmids:
        return None
    xml_blob = _pubmed_fetch_summaries(pmids[:20])
    articles = _parse_pubmed_xml(xml_blob, max_abstract_len=max_abstract_len)
    if not articles:
        return None
    lines = [
        "--- Curated literature repository (your practice / patient-linked PubMed IDs) ---",
        "Prioritize these when relevant to the question. Link: https://pubmed.ncbi.nlm.nih.gov/PMID/",
    ]
    for pmid, title, abstract in articles:
        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        lines.append(f"PMID {pmid} | {title}")
        lines.append(f"URL: {url}")
        lines.append(abstract)
        lines.append("")
    return "\n".join(lines).strip()


def gather_open_source_clinical_bundle(
    question: str, pubmed_max: int = 4
) -> Dict[str, Any]:
    """
    PubMed query search + openFDA. Returns text_block, query_pmids (from search only).
    """
    q = (question or "").strip()
    out: Dict[str, Any] = {"text_block": None, "query_pmids": []}
    if len(q) < 4:
        return out

    parts: List[str] = []
    pmids = _pubmed_search_ids(q, retmax=pubmed_max)
    out["query_pmids"] = list(pmids)
    if pmids:
        xml_blob = _pubmed_fetch_summaries(pmids)
        articles = _parse_pubmed_xml(xml_blob)
        if articles:
            lines = [
                "--- PubMed / NLM (peer-reviewed literature index; abstracts may be incomplete) ---",
                "Use for general background only. Link format for references: https://pubmed.ncbi.nlm.nih.gov/PMID/",
            ]
            for pmid, title, abstract in articles:
                url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
                lines.append(f"PMID {pmid} | {title}")
                lines.append(f"URL: {url}")
                lines.append(abstract)
                lines.append("")
            parts.append("\n".join(lines).strip())

    seen_set_ids = set()
    for tok in _tokenize_for_fda(q)[:4]:
        expr = f'openfda.generic_name:"{tok}"'
        hit = _openfda_label_search(expr, limit=1)
        if not hit:
            hit = _openfda_label_search(f'openfda.brand_name:"{tok}"', limit=1)
        if not hit:
            continue
        sid = hit.get("set_id") or ""
        if sid and sid in seen_set_ids:
            continue
        if sid:
            seen_set_ids.add(sid)
        fmt = _format_openfda_hit(hit)
        if fmt:
            parts.append(fmt)
            break

    if not parts:
        return out

    header = (
        "Open-data clinical context (PubMed + openFDA). "
        "These are third-party public sources - not a diagnosis or prescribing instruction. "
        "Prefer recent guidelines and the patient's care team for decisions.\n\n"
    )
    out["text_block"] = header + "\n\n".join(parts)
    return out


def gather_open_source_clinical_block(question: str, pubmed_max: int = 4) -> Optional[str]:
    """Backward-compatible: text only."""
    b = gather_open_source_clinical_bundle(question, pubmed_max=pubmed_max)
    return b.get("text_block")
