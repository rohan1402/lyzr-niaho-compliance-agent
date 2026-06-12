# Lyzr Studio Build: Healthcare Compliance Agent

**Author:** Rohan Pant

## Summary

I built a healthcare accreditation compliance assistant in Lyzr Studio, grounded in the DNV NIAHO Accreditation Requirements for Hospitals (Rev 25-1, ~459 pages). The agent answers staff questions about accreditation standards with cited, source-grounded responses, handles three distinct query types, and refuses cleanly when a question falls outside the indexed standards.

The build also surfaced a concrete retrieval limitation that I diagnosed and worked around, and that is the most useful part of this writeup. It is a clean example of where single-path vector RAG breaks on real data, and how I would architect around it in production.

## Objective and design principles

The goal was a reliable compliance lookup tool. In a compliance domain, a confident wrong answer is worse than no answer, so the design centers on trust:

- **Grounding:** every answer is drawn only from the indexed standards, never from the model's general knowledge.
- **Citations:** answers reference the specific standard IDs and sub-requirements they rely on, so a reviewer can verify them.
- **Refusal by default:** when the knowledge base does not contain the answer, the agent says so rather than inventing one.

## Architecture and configuration

**Knowledge base.** Created a dedicated knowledge base (`niaho_accreditation_standards`) on the Qdrant vector store.

**Embedding model.** Chose `text-embedding-3-large` for the strongest retrieval quality on dense regulatory prose, prioritizing match precision over cost since in compliance a wrong retrieval is expensive. This mirrors the Voyage `voyage-3-large` choice in my own agentic RAG build.

**Document parser.** Used a layout-aware parser (LLMSherpa) rather than flat text extraction. The NIAHO document is deeply structured: standards carry two-letter prefixes (GB for governing body, IC for infection control, MM for medication management, and so on), each with nested SR sub-requirements. A layout-aware parser keeps chunk boundaries aligned with standard boundaries. If chunks bleed across standards, exact-citation lookup returns the wrong text, which is the failure that matters most here.

**Retrieval.** MMR retrieval to favor diverse coverage across multiple standards rather than returning near-duplicate chunks of the same one, which suits compliance questions that often span several standards.

**Memory.** Lyzr Cognis with cross-session retention disabled, so context is held within a conversation (enabling follow-ups like "show me the exact text of that one") but does not bleed between users, which is the correct privacy posture for this domain. Extraction was scoped to the standards and IDs discussed.

**Agent instructions.** The instructions encode three query intents and the refusal rule:
1. Semantic question: synthesize from retrieved standards and cite them.
2. Exact citation: return the verbatim regulatory text, including SR sub-requirements, rather than paraphrasing.
3. Browse or list: return an organized index of the standards present.
With an explicit instruction to refuse when retrieved content does not address the question.

## Behavior

The agent handles four behaviors, each tested live:
- **Semantic synthesis:** "What are the infection prevention and control program requirements?" returns a synthesized, cited answer spanning IC.1 and its SR sub-requirements.
- **Exact citation:** a request for a specific standard returns its verbatim text.
- **Multi-turn follow-up:** memory lets a follow-up reference a standard cited in the previous turn.
- **Out-of-scope refusal:** an unrelated clinical question (for example a dosage question) returns a clean refusal rather than a hallucinated answer.

## Key finding: exact-ID lookup is unreliable on single-path vector retrieval

This is the most interesting result of the build.

**Observation.** Semantic questions about a standard retrieved it reliably and produced cited answers. But a direct request phrased around the bare standard ID, for example "show me the exact text of IC.1," failed to retrieve and the agent refused, even though that exact standard had just been retrieved successfully by the semantic query seconds earlier.

**Diagnosis.** I ruled out the obvious causes in order:
- Not an indexing problem: the semantic query proved IC.1 was indexed and retrievable. (Chunking later turned out to be half the story — measurement showed the standard spans multiple chunks, so any single query surfaces only the subset its phrasing resembles; see below.)
- Not a score-threshold problem: the exact query still failed with the threshold set to zero, meaning nothing was being filtered out.

**Root cause.** The issue is the query embedding, not the index. A query dominated by a bare identifier like "IC.1" carries almost no semantic weight. Its embedding lands far from the dense regulatory prose of the actual standard, so the nearest-neighbor chunks returned by vector similarity are not the target standard. The same standard retrieves perfectly when asked about by topic, because the topic words sit close to the standard's text in embedding space. This is the classic weakness of single-path vector RAG: it is strong on semantic similarity and weak on exact-identifier lookup.

**Attempted fix in the studio — then falsified by measurement.** I added a query-expansion step in the agent instructions: when a user references a standard by ID, the agent should expand the ID to its title (for example IC.1 becomes "Infection Prevention and Control Program") before retrieving. Two measured experiment rounds ([`topk-experiment.md`](topk-experiment.md), [`retrieval-experiments-round2.md`](retrieval-experiments-round2.md)) showed this cannot work on this platform: Lyzr's managed RAG retrieves platform-side on the raw message before the model runs, so an instruction about how to retrieve never gets the chance to fire. Across 20 fresh-session bare-ID runs at two temperatures, the standard's opening paragraph never surfaced once; raising top_k from 20 to 60 raised the answer rate (2/5 → 5/5) but produced zero complete renderings (0/15) and introduced duplicated text. What did measurably work: putting the title into the query string itself (client-side expansion), which at temperature 0.2 returned the complete standard 6/6 times, and two-pass stitching (ask for the standard, then "continue with SR.3–SR.6"), complete 3/3. Temperature mattered because completeness failures of well-phrased queries were generation-side: at 0.7 the model often stopped after the first retrieved chunk and presented the fragment as the exact text; at 0.2 it reliably stitched everything it received.

**Fix in production.** The studio workaround compensates for the limitation, it does not remove it. In a production system I would route exact-citation queries to a direct lookup tool (keyword or ID index) that bypasses embeddings entirely, while semantic questions continue to go to vector search. That intent-based routing between retrieval strategies is the three-path design in my own agentic RAG project, and it is the correct fix because it matches the retrieval method to the query type rather than forcing every query through one pipe.

## Production considerations

If this moved beyond a single-tenant demo:
- **Retrieval routing:** a dedicated exact-lookup tool alongside vector search, selected by query intent, as above.
- **Multi-tenant isolation:** each client's standards indexed as a separate corpus, with single-tenant deployment for privacy-sensitive customers.
- **Evaluation:** a labeled test set scored for retrieval accuracy, citation correctness, and answer faithfulness, with an LLM-judge harness for offline scoring at scale (an approach I built previously for a production RAG chatbot).
- **Confidence and review:** for high-stakes compliance use, surface retrieval confidence and route low-confidence answers to human review rather than answering automatically.

## Takeaway

The build works, but the more valuable outcome was rediscovering, on real regulatory data, the precise limitation that justifies an agentic, multi-path retrieval architecture. The architecture is not real until it meets the data and you see where it breaks, and this is a clean instance of exactly that. The experiment rounds added a second lesson: the instruction-level workaround I initially believed in was itself falsified once measured — deployed behavior, not design intent, is the thing to test.

---

**Rohan Pant**
https://www.linkedin.com/in/rohan1402
