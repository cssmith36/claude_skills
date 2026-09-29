#!/usr/bin/env python3
"""Fetch recent arXiv papers for the daily NQS / ML-for-quantum digest.

Uses arXiv's RSS feeds (rss.arxiv.org) as the primary data source. The
Atom API at export.arxiv.org is currently blocked from many cloud IPs
(returns HTTP 406), whereas RSS is served from separate infrastructure
that remains accessible. RSS gives us the same paper set (each category's
newly-announced submissions for the day) with title, authors, abstract,
categories, arXiv id, and pubDate.

Pure standard library. Outputs the same JSON schema as the previous
API-based fetcher, so downstream tooling (routine, digest format) does
not need to change.

Judgement (CORE / RELEVANT / SKIP) is intentionally NOT done here --
that is the language model's job (see SKILL.md).

Exit codes:
    0 = success (may be zero candidates on a genuinely quiet day)
    2 = fetch failure (too many category feeds unreachable) -- surfaced
        so the workflow shows red instead of silently committing empty JSON.

Usage:
    python fetch_arxiv.py --state /path/to/arxiv_seen.json
"""

import argparse
import datetime as dt
import html
import json
import re
import sys
import time
import urllib.request

RSS_BASE = "https://rss.arxiv.org/rss"

# Categories we pull. arXiv RSS is per-category; there is no server-side
# keyword filter, so we keyword-gate high-volume categories client-side
# in KEYWORD_GATE below.
CATEGORIES = [
    "cond-mat.str-el",
    "cond-mat.dis-nn",
    "cond-mat.mes-hall",
    "cond-mat.mtrl-sci",
    "cond-mat.supr-con",
    "cond-mat.quant-gas",
    "quant-ph",
    "physics.chem-ph",
    "hep-lat",
]

# Categories that are high-volume with lots of unrelated content: require
# at least one quantum/many-body/ML/NQS/moire keyword in the abstract.
# Home categories (str-el, dis-nn, supr-con, quant-gas) are NOT gated;
# everything announced there is a candidate.
KEYWORD_GATE = {
    "quant-ph",
    "physics.chem-ph",
    "hep-lat",
    "cond-mat.mes-hall",
    "cond-mat.mtrl-sci",
}

GATE_RE = re.compile(
    r"\b("
    r"neural[- ]network|neural quantum|NQS|variational Monte Carlo|VMC|"
    r"FermiNet|PauliNet|PsiFormer|backflow|"
    r"machine[- ]learning|deep learning|normalizing flow|"
    r"wave[- ]?function|density functional|"
    r"Wigner crystal|Wigner solid|electron crystal|"
    r"2D electron gas|two-dimensional electron gas|artificial graphene|"
    r"fractional quantum Hall|quantum Hall|Landau level|composite fermion|"
    r"moire|moiré|twisted bilayer|twisted graphene|flat band|flat-band|"
    r"Aharonov[- ]Casher|"
    r"superconduct|Cooper pair|pairing"
    r")\b",
    re.I,
)

USER_AGENT = "arxiv-nqs-digest/2.0 (mailto:csmith4229@gmail.com)"
REQUEST_DELAY = 1.5
FEED_TIMEOUT = 30

# If fewer than this many category feeds return successfully, treat the
# whole run as a failure. RSS is normally very reliable; a large-scale
# failure means arxiv or the runner has a problem worth investigating.
MIN_FEEDS_OK = 5


ITEM_RE = re.compile(r"<item\b[^>]*>(.*?)</item>", re.DOTALL)
TAG_RES = {
    "title": re.compile(r"<title[^>]*>(.*?)</title>", re.DOTALL),
    "link": re.compile(r"<link[^>]*>(.*?)</link>", re.DOTALL),
    "description": re.compile(r"<description[^>]*>(.*?)</description>", re.DOTALL),
    "pubDate": re.compile(r"<pubDate[^>]*>(.*?)</pubDate>", re.DOTALL),
    "creator": re.compile(r"<dc:creator[^>]*>(.*?)</dc:creator>", re.DOTALL),
    "announce": re.compile(r"<arxiv:announce_type[^>]*>(.*?)</arxiv:announce_type>", re.DOTALL),
}
CATEGORY_RE = re.compile(r"<category[^>]*>([^<]+)</category>")
ID_RE = re.compile(r"arxiv\.org/abs/([^\s<]+)")


def strip_cdata(s: str) -> str:
    s = s.strip()
    if s.startswith("<![CDATA[") and s.endswith("]]>"):
        s = s[9:-3]
    return html.unescape(s.strip())


def parse_pubdate(s: str) -> str:
    """RFC-822 -> ISO 8601 (best effort)."""
    if not s:
        return ""
    try:
        d = dt.datetime.strptime(s.strip(), "%a, %d %b %Y %H:%M:%S %z")
        return d.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    except ValueError:
        return s.strip()


def parse_feed(xml_text: str, feed_category: str) -> list:
    out = []
    for m in ITEM_RE.finditer(xml_text):
        item = m.group(1)

        def field(name: str) -> str:
            r = TAG_RES[name].search(item)
            return strip_cdata(r.group(1)) if r else ""

        link = field("link")
        id_m = ID_RE.search(link)
        if not id_m:
            continue
        raw_id = id_m.group(1)
        sid = re.sub(r"v\d+$", "", raw_id.split("/")[-1] if "/" in raw_id else raw_id)

        desc = field("description")
        # RSS description = "arXiv:2609.31831v1 Announce Type: new \nAbstract: ..."
        # Strip the prefix so we're left with just the abstract.
        abstract = desc
        idx = abstract.find("Abstract:")
        if idx >= 0:
            abstract = abstract[idx + len("Abstract:") :].strip()
        abstract = " ".join(abstract.split())

        announce = field("announce").lower()
        # Only take genuinely new submissions; drop replacements and
        # cross-lists whose primary is elsewhere.
        if announce and announce != "new":
            continue

        authors_raw = field("creator")
        authors = [a.strip() for a in authors_raw.split(",") if a.strip()] if authors_raw else []

        cats = [c.strip() for c in CATEGORY_RE.findall(item)]
        primary = cats[0] if cats else feed_category

        out.append(
            {
                "id": sid,
                "title": " ".join(field("title").split()),
                "abstract": abstract,
                "authors": authors,
                "primary_category": primary,
                "categories": cats,
                "published": parse_pubdate(field("pubDate")),
                "abs_url": f"https://arxiv.org/abs/{sid}",
                "pdf_url": f"https://arxiv.org/pdf/{sid}",
                "_source_feed": feed_category,
            }
        )
    return out


def fetch_feed(category: str) -> list:
    url = f"{RSS_BASE}/{category}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=FEED_TIMEOUT) as resp:
        body = resp.read().decode("utf-8", errors="replace")
    return parse_feed(body, category)


def keyword_gated(paper: dict) -> bool:
    """True if paper passes the keyword gate for its primary category."""
    if paper["primary_category"] not in KEYWORD_GATE:
        return True
    text = f"{paper['title']} {paper['abstract']}"
    return bool(GATE_RE.search(text))


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
    ap.add_argument("--state", default="arxiv_seen.json")
    ap.add_argument("--no-commit", action="store_true",
                    help="do not add fetched ids to the state file")
    args = ap.parse_args()

    seen = load_state(args.state)

    by_id: dict = {}
    feeds_ok = 0
    for i, cat in enumerate(CATEGORIES):
        if i:
            time.sleep(REQUEST_DELAY)
        try:
            for p in fetch_feed(cat):
                # Prefer whichever feed first sees the paper -- doesn't matter
                # because the same paper appears in multiple category feeds
                # with identical content.
                by_id.setdefault(p["id"], p)
            feeds_ok += 1
        except Exception as ex:
            print(f"warning: feed {cat} failed: {ex}", file=sys.stderr)

    if feeds_ok < MIN_FEEDS_OK:
        print(
            f"FATAL: only {feeds_ok}/{len(CATEGORIES)} feeds returned; "
            f"threshold is {MIN_FEEDS_OK}. Not committing anything.",
            file=sys.stderr,
        )
        sys.exit(2)

    candidates = [
        p for p in by_id.values()
        if p["id"] not in seen and keyword_gated(p)
    ]
    candidates.sort(key=lambda p: p["published"], reverse=True)
    for p in candidates:
        p.pop("_source_feed", None)

    json.dump(candidates, sys.stdout, indent=2)
    sys.stdout.write("\n")

    # Seen state records every paper we FETCHED (not just reported), so
    # tomorrow's run doesn't re-consider today's papers regardless of
    # whether the LLM chose to include them in the digest.
    if not args.no_commit:
        save_state(args.state, seen | set(by_id.keys()))

    print(
        f"{len(candidates)} candidate papers "
        f"({len(by_id)} unique fetched from {feeds_ok}/{len(CATEGORIES)} feeds)",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
