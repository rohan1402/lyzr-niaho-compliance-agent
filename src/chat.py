"""
Query the deployed NIAHO Compliance Agent.

Usage:
  export LYZR_AGENT_API_KEY=...
  export LYZR_AGENT_ID=...
  python src/chat.py "Show me the full text of the IC.1 Infection Prevention and Control Program standard."

With no argument, runs the five demo queries that exercise each behavior.
"""

import os
import sys
import uuid

from lyzr_python_sdk import LyzrAgentAPI

DEMO_QUERIES = [
    # 1. Semantic synthesis
    "What are the infection prevention and control program requirements for hospitals?",
    # 2. Exact citation — intentionally title-expanded (ID plus full standard title) so
    #    retrieval does not depend on the agent's instruction-level query expansion.
    "Show me the full text of the IC.1 Infection Prevention and Control Program standard, including its SR sub-requirements.",
    # 3. Multi-turn follow-up (relies on memory)
    "Show me the exact wording of that standard.",
    # 4. Out-of-scope refusal
    "What is the recommended insulin dosage for a diabetic patient?",
    # 5. Bare-ID lookup — intentionally uses the bare standard ID with no title to
    #    demonstrate the single-path retrieval limitation measured in docs/topk-experiment.md
    #    and docs/retrieval-experiments-round2.md. Expect a refusal or a partial answer.
    "Show me the exact text of IC.1",
]


def ask(client, agent_id, message, session_id):
    response = client.inference.chat(
        {
            "user_id": "reviewer@example.com",
            "agent_id": agent_id,
            "message": message,
            "session_id": session_id,
        }
    )
    return response.get("response", response)


def main() -> None:
    api_key = os.environ.get("LYZR_AGENT_API_KEY")
    agent_id = os.environ.get("LYZR_AGENT_ID")
    if not api_key or not agent_id:
        raise SystemExit("Set LYZR_AGENT_API_KEY and LYZR_AGENT_ID before running.")

    client = LyzrAgentAPI(api_key=api_key)
    session_id = str(uuid.uuid4())

    if len(sys.argv) > 1:
        print(ask(client, agent_id, " ".join(sys.argv[1:]), session_id))
        return

    for i, query in enumerate(DEMO_QUERIES, 1):
        print(f"\n=== Query {i}: {query}\n")
        print(ask(client, agent_id, query, session_id))


if __name__ == "__main__":
    main()
