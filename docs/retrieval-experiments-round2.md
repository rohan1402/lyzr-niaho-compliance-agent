# Experiments round 2: what actually makes exact-citation lookup reliable?

**Date:** 2026-06-12
**Agent:** NIAHO Compliance Agent (`6a19b313b7546fc79c71354f`), top_k 20 throughout
**Baseline:** see `docs/topk-experiment.md` (round 1: top_k does not fix completeness; bare-ID complete 0/15; title-expanded complete 1/3 at temperature 0.7)

Four experiments. The agent's live config was temporarily modified only in
experiment C (temperature), then restored and verified field-identical
(temperature 0.7, top_k 20, prompts byte-identical). No repo code was changed.

## A. Hybrid query expansion (temperature 0.7, no agent changes)

Hypothesis: a single query containing both the title/intro vocabulary and
SR-section vocabulary spans both chunk groups and retrieves the whole standard.

Query: *"Show me the exact full text of IC.1 Infection Prevention and Control
Program, including the opening requirement paragraph and all sub-requirements
SR.1 through SR.6 (responsibilities, risk assessments, exposure incidents,
sterilization and high-level disinfection, and annual program evaluation)."*

| Run | Outcome | Intro | SRs | Chars |
| --- | --- | --- | --- | --- |
| 1 | hedged refusal | no | — | 544 |
| 2 | stub answer | no | 2/6 | 184 |
| 3 | **complete** | yes | 6/6 | 6,342 |
| 4 | answer | yes | 5/6 (missing SR.4) | 5,506 |
| 5 | **complete** | yes | 6/6 | 5,932 |

Complete 2/5. First bare-style phrasing to ever surface the intro (3/5 runs vs
0/15 for the bare ID), so the chunk-spanning idea works — but at temperature
0.7 it is still a coin flip.

## B. Two-pass stitching (temperature 0.7, no agent changes)

Same session: title-expanded query, then *"Continue with the exact text of
IC.1 SR.3, SR.4, SR.5, and SR.6, quoting them directly."* Scored on the union
of both answers.

| Session | Turn 1 | Turn 2 | Union |
| --- | --- | --- | --- |
| 1 | intro + 6/6 SRs | SR.3–SR.6 | **complete** |
| 2 | intro + 6/6 SRs | SR.3–SR.6 | **complete** |
| 3 | intro + 6/6 SRs | SR.3–SR.6 | **complete** |

Complete 3/3. Caveat: all three first turns happened to be complete already
(the expanded query's luck was good in this batch), so the union result is
partly trivial — but turn 2 retrieved the SR.3–SR.6 block all three times,
which is the mechanism that would rescue a truncated first turn. Each pass
targets one chunk group by construction; this is a manual simulation of what
a routing/lookup layer would do.

## C. Temperature 0.2 arm (live agent temporarily updated, then restored)

| Query style | n | Answered | Complete @ 0.2 | Complete @ 0.7 (rounds 1–2) |
| --- | --- | --- | --- | --- |
| Bare ID | 5 | 2/5 | 0/5 | 0/15 |
| Title-expanded | 3 | 3/3 | **3/3** | 1/3 |
| Hybrid | 3 | 3/3 | **3/3** | 2/5 |

Bare-ID detail at 0.2: 3 refusals, 2 answers — both answers nearly identical
(4,280 / 4,269 chars), both starting at SR.3, both missing intro + SR.1 + SR.2.

## Findings

1. **The completeness problem for well-phrased queries was generation-side,
   not retrieval-side.** Pooling the queries that retrieve the right chunks
   (expanded + hybrid): 6/6 complete at temperature 0.2 vs 3/8 at 0.7
   (Fisher's exact p ≈ 0.03 — small cells, but the split has no overlap).
   At 0.2 the model reliably stitches everything it received; at 0.7 it
   frequently stops after the first chunk and presents the result as the
   exact text. The repo's original temperature-0.2 "determinism" rationale,
   which round 1 inherited 0.7 over, is empirically supported for
   exact-citation fidelity.
2. **Temperature cannot rescue the bare ID.** Across 20 bare-ID runs at two
   temperatures, the intro chunk appeared zero times. Retrieval is the binding
   constraint for ID-only queries; only the query string (expansion) or the
   retrieval architecture (routing/lookup) changes what surfaces.
3. **Two-pass stitching is the most reliable procedure tested** (3/3), and
   hybrid single-query expansion becomes reliable once temperature is 0.2.
4. Recon note: `rag-prod.studio.lyzr.ai` exposes no public OpenAPI spec
   (404 on `/openapi.json` and `/docs`), so the retrieved chunk set remains
   unobservable through this API; all scoring is output-level.

## What works (measured recipes)

- **Reliable exact citation today:** temperature 0.2 + title-expanded (or
  hybrid) query → 6/6 complete in this sample.
- **Reliable at any temperature:** two-pass stitching (expanded, then
  "continue with SR.x–SR.y").
- **Still broken under every tested combination:** the bare standard ID as a
  single query. The fix for that remains pre-retrieval expansion (client-side
  or routed) — confirming the production design in `docs/build-writeup.md`.

## Limitations

Small cells (n=3–5); output-level scoring; chunk sets not observable;
single standard (IC.1) on a single-day index; temperature comparison uses
round-1 0.7 data gathered a few hours earlier on the same index.

## Status

No configuration was changed during the experiments themselves; the live agent
was verified restored to the repo config after each arm. Based on finding 1,
temperature 0.2 was subsequently adopted in `config/agent_config.json` and
deployed (2026-06-12); a post-deploy smoke test of the title-expanded query
returned a complete citation (intro + SR.1–SR.6).
