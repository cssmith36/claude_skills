You are running my daily arXiv digest. Follow the `arxiv-nqs-digest` skill in
this repo at `.claude/skills/arxiv-nqs-digest/SKILL.md` exactly.

1. Fetch and de-duplicate candidates:
   `python .claude/skills/arxiv-nqs-digest/scripts/fetch_arxiv.py --state state/arxiv_seen.json`
   This prints candidate papers as JSON and updates `state/arxiv_seen.json`.

2. Judge each candidate against the skill's Interest Profile, assigning CORE,
   RELEVANT, or SKIP. Use ONLY papers present in the script's JSON output. Never
   invent or recall a paper. Copy each title, author list, arXiv id, and abstract
   URL verbatim from the JSON. Keep every "Why" grounded in the fetched abstract.

3. Write the digest in the skill's output format to `digests/<YYYY-MM-DD>.md`
   (CORE first, then RELEVANT, dropping SKIP). If nothing qualifies, write a single
   line: `No new relevant papers today (<YYYY-MM-DD>).` — this is normal on
   weekends/holidays.

4. Commit the updated `state/arxiv_seen.json` and the new digest file with the
   message `arXiv digest <YYYY-MM-DD>` so tomorrow's run doesn't repeat today's
   papers.

Keep it terse — this is for me to skim over coffee, not a report.
