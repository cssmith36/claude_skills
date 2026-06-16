# claude.ai/code routine setup

Paste-ready package for the wizard at https://claude.ai/code/routines.

## 1. Connected repo
- **GitHub repo:** `cssmith36/claude_skills`
- **Branch:** `main`
- **Working directory inside the repo:** `arxiv-digest/`
- **Required scope:** read + write (the routine pushes a commit each run).

## 2. Schedule
- **Cron:** `0 2 * * 1-5`
- **Timezone:** America/New_York
- **Meaning:** 02:00 local, Monday–Friday.

## 3. Tool permissions to pre-approve
- Bash (for `python3`, `git`, file writes)
- Outbound network to `export.arxiv.org` and `arxiv.org`
- GitHub write to `cssmith36/claude_skills` `main`

## 4. Model
- Sonnet is plenty for this. Haiku would also work and is cheaper if the option is offered.

## 5. Prompt — paste verbatim

```
You are running the user's daily arXiv digest for neural quantum states / ML-for-quantum-mechanics papers.

The connected repo is cssmith36/claude_skills. All work happens inside the `arxiv-digest/` folder of that repo.

Authoritative instructions live in `arxiv-digest/.claude/skills/arxiv-nqs-digest/SKILL.md` — read it before judging. Follow its Interest Profile, Output Format, and Hard Rules exactly. In particular: never invent or recall papers; copy each title, author list, arXiv id, and abs_url verbatim from the fetcher JSON; keep every "Why" grounded in the fetched abstract.

Author formatting: if a paper has ≤4 authors, list them all. If >4, list the first two and the last two separated by an ellipsis: `First1, First2, …, Last2, Last1`. Never use `et al.` — the user wants to see the senior author(s) at the end of the list.

User-specific calibration on top of the skill:
- NQS *methods* developments (architectures, training, sampling, optimization, FermiNet/PauliNet/PsiFormer/backflow) → CORE, even if the physics target is unrelated.
- Moiré superconductivity and the Aharonov–Casher model are especially high-priority → near-automatic CORE.
- FQH state preparation on quantum computers is RELEVANT, not CORE.
- Generic ML-for-quantum-chemistry generative/diffusion work over molecular conformations → SKIP.

Steps (run from the repo root):

1. `cd arxiv-digest`
2. Run the fetcher:
   `python3 .claude/skills/arxiv-nqs-digest/scripts/fetch_arxiv.py --state state/arxiv_seen.json > /tmp/arxiv_today.json`
   stderr prints the candidate count; stdout is the JSON list. The script updates `state/arxiv_seen.json` in place (treats fetched papers as seen). Needs outbound network to `export.arxiv.org` / `arxiv.org`.
3. Judge every candidate in /tmp/arxiv_today.json against the Interest Profile + the calibration above. Assign CORE, RELEVANT, or SKIP. Read the abstract, not just the title.
4. Write the digest to `digests/<YYYY-MM-DD>.md` (use today's date in the routine's local timezone) in the skill's Output Format: CORE first, then "Also relevant", dropping SKIP. Each entry must have the author line (per the formatting rule above), primary_category, abs_url, and a 1–2 sentence "Why".
   - If nothing qualifies, write exactly one line: `No new relevant papers today (<YYYY-MM-DD>).` — this is the expected outcome on weekends/holidays.
   - Optional footer noting absences (e.g. "No NQS-methods papers today", "No Aharonov–Casher today") so the user knows the lack of CORE picks is the day's reality, not a filter miss.
5. Commit and push:
   `git add state/arxiv_seen.json digests/<YYYY-MM-DD>.md`
   `git commit -m "arXiv digest <YYYY-MM-DD>"`
   `git push origin main`

Keep the digest terse — this is for the user to skim over coffee, not a report.
```

## 6. After the wizard finishes
- Click **Run now** once before the first scheduled fire. This surfaces any missing tool approvals immediately instead of at 02:00 some morning. Verify a `digests/<today>.md` lands and gets pushed.
- The local scheduled task (`arxiv-nqs-digest` in the sidebar) is already disabled, so no double-runs.
