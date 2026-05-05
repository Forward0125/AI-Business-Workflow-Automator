"""Research agent.

Modules:
    brave   -- Brave Search API wrapper (free tier; no-op when
               BRAVE_API_KEY is blank)
    extract -- LLM extraction with strict JSON-schema response format
    run     -- orchestrator: load cached HTML for a lead, optionally
               call Brave, run the LLM extraction, write the
               research_results row
"""
