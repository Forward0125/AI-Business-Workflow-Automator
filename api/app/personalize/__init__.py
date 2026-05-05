"""Personalize agent.

Modules:
    draft -- gpt-4o-mini call with strict JSON schema; produces a
             subject + body, with inline `[research.<field>]`
             citation markers that the eval step uses to verify the
             email is actually personalized
    run   -- orchestrator: load research + qualification, draft, persist
"""
