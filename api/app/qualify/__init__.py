"""Qualify agent.

LLM-as-judge BANT scorer that turns a research_results row + a pitch
string into a structured fit score (Budget / Authority / Need / Timing).

Modules:
    score -- the OpenAI call (strict JSON schema)
    run   -- orchestrator: load research, score, persist
"""
