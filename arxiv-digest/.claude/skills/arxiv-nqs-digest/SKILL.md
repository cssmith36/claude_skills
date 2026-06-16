---
name: arxiv-nqs-digest
description: >-
  Produce a daily arXiv digest of new papers on neural quantum states (NQS) and,
  more broadly, machine learning for quantum mechanics. Use this skill whenever
  running the scheduled "arXiv digest" / "morning papers" routine, or whenever
  the user asks to check, fetch, scan, or summarize recent arXiv papers on neural
  quantum states, neural-network wavefunctions, variational Monte Carlo, ML for
  quantum many-body / electronic structure, 2D quantum materials, or related
  topics. Trigger it even if the user just says "run my paper digest" or "any new
  NQS papers" without naming arXiv explicitly.
---

# arXiv NQS / ML-for-quantum digest

Find the day's genuinely relevant new arXiv papers for a researcher working on
**neural quantum states (NQS) in real space, mainly for 2D materials**, with
in-progress work on **NQS in magnetic fields**, and a broad interest in **any
machine learning for quantum mechanics**. Fetching is deterministic (a script);
judging relevance is your job.

## Workflow

1. **Fetch candidates.** Run the bundled script. It hits the arXiv API, applies a
   date window, removes papers already seen, and prints a JSON list to stdout:

   ```bash
   python scripts/fetch_arxiv.py --state <persistent_state_path>
   ```

   `<persistent_state_path>` must point at a file that survives between runs
   (e.g. a file in a connected GitHub repo or Google Drive). Load it before the
   run and save it after; without persistence you will re-report the same papers
   every day. See **State** below.

2. **Judge each candidate** against the Interest Profile. Assign exactly one tier:
   **CORE**, **RELEVANT**, or **SKIP**. Use the abstract, not just the title.

3. **Write the digest** in the Output Format, CORE first then RELEVANT, dropping
   everything marked SKIP. If nothing qualifies, say so plainly (this is normal on
   weekends and US holidays, when arXiv announces nothing new).

4. **Deliver** the digest to the configured destination (file, email, Slack —
   whatever the routine is wired to).

5. **Persist state** so today's papers are not repeated tomorrow (the script
   commits fetched ids by default; just make sure the state file is written back
   to its persistent location).

## Interest Profile

Grounded in the user's own publications: neural quantum states and their
*training / sampling methods*; the 2D electron gas and Wigner crystallization
(including in artificial graphene); correlated electrons in 2D materials; and
machine learning for electronic structure.

### CORE — report these prominently
- **NQS in magnetic fields & the quantum Hall family** — Landau levels, integer
  and fractional quantum Hall, composite fermions, neural ansätze with gauge fields
  / magnetic translation symmetry. **Highest priority:** the user has three papers
  in progress on NQS for magnetic fields and quantum Hall, so closely related work
  matters a lot — favour recall here, and flag anything that looks like it could
  scoop or overlap that line of work.
- **NQS for superconductivity** — neural-network wavefunctions for paired /
  superconducting states, pairing in Hubbard-type models, and unconventional /
  flat-band / moiré superconductivity tackled with NQS or VMC. Currently very
  important to the user.
- **Moiré / flat-band correlated systems** — twisted bilayers, flat bands,
  correlated insulators and superconductors in moiré superlattices. Important to
  the user right now; ML angle not required.
- **Neural quantum states generally** — architectures *and* their methods:
  training, optimization, sampling, parallel / quantum-inspired tempering, VMC with
  neural wavefunctions. NQS *methods* papers are CORE even if the physics target
  differs.
- **Real-space / continuum / first-quantized NQS and VMC** for electrons —
  FermiNet / PauliNet / PsiFormer lineage, neural backflow, neural Slater–Jastrow,
  continuum-NQS-vs-AFQMC comparisons.
- **Wigner crystals / Wigner solids / electron crystallization** — in artificial
  graphene, the 2D electron gas, and under quenched disorder. ML angle not required.
- **The 2D electron gas (2DEG) and correlated-electron phases in 2D materials** —
  ground-state phases, competing orders, TMD correlated states.

### RELEVANT — report under a secondary heading
Machine learning for quantum mechanics, plus methods/physics adjacent to the CORE:
- **ML for electronic structure**: learned exchange–correlation functionals,
  ML-accelerated or orbital-free DFT, error propagation in ML functionals.
- **Unconventional / 2D / moiré superconductivity** physics without an NQS angle,
  and ML-guided superconductor discovery or T_c prediction.
- ML for quantum many-body physics: ground/excited states, dynamics, spectral
  functions, the sign problem; Hamiltonian learning from measurements.
- ML for quantum chemistry and quantum Monte Carlo; NQS ↔ tensor-network interplay.
- Symmetry-equivariant / geometric deep learning, and generative models
  (diffusion, flows, autoregressive) **for quantum states or quantum sampling**.
- Differentiable-VMC / neural-wavefunction software, incl. JAX tooling
  (NetKet-style) — the user codes in Python/JAX.
- **Experimental probes of correlated electrons in 2D** (STM/imaging of Wigner
  crystals or correlated states, quantum dots, Friedel oscillations). *Optional:*
  the user co-authors these; keep if a reading list of their systems is wanted,
  drop if only theory/methods papers are desired.

### SKIP — do not report
- Pure quantum computing / quantum information / QEC / qubit-hardware papers with
  no ML-for-physics or correlated-electron content. (The user has one older 2016
  QEC paper, treated as a past interest — flip this if that is wrong.)
- Pure ML methodology with no quantum-physics application; generic DL theory; CV/NLP.
- Materials informatics that is database property-prediction with no
  electronic-structure / quantum-mechanical modelling.
- Unrelated cond-mat (e.g. classical soft matter) that slipped past the filter.

### Tie-breakers
- Between RELEVANT and SKIP, prefer SKIP — a tight digest beats an exhaustive one.
- Between CORE and RELEVANT, choose CORE when NQS, the 2DEG / Wigner-crystal
  family, or NQS-in-field is central to the paper, not merely mentioned.

## Output Format

```
# arXiv digest — {date}    ({n_core} core, {n_relevant} relevant)

## Core
### {Title}
{authors — see rule below}  ·  {primary_category}  ·  {abs_url}
Why: {one or two sentences, grounded in the abstract, on why it matches —
name the specific overlap, e.g. "real-space NQS for a magnetic-field problem".}

## Also relevant
### {Title}
{authors}  ·  {primary_category}  ·  {abs_url}
Why: {one sentence.}
```

If there are no CORE or RELEVANT papers: output a single line —
`No new relevant papers today ({date}).`

## Hard rules

- **Never invent or recall a paper.** Every entry must come from the script's JSON
  output for this run. Use its exact `title`, `authors`, `id`, and `abs_url`
  verbatim. If a paper is not in the JSON, it does not go in the digest.
- **Do not rewrite titles or author names.** Copy them as given.
- **Author list formatting:** if ≤4 authors, list them all. If >4, list the first two and the last two separated by an ellipsis: `First1, First2, …, Last2, Last1`. Never abbreviate to `et al.` — the user wants to see the senior author(s) at the end of the list.
- **Keep "Why" grounded in the fetched abstract** — do not speculate about content
  the abstract does not state.
- Quote at most a short phrase from any abstract; otherwise paraphrase.
- An empty day is a valid, expected result — report it, do not pad the digest.

## State

Each routine run is a fresh session with no memory of prior runs, so the
"already-seen" list must live somewhere persistent:
- **Recommended:** a small JSON file in a connected GitHub repo or Google Drive,
  passed to the script via `--state`. Read it in at the start, write it back at
  the end.
- The script treats *fetched* (not merely *reported*) papers as seen, so SKIPped
  papers are not re-evaluated tomorrow. If a run fails after fetching, that day's
  papers are lost from the digest; pass `--no-commit` and commit ids yourself
  after a successful delivery if you would rather avoid that.

## Tuning

The category and keyword filters live at the top of `scripts/fetch_arxiv.py` in
`QUERIES`. They trade recall for volume: high-traffic categories (cs.LG, quant-ph,
mtrl-sci) are gated behind ML/quantum keywords, so a relevant paper whose abstract
avoids those words can be missed. Widen `QUERIES` if the digest feels too sparse;
tighten the Interest Profile's SKIP rules if it feels too noisy.
