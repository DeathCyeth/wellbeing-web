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
from typing import List, Optional, Tuple
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


def gather_open_source_clinical_block(question: str, pubmed_max: int = 4) -> Optional[str]:
    """
    Build a single text block for the LLM from PubMed + openFDA.
    Returns None if nothing retrieved or question too short.
    """
    q = (question or "").strip()
    if len(q) < 4:
        return None

    parts: List[str] = []

    pmids = _pubmed_search_ids(q, retmax=pubmed_max)
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

    # openFDA: try specific generic/brand matches from query tokens
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
        return None

    header = (
        "Open-data clinical context (PubMed + openFDA). "
        "These are third-party public sources - not a diagnosis or prescribing instruction. "
        "Prefer recent guidelines and the patient's care team for decisions.\n\n"
    )
    return header + "\n\n".join(parts)
