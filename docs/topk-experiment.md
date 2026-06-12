# Experiment: does raising top_k fix bare-ID exact-citation retrieval?

**Date:** 2026-06-12
**Agent:** NIAHO Compliance Agent (`<agent_id>`), model `gpt-5.4-mini`, temperature 0.7
**Knowledge base:** `niaho_accreditation_standardssaxq` (`<rag_id>`), MMR, score_threshold 0

## Question

The bare-ID query "Show me the exact text of IC.1" fails intermittently while the
title-expanded variant usually succeeds (see the README's engineering finding).
Score threshold is already at the floor (0), so the only retrieval knob left is
`top_k`. Does raising it make bare-ID exact-citation lookup reliable?

## Method

- Cells: bare-ID query at `top_k` 20 / 40 / 60, five runs each; control cell:
  title-expanded query at `top_k` 20, three runs.
- Every run used a fresh `session_id` (no memory carryover) through the same
  Agent API path as `src/chat.py`.
- The live agent's `top_k` was updated per cell via `update_agent` and verified
  via `get_agent` before querying; the repo config was restored and re-verified
  afterward (top_k 20, prompts byte-identical).
- Scoring is output-level (the retrieved chunk set is not observable through
  this API): **answered** vs **refused** ("couldn't find…", including the
  curly-apostrophe variant); **intro present** = the standard's opening
  paragraph ("active, facility-wide…") appears; **complete** = intro present
  AND all of SR.1–SR.6 appear in an answer.

## Results

| Cell | Answered | Intro present | Complete (intro + SR.1–6) |
| --- | --- | --- | --- |
| Bare ID, top_k 20 | 2/5 | 0/5 | **0/5** |
| Bare ID, top_k 40 | 4/5 | 0/5 | **0/5** |
| Bare ID, top_k 60 | 5/5 | 0/5 | **0/5** |
| Title-expanded, top_k 20 (control) | 3/3 | 3/3 | 1/3 |

An earlier same-day probe (bare ID, top_k 20, n=5, same scoring) answered 3/5,
so the pooled top_k-20 answer rate is 5/10.

Per-run detail:

| Cell | Run | Outcome | Intro | SRs found | Missing | Chars |
| --- | --- | --- | --- | --- | --- | --- |
| bare k20 | 1 | answer | no | 5/6 | SR.1 | 5,845 |
| bare k20 | 2 | hedged refusal (offered fragments) | no | — | — | 546 |
| bare k20 | 3 | refusal | no | — | — | 46 |
| bare k20 | 4 | refusal | no | — | — | 46 |
| bare k20 | 5 | answer | no | 4/6 | SR.1, SR.2 | 4,337 |
| bare k40 | 1 | answer | no | 6/6 | — | 4,721 |
| bare k40 | 2 | answer | no | 4/6 | SR.1, SR.2 | 4,217 |
| bare k40 | 3 | refusal | no | — | — | 46 |
| bare k40 | 4 | answer | no | 5/6 | SR.1 | 4,420 |
| bare k40 | 5 | answer | no | 4/6 | SR.1, SR.2 | 4,217 |
| bare k60 | 1 | answer | no | 5/6 | SR.1 | 8,592 |
| bare k60 | 2 | answer | no | 5/6 | SR.1 | 8,492 |
| bare k60 | 3 | answer | no | 4/6 | SR.1, SR.2 | 4,274 |
| bare k60 | 4 | answer | no | 5/6 | SR.1 | 5,713 |
| bare k60 | 5 | answer | no | 5/6 | SR.1 | 4,439 |
| expanded k20 | 1 | answer | yes | 2/6 | SR.3–SR.6 | 2,264 |
| expanded k20 | 2 | answer | yes | 2/6 | SR.3–SR.6 | 1,896 |
| expanded k20 | 3 | answer (complete) | yes | 6/6 | — | 6,998 |

## Observations

1. **Answer rate rises monotonically with top_k** (2/5 → 4/5 → 5/5).
   **Completeness does not move: 0/15 bare-ID runs were complete.**
2. **The standard's opening paragraph never appeared in any bare-ID run**
   (0/15), and SR.1 was missing from 10 of the 11 bare-ID answers.
3. **Both partial control runs truncate at exactly the same point — the end of
   SR.2d.** Combined with (2), the chunk map is visible: one chunk (or chunk
   group) holds [header + intro + SR.1–SR.2d], surfaced by title-like queries;
   separate chunks hold [SR.3 onward], surfaced by the bare-ID query. A Studio
   playground test of the bare query showed the same signature (header, then
   straight to SR.3). No single query phrasing surfaced all chunks reliably.
4. **At top_k 60 the long answers (~8.5k chars) quote overlapping chunks twice**
   (duplicate SR.3 and SR.5 text) — "exact text" with silent duplication.
5. One top_k-20 run produced an honest hedged refusal, stating there is no
   "single complete block with the entire standard text" and offering the
   available fragments (including Definitions and Surveyor Guidance excerpts).
   The model *can* detect incompleteness; at temperature 0.7 it usually
   doesn't, and instead presents whatever it received as the exact text.
6. **Even the title-expanded control is not deterministic** (1/3 complete).
   The original demo run's complete Query 2 answer was a favorable draw.

## Interpretation

Retrieval is platform-side (Lyzr's managed `lyzr_rag` embeds the raw user
message before the model runs), so which chunks of a multi-chunk standard
surface is decided entirely by the query's embedding. Bare IDs land near the
SR-enumeration chunks; the title lands near the intro chunk. Raising top_k
widens the window and so raises the probability of *answering*, but it never
assembled the full standard in 15 attempts, and at 60 it introduced duplicated
verbatim text.

For a compliance assistant, that trade is backwards. A refusal is a safe
failure; a confident partial rendering presented as "the exact text" is the
dangerous one — 10 of 11 bare-ID answers silently omitted SR.1 and/or SR.2
(QAPI collaboration and the infection preventionist's responsibilities).
Raising top_k converts safe failures into unsafe ones.

## Limitations

- Small cells (n=5, control n=3): treat rates as indicative. The strong
  signals are the splits with no overlap: intro present 0/15 bare vs 3/3
  expanded; complete 0/15 bare.
- Output-level scoring only; "never surfaced" strictly means "never appeared
  in the output".
- Temperature 0.7 adds generation-side variance to every cell.
- Results are tied to the current KB ingestion; re-chunking invalidates them.

## Recommendations

1. **Keep `top_k` at 20** (the repo value). Raising it buys answer rate, not
   correctness, and worsens the failure profile (partials, duplication, cost).
2. **Fix exact-citation at the architecture level**: route ID-style queries to
   retrieval the model controls (a direct lookup tool, or Lyzr's agentic-RAG
   mode), keeping vector search for semantic questions — the intent-routing
   design already proposed in `docs/build-writeup.md`, now backed by measured
   data.
3. Candidate follow-up experiments: a temperature-0.2 arm (does the
   answer/refuse/hedge judgment stabilize?); re-chunking the KB so every chunk
   carries the standard's ID + title header (gives bare IDs something to match).
4. Update the README's claim that the instruction-level query-expansion step
   is "the fix in this repo": instructions run after platform-side retrieval
   and cannot influence it. The measured behavior above is the honest story.

No repo or agent configuration was changed by this experiment; the live agent
was restored to the repo config and verified field-identical afterward.
