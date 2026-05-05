"""Lead intake + workflow pipeline modules.

Modules:
    lead     -- intake_lead(): validate URL, fetch homepage, upsert
                companies + leads rows, return summary metadata
    research -- (step 7) Brave Search + LLM extraction
    qualify  -- (step 8) BANT scoring
    personalize -- (step 9) outreach email generation
    pipeline -- (step 10) orchestrator
"""
