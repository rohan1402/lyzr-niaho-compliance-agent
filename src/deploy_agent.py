"""
Deploy (create or update) the NIAHO Compliance Agent in Lyzr from version-controlled config.

The agent definition lives in:
  - config/agent_config.json   (model, knowledge base, retrieval, memory)
  - prompts/agent_role.txt
  - prompts/agent_goal.txt
  - prompts/agent_instructions.txt

This keeps the agent reproducible from Git: edit the files, run this, and the
deployed agent matches the repo.

Usage:
  export LYZR_AGENT_API_KEY=...      # from the Lyzr dashboard / Agent API panel
  export LYZR_KB_ID=...              # Studio KB id (optional override, see note)
  export LYZR_AGENT_ID=...           # set to update an existing agent instead of creating
  python src/deploy_agent.py

Note on the knowledge base: the KB itself (uploaded NIAHO PDF, parser, embedding
model) is provisioned once in Studio and referenced by features[].config.lyzr_rag.rag_id
in config/agent_config.json, which ships with the live KB id. Set LYZR_KB_ID only to
point the deploy at a different KB. The config schema mirrors a live get_agent()
export from lyzr-python-sdk 0.1.5.
"""

import json
import os
from pathlib import Path

from lyzr_python_sdk import LyzrAgentAPI

ROOT = Path(__file__).resolve().parents[1]


def read(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8").strip()


def build_config() -> dict:
    cfg = json.loads(read("config/agent_config.json"))
    cfg["agent_role"] = read("prompts/agent_role.txt")
    cfg["agent_goal"] = read("prompts/agent_goal.txt")
    cfg["agent_instructions"] = read("prompts/agent_instructions.txt")

    kb_id = os.environ.get("LYZR_KB_ID")
    if kb_id:
        for feature in cfg.get("features", []):
            if feature.get("type") == "KNOWLEDGE_BASE":
                feature["config"]["lyzr_rag"]["rag_id"] = kb_id
    return cfg


def main() -> None:
    api_key = os.environ.get("LYZR_AGENT_API_KEY")
    if not api_key:
        raise SystemExit("Set LYZR_AGENT_API_KEY before running.")

    client = LyzrAgentAPI(api_key=api_key)
    cfg = build_config()

    for feature in cfg.get("features", []):
        if feature.get("type") != "KNOWLEDGE_BASE":
            continue
        rag_id = feature.get("config", {}).get("lyzr_rag", {}).get("rag_id", "")
        if not rag_id or rag_id == "<SET_FROM_STUDIO_KB_ID>":
            raise SystemExit(
                "lyzr_rag.rag_id is not set on the KNOWLEDGE_BASE feature. "
                "Export LYZR_KB_ID with the knowledge base id from Studio "
                "(or fill lyzr_rag.rag_id in config/agent_config.json) and re-run."
            )
        if rag_id.startswith("sk-"):
            raise SystemExit(
                "lyzr_rag.rag_id looks like an API key, not a knowledge base id — "
                "check LYZR_KB_ID in your .env."
            )

    agent_id = os.environ.get("LYZR_AGENT_ID")
    if agent_id:
        # Update the existing agent in place so the deployed agent tracks the repo.
        client.agents.update_agent(agent_id, cfg)
        print(f"Updated agent {agent_id}")
    else:
        agent = client.agents.create_agent(cfg)
        print(f"Created agent {agent.get('agent_id') or agent.get('_id')}")
        print("Set LYZR_AGENT_ID to this value to update it on the next deploy.")


if __name__ == "__main__":
    main()
