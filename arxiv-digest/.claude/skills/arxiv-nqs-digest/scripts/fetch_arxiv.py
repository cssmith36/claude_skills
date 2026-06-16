#!/usr/bin/env python3
"""Fetch recent arXiv papers for the daily NQS / ML-for-quantum digest.

Pure standard library (urllib + xml.etree) so it runs in a routine
environment with no pip installs. Hits the official arXiv API, applies a
date window, drops papers already recorded in the state file, and prints
the remaining candidates as JSON to stdout.

The relevance *judgement* is intentionally NOT done here -- that is the
language model's job (see SKILL.md). This script only does the
deterministic part: fetch + de-duplicate, so the model never has to
invent or recall paper metadata.

Usage:
    python fetch_arxiv.py --state /path/to/arxiv_seen.json
"""

import argparse
import datetime as dt
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

API = "https://export.arxiv.org/api/query"

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}

# Each lane is one arXiv `search_query`. Lane 1 pulls the NQS home
# categories broadly; the others gate high-volume categories behind
# keyword filters so the digest does not drown in unrelated ML / quant-ph.
# Widen these if you find relevant papers are being missed.
QUERIES = [
    # Lane 1 -- NQS / correlated-electron home categories, pulled broadly.
    "cat:cond-mat.str-el OR cat:cond-mat.dis-nn",

    # Lane 2 -- broader categories gated behind ML / quantum-method keywords.
    # supr-con included so NQS / ML-for-superconductivity papers are caught.
    '(cat:quant-ph OR cat:physics.comp-ph OR cat:physics.chem-ph '
    'OR cat:cond-mat.mes-hall OR cat:cond-mat.mtrl-sci OR cat:cond-mat.supr-con) AND '
    '(abs:"neural network" OR abs:"machine learning" OR abs:"deep learning" '
    'OR abs:"neural quantum state" OR abs:"variational Monte Carlo" '
    'OR abs:"wave function" OR abs:"wavefunction" OR abs:"density functional")',

    # Lane 3 -- ML categories, gated to a quantum / many-body context.
    '(cat:cs.LG OR cat:stat.ML) AND '
    '(abs:quantum OR abs:"many-body" OR abs:wavefunction '
    'OR abs:"electronic structure" OR abs:Schrodinger OR abs:superconduct)',

    # Lane 4 -- Wigner crystals & the 2D electron gas (physics, no ML gate).
    '(cat:cond-mat.mes-hall OR cat:cond-mat.mtrl-sci OR cat:quant-ph) AND '
    '(abs:"Wigner crystal" OR abs:"Wigner solid" OR abs:"electron crystal" '
    'OR abs:"2D electron gas" OR abs:"two-dimensional electron gas" '
    'OR abs:"artificial graphene")',

    # Lane 5 -- quantum Hall / magnetic-field physics. Your active frontier:
    # three in-progress NQS-in-field / quantum-Hall papers, so favour recall.
    '(cat:cond-mat.mes-hall OR cat:quant-ph) AND '
    '(abs:"fractional quantum Hall" OR abs:"quantum Hall" OR abs:"Landau level" '
    'OR abs:"composite fermion")',

    # Lane 6 -- moire / flat-band correlated systems & 2D superconductivity.
    # Main volume driver; tighten these keywords if it floods the digest.
    '(cat:cond-mat.mes-hall OR cat:cond-mat.mtrl-sci OR cat:cond-mat.supr-con) AND '
    '(abs:moire OR abs:"twisted bilayer" OR abs:"twisted graphene" '
    'OR abs:"flat band")',
]

MAX_PER_QUERY = 120
REQUEST_DELAY = 3.0  # arXiv asks for ~3 s between successive calls


def short_id(entry_id: str) -> str:
    """2406.01234v2 -> 2406.01234 ; hep-th/9901001v1 -> hep-th/9901001."""
    raw = entry_id.split("/abs/")[-1]
    return re.sub(r"v\d+$", "", raw)


def parse_feed(xml_bytes: bytes) -> list:
    root = ET.fromstring(xml_bytes)
    out = []
    for e in root.findall("atom:entry", NS):
        eid = e.findtext("atom:id", default="", namespaces=NS)
        if not eid:
            continue
        sid = short_id(eid)
        primary = e.find("arxiv:primary_category", NS)
        out.append({
            "id": sid,
            "title": " ".join((e.findtext("atom:title", "", NS) or "").split()),
            "abstract": " ".join((e.findtext("atom:summary", "", NS) or "").split()),
            "authors": [a.findtext("atom:name", "", NS)
                        for a in e.findall("atom:author", NS)],
            "primary_category": primary.get("term") if primary is not None else "",
            "categories": [c.get("term") for c in e.findall("atom:category", NS)],
            "published": e.findtext("atom:published", "", NS),
            "abs_url": f"https://arxiv.org/abs/{sid}",
            "pdf_url": f"https://arxiv.org/pdf/{sid}",
        })
    return out


def fetch_query(query: str, max_results: int) -> list:
    params = urllib.parse.urlencode({
        "search_query": query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    })
    url = f"{API}?{params}"
    req = urllib.request.Request(
        url, headers={"User-Agent": "arxiv-nqs-digest/1.0 (personal research digest)"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return parse_feed(resp.read())


def load_state(path: str) -> set:
    try:
        with open(path) as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_state(path: str, ids: set) -> None:
    with open(path, "w") as f:
        json.dump(sorted(ids), f)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--state", default="arxiv_seen.json",
                    help="JSON file of already-considered arXiv ids")
    ap.add_argument("--lookback-days", type=float, default=2.0)
    ap.add_argument("--no-commit", action="store_true",
                    help="do not add fetched ids to the state file")
    args = ap.parse_args()

    seen = load_state(args.state)
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=args.lookback_days)

    by_id: dict = {}
    for i, q in enumerate(QUERIES):
        if i:
            time.sleep(REQUEST_DELAY)
        try:
            for p in fetch_query(q, MAX_PER_QUERY):
                by_id.setdefault(p["id"], p)
        except Exception as ex:  # one lane failing should not kill the run
            print(f"warning: query lane {i} failed: {ex}", file=sys.stderr)

    candidates = []
    for p in by_id.values():
        if p["id"] in seen:
            continue
        raw = (p["published"] or "").replace("Z", "+00:00")
        try:
            pub = dt.datetime.fromisoformat(raw)
        except ValueError:
            pub = cutoff  # unparseable date -> don't let it gate the paper out
        if pub < cutoff:
            continue
        candidates.append(p)

    candidates.sort(key=lambda p: p["published"], reverse=True)
    json.dump(candidates, sys.stdout, indent=2)
    sys.stdout.write("\n")

    # "seen" means "already considered", not "already reported": commit every
    # fetched candidate so tomorrow's run doesn't re-evaluate the same papers.
    if not args.no_commit:
        save_state(args.state, seen | {p["id"] for p in candidates})

    print(f"{len(candidates)} candidate papers", file=sys.stderr)


if __name__ == "__main__":
    main()
