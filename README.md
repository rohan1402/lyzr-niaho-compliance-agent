# NIAHO Compliance Agent

An agentic RAG assistant for healthcare accreditation compliance, defined as code and deployable to Lyzr. It answers staff questions about the DNV NIAHO Accreditation Requirements for Hospitals with cited, source-grounded responses, handles three distinct query types, and refuses cleanly when a question falls outside the indexed standards.

The agent was first built in Lyzr Studio, then captured here as version-controlled configuration so it is reproducible: edit the files, run the deploy script, and the deployed agent matches the repo.

## Repository structure

```
.
├── config/
│   └── agent_config.json        Model, knowledge base, retrieval, and memory settings
├── prompts/
│   ├── agent_role.txt           Who the agent is
│   ├── agent_goal.txt           What it optimizes for
│   └── agent_instructions.txt   Intent routing, query expansion, and refusal rules
├── src/
│   ├── deploy_agent.py          Create or update the agent in Lyzr from the config above
│   └── chat.py                  Query the deployed agent (includes the five demo queries)
├── docs/
│   ├── build-writeup.md         Full design writeup, including the retrieval finding
│   ├── topk-experiment.md       Measured: top_k vs bare-ID exact-citation retrieval
│   └── retrieval-experiments-round2.md   Measured: what makes exact citation reliable
├── requirements.txt
└── .env.example
```

The agent's prompts and settings are captured by the three prompt files plus `agent_config.json`; the knowledge base itself — the uploaded NIAHO corpus, its parser, and its chunking — is provisioned once in Lyzr Studio and referenced here by id. Keeping prompts as separate files (rather than inline strings) makes them reviewable and diffable in pull requests.

## Agent configuration

| Setting | Value | Reason |
| --- | --- | --- |
| Model | `gpt-5.4-mini` (OpenAI) | As deployed in Studio; answer quality comes from grounding, not model size |
| Knowledge base | `niaho_accreditation_standardssaxq` (Qdrant) | Single bounded corpus of the official standards |
| Embedding model | `text-embedding-3-large` | Strongest retrieval on dense regulatory prose |
| Parser | LLMSherpa (layout-aware) | Keeps chunk boundaries aligned with standard and SR sub-requirement boundaries |
| Retrieval | MMR, top_k 20 | Diverse coverage across standards rather than redundant chunks |
| Memory | Lyzr Cognis, cross-session off | Within-conversation follow-ups without cross-user bleed |
| Temperature | 0.2 | Determinism for verbatim citations — measured 6/6 complete exact-citation answers at 0.2 vs 3/8 at 0.7 (see `docs/retrieval-experiments-round2.md`) |

## Design principles

In a compliance domain a confident wrong answer is worse than no answer, so the agent is built around trust:

- Grounding: answers are drawn only from the indexed standards, never from the model's general knowledge.
- Citations: answers reference the specific standard IDs and SR sub-requirements they rely on, so a reviewer can verify them.
- Refusal by default: when the knowledge base does not contain the answer, the agent says so rather than inventing one.

It handles three query intents: semantic synthesis, exact-citation lookup (verbatim text), and browse or list. See `prompts/agent_instructions.txt`.

## Setup and deploy

```bash
pip install -r requirements.txt

cp .env.example .env
# fill in LYZR_AGENT_API_KEY (LYZR_KB_ID is an optional override; the live KB id is committed)

export $(grep -v '^#' .env | xargs)

# Create the agent (prints an agent id)
python src/deploy_agent.py

# Set LYZR_AGENT_ID to that id, then re-running deploy updates in place
python src/chat.py        # runs the five demo queries
```

The knowledge base (the uploaded NIAHO PDF, parser, and embedding model) is provisioned once in Studio and referenced by `lyzr_rag.rag_id` in `agent_config.json`, which ships with the live KB id (`LYZR_KB_ID` overrides it). The config schema mirrors a live `get_agent()` export from `lyzr-python-sdk` 0.1.5.

## Key engineering finding: exact-ID lookup on single-path vector RAG

The most useful outcome of this build was a retrieval limitation worth documenting — first observed by hand, then quantified in two measured experiments ([`docs/topk-experiment.md`](docs/topk-experiment.md), [`docs/retrieval-experiments-round2.md`](docs/retrieval-experiments-round2.md)).

Semantic questions about a standard retrieved it reliably, but a request phrased around the bare standard ID (for example "show me the exact text of IC.1") is unreliable: across 20 fresh-session runs at two temperatures it either refused or returned a confident *partial* rendering, and the standard's opening paragraph never surfaced once. I ruled out the score threshold (it failed even at zero). The root cause is twofold. First, the query embedding: a bare identifier like "IC.1" carries almost no semantic weight, so it lands near only some of the standard's chunks (the SR enumerations) and never near others (the intro block) — the classic weakness of single-path vector RAG. Second, the standard spans multiple chunks, so any single query surfaces the subset its phrasing resembles; raising top_k from 20 to 60 raised the answer rate (2/5 → 5/5) but never once produced the complete standard (0/15) and introduced duplicated text. For a compliance tool that partial-but-confident failure mode is worse than a refusal.

The instructions include a query-expansion step (expand a bare ID to its title "before retrieving") — and the experiments showed it cannot work here: with Lyzr's managed RAG, retrieval runs platform-side on the raw message before the model executes, so instructions cannot influence which chunks arrive. What does work, measured: putting the title in the query itself (client-side expansion), which at temperature 0.2 produced complete verbatim citations 6/6 times; and two-pass stitching (ask for the standard, then "continue with SR.3–SR.6"), complete 3/3. In production the cleaner fix is unchanged: route exact-citation queries to a direct lookup tool that bypasses embeddings, while semantic questions go to vector search — intent-based retrieval routing.

The full diagnosis and production notes are in [`docs/build-writeup.md`](docs/build-writeup.md); the run-by-run data is in the two experiment reports above.

## Author

Rohan Pant
https://www.linkedin.com/in/rohan1402
